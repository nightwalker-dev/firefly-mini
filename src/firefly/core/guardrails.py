"""Firefly Mini guardrail layer.

Every action the agent wants to take (shell command, typed text, hotkey) is
passed through :class:`Guardrails` *before* execution. Design rules:

1. **Default-deny for the catastrophic.** A hard-coded blocklist that the LLM,
   config and CLI flags cannot override (disk wipes, root deletion, fork bombs,
   reverse shells, kernel memory writes, removing essential packages).
2. **Parse, don't grep.** Commands are split on shell control operators with
   quote awareness, wrappers (``sudo``, ``env``, ``nohup``, ``xargs`` ...) are
   peeled off and nested code (``bash -c``, ``$(...)``, backticks, ``eval``)
   is analysed recursively. Anything we cannot parse is treated as risky.
3. **Humans approve, never the model.** ``CONFIRM`` and ``MFA`` verdicts must be
   resolved by a UI callback talking to the human. ``MFA`` needs a one-time
   challenge code (plus TOTP if configured) typed on a keyboard.
4. **Predict the blast radius.** Bulk/elevated file operations get a dry-run
   impact report (file count, bytes, sample paths); package removals are
   simulated with ``apt-get -s``.
"""

from __future__ import annotations

import glob
import hmac
import os
import re
import secrets
import shlex
import shutil
import subprocess
import threading
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Iterable


# --------------------------------------------------------------------------- #
# Verdict model
# --------------------------------------------------------------------------- #
class Risk(IntEnum):
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Action(str, Enum):
    ALLOW = "allow"  # run without asking
    CONFIRM = "confirm"  # human must say yes
    MFA = "mfa"  # human must pass a typed challenge (+TOTP)
    BLOCK = "block"  # never runs

    @property
    def rank(self) -> int:
        return ["allow", "confirm", "mfa", "block"].index(self.value)


@dataclass
class Finding:
    rule: str
    risk: Risk
    action: Action
    reason: str
    segment: str = ""


@dataclass
class ImpactReport:
    targets: list[str] = field(default_factory=list)
    files: int = 0
    dirs: int = 0
    bytes: int = 0
    sample: list[str] = field(default_factory=list)
    truncated: bool = False
    simulation: str | None = None
    notes: list[str] = field(default_factory=list)

    def human(self) -> str:
        more = "+" if self.truncated else ""
        lines = [
            f"Blast radius: {self.files}{more} files, {self.dirs}{more} dirs, "
            f"{_fmt_bytes(self.bytes)}{more}"
        ]
        if self.sample:
            lines.append("Sample: " + ", ".join(self.sample[:8]))
        lines.extend(self.notes)
        if self.simulation:
            lines.append("Simulation:\n" + self.simulation)
        return "\n".join(lines)


@dataclass
class Verdict:
    subject: str
    kind: str  # "shell" | "type" | "hotkey"
    action: Action = Action.ALLOW
    risk: Risk = Risk.SAFE
    findings: list[Finding] = field(default_factory=list)
    requires_sudo: bool = False
    impact: ImpactReport | None = None
    segments: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.action is Action.ALLOW

    @property
    def blocked(self) -> bool:
        return self.action is Action.BLOCK

    def add(self, f: Finding) -> None:
        self.findings.append(f)
        if f.risk > self.risk:
            self.risk = f.risk
        if f.action.rank > self.action.rank:
            self.action = f.action

    def summary(self) -> str:
        head = f"[{self.action.value.upper()}] risk={self.risk.name}"
        if self.requires_sudo:
            head += " (sudo)"
        body = "\n".join(f"  - {f.rule}: {f.reason}" for f in self.findings) or "  - no findings"
        out = f"{head}\n{body}"
        if self.impact:
            out += "\n" + self.impact.human()
        return out

    def explain(self) -> str:
        """Returns clear 'why blocked' explanation with actionable safer alternatives."""
        from firefly.security.explainer import default_block_explainer

        return default_block_explainer.explain(self).format_text()


class GuardrailViolation(RuntimeError):
    def __init__(self, verdict: Verdict):
        super().__init__(verdict.summary())
        self.verdict = verdict


# --------------------------------------------------------------------------- #
# Static knowledge
# --------------------------------------------------------------------------- #
HOME = os.path.realpath(os.path.expanduser("~"))

CRITICAL_PATHS = frozenset(
    {
        "/",
        "/bin",
        "/boot",
        "/boot/efi",
        "/dev",
        "/efi",
        "/etc",
        "/home",
        "/lib",
        "/lib32",
        "/lib64",
        "/libx32",
        "/media",
        "/mnt",
        "/opt",
        "/proc",
        "/root",
        "/run",
        "/sbin",
        "/snap",
        "/srv",
        "/sys",
        "/usr",
        "/usr/bin",
        "/usr/lib",
        "/usr/lib64",
        "/usr/local",
        "/usr/sbin",
        "/usr/share",
        "/usr/include",
        "/var",
        "/var/lib",
        "/var/log",
        "/var/cache",
        "/etc/ssh",
        "/etc/pam.d",
        "/etc/systemd",
        HOME,
        os.path.join(HOME, ".ssh"),
        os.path.join(HOME, ".gnupg"),
        os.path.join(HOME, ".config"),
        os.path.join(HOME, ".local"),
        os.path.join(HOME, "Documents"),
    }
)

SENSITIVE_FILES = frozenset(
    {
        "/etc/passwd",
        "/etc/shadow",
        "/etc/group",
        "/etc/gshadow",
        "/etc/sudoers",
        "/etc/fstab",
        "/etc/crypttab",
        "/etc/hostname",
        "/etc/hosts",
        "/etc/resolv.conf",
        "/etc/ssh/sshd_config",
        "/etc/default/grub",
        "/boot/grub/grub.cfg",
        "/etc/security/limits.conf",
        "/etc/login.defs",
        "/etc/environment",
    }
)
SENSITIVE_PREFIXES = ("/etc/sudoers.d", "/etc/pam.d", "/boot/", "/etc/apparmor", "/etc/selinux")
# Truncating/overwriting these breaks the system outright.
UNWRITABLE_FILES = frozenset(
    {
        "/etc/passwd",
        "/etc/shadow",
        "/etc/group",
        "/etc/gshadow",
        "/etc/sudoers",
        "/etc/fstab",
        "/boot/grub/grub.cfg",
    }
)

BLOCK_DEVICE_RE = re.compile(
    r"/dev/(?:sd[a-z]|hd[a-z]|vd[a-z]|xvd[a-z]|nvme\d|mmcblk\d|md\d|dm-\d|loop\d|"
    r"sr\d|nbd\d|zd\d|mapper/|disk/|root\b|block/)"
)
KERNEL_SURFACE_RE = re.compile(
    r"/dev/(?:mem|kmem|port)\b|/proc/sysrq-trigger|/proc/sys/kernel/|"
    r"/sys/firmware/efi/efivars|/proc/kcore|/sys/kernel/security"
)
# bash ":(){ :|:& };:" style and named variants: f(){ f|f& }; f
FORK_BOMB_RE = re.compile(r"([\w:.]+)\s*\(\s*\)\s*\{[^}]*?\1\s*\|\s*\1\s*&")
FORK_LOOP_RE = re.compile(
    r"(?:while|for)\b[^\n]*\bfork\s*\(|\bos\.fork\s*\(\s*\)[^\n]*while|"
    r"while\s*(?:true|1|:)\s*;?\s*do[^\n]*&\s*done[^\n]*&"
)
REVERSE_SHELL_RE = re.compile(
    r"/dev/(?:tcp|udp)/|\bnc(?:at)?\b[^|;&]*\s-(?:e|c)\b|\bsocat\b[^|;&]*exec:|"
    r"\bbash\s+-i\s*>&|\bsh\s+-i\s*[<>]&"
)
# Trojan-source / terminal-injection characters (tab and newline are allowed).
CONTROL_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]"
)

WRAPPERS = {
    "sudo",
    "doas",
    "pkexec",
    "env",
    "nohup",
    "nice",
    "ionice",
    "time",
    "timeout",
    "stdbuf",
    "command",
    "builtin",
    "exec",
    "chrt",
    "taskset",
    "setsid",
    "unbuffer",
    "flock",
    "systemd-run",
    "firejail",
    "torsocks",
    "proxychains",
    "proxychains4",
    "strace",
    "ltrace",
    "watch",
    "chroot",
    "busybox",
    "xargs",
    "parallel",
    "runuser",
    "unshare",
    "nsenter",
    "run0",
    "catchsegv",
}
ELEVATORS = {"sudo", "doas", "pkexec", "su", "run0", "runuser"}
SHELL_KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "time"}
SHELL_TERMINATORS = {"fi", "done", "esac", "}", "in"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh", "ash", "mksh"}
INTERPRETERS = SHELLS | {"python", "python2", "python3", "perl", "ruby", "node", "php", "lua"}
# Options of wrappers that consume the next argument.
WRAPPER_ARG_OPTS = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "nice": {"-n"},
    "ionice": {"-c", "-n", "-p"},
    "chrt": {"-p"},
    "taskset": {"-p"},
    "xargs": {"-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a"},
    "flock": {"-w", "-E"},
    "env": {"-u", "-C", "-S"},
    "watch": {"-n", "-d"},
    "stdbuf": {"-i", "-o", "-e"},
    "runuser": {"-u", "-g"},
    "systemd-run": {"-p", "-u"},
}

SAFE_COMMANDS = {
    "ls",
    "ll",
    "la",
    "pwd",
    "whoami",
    "id",
    "uname",
    "hostname",
    "date",
    "uptime",
    "cal",
    "echo",
    "printf",
    "cat",
    "bat",
    "batcat",
    "less",
    "more",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    "cut",
    "tr",
    "grep",
    "rg",
    "egrep",
    "fgrep",
    "fd",
    "fdfind",
    "which",
    "type",
    "whereis",
    "file",
    "stat",
    "du",
    "df",
    "free",
    "ps",
    "pgrep",
    "lsblk",
    "lscpu",
    "lsusb",
    "lspci",
    "lsmod",
    "ss",
    "netstat",
    "ping",
    "dig",
    "host",
    "nslookup",
    "traceroute",
    "tracepath",
    "printenv",
    "true",
    "false",
    "test",
    "[",
    "fastfetch",
    "neofetch",
    "tree",
    "diff",
    "cmp",
    "md5sum",
    "sha1sum",
    "sha256sum",
    "jq",
    "realpath",
    "dirname",
    "basename",
    "seq",
    "sleep",
    "man",
    "tldr",
    "nproc",
    "locale",
    "dmesg",
    "sensors",
    "column",
    "w",
    "who",
    "last",
    "groups",
    "getent",
    "lsof",
    "vmstat",
    "iostat",
    "mpstat",
    "uptime",
    "notify-send",
    "xdg-open",
    "cd",
    "readlink",
    "nl",
    "fold",
    "rev",
    "tac",
    "expr",
    "bc",
}
WRITE_LOW_COMMANDS = {
    "mkdir",
    "touch",
    "cp",
    "ln",
    "tar",
    "unzip",
    "zip",
    "gzip",
    "gunzip",
    "wget",
    "curl",
    "code",
    "nano",
    "vim",
    "nvim",
    "pip",
    "pip3",
    "pipx",
    "npm",
    "npx",
    "cargo",
    "make",
    "python",
    "python3",
    "feh",
    "swaybg",
    "gsettings",
    "playerctl",
    "pactl",
    "wpctl",
    "brightnessctl",
    "nmcli",
    "xdotool",
    "ydotool",
    "grim",
    "slurp",
    "scrot",
    "kitty",
    "alacritty",
}

ESSENTIAL_PACKAGES = re.compile(
    r"^(?:libc6|libc-bin|systemd|systemd-sysv|init|sudo|bash|dash|coreutils|util-linux|"
    r"apt|dpkg|base-files|base-passwd|login|passwd|grub.*|linux-image.*|linux-generic.*|"
    r"shim-signed|libpam.*|network-manager|ubuntu-minimal|ubuntu-desktop.*|debianutils|"
    r"findutils|grep|sed|tar|gzip|mount|e2fsprogs|libsystemd0|python3|python3-minimal|"
    r"glibc|pacman|filesystem|linux|dnf|rpm|kernel.*)(?::\w+)?$"
)
SECURITY_SERVICES = re.compile(
    r"^(?:apparmor|ufw|firewalld|auditd|fail2ban|nftables|iptables|netfilter-persistent|"
    r"selinux.*|clamav.*|clamd|crowdsec.*|rkhunter|aide.*|unattended-upgrades|polkit|"
    r"systemd-journald|rsyslog|apport)(?:\.service|\.socket)?$"
)

DANGEROUS_HOTKEYS = {
    frozenset({"ctrl", "alt", "delete"}): "reboot/logout combo",
    frozenset({"ctrl", "alt", "backspace"}): "kills the display server",
    frozenset({"alt", "sysrq"}): "magic SysRq",
    frozenset({"super", "shift", "e"}): "exits the sway/i3 session",
    frozenset({"super", "shift", "q"}): "may log out / close session",
}
# Hotkeys that commonly run whatever is on the prompt / paste into terminals.
TERMINAL_HOTKEYS = {frozenset({"ctrl", "shift", "v"}), frozenset({"shift", "insert"})}


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


# --------------------------------------------------------------------------- #
# Shell lexing helpers
# --------------------------------------------------------------------------- #
_CTRL_OPS = ("&&", "||", "|&", ";;", ";", "|", "&", "\n")


def split_segments(cmd: str) -> tuple[list[tuple[str, str]], bool]:
    """Split on shell control operators, respecting quotes, escapes and subshells.

    Returns ``([(operator_before, segment), ...], balanced)``. Redirections like
    ``2>&1``, ``&>`` and ``>|`` are not treated as operators.
    """
    segs: list[tuple[str, str]] = []
    buf: list[str] = []
    op_before = ""
    sq = dq = False
    depth = 0
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if c == "\\" and not sq and i + 1 < n:
            buf.append(cmd[i : i + 2])
            i += 2
            continue
        if c == "'" and not dq:
            sq = not sq
        elif c == '"' and not sq:
            dq = not dq
        elif not sq and not dq:
            word_start = i == 0 or cmd[i - 1] in " \t\n;&|("
            if c == "(" or (c == "{" and word_start):
                depth += 1
            elif (c == ")" or (c == "}" and word_start)) and depth:
                depth -= 1
            elif depth == 0:
                op = next((o for o in _CTRL_OPS if cmd.startswith(o, i)), None)
                prev = buf[-1] if buf else ""
                if op == "&" and (prev.endswith((">", "<")) or cmd.startswith("&>", i)):
                    op = None
                if op == "|" and prev.endswith(">"):
                    op = None
                if op:
                    seg = "".join(buf).strip()
                    if seg:
                        segs.append((op_before, seg))
                    op_before = op.strip() or ";"
                    buf = []
                    i += len(op)
                    continue
        buf.append(c)
        i += 1
    seg = "".join(buf).strip()
    if seg:
        segs.append((op_before, seg))
    return segs, not (sq or dq or depth)


def extract_substitutions(cmd: str) -> list[str]:
    """Bodies of ``$(...)``, ``<(...)``, ``>(...)`` and backticks (outside single quotes)."""
    out: list[str] = []
    i, n, sq = 0, len(cmd), False
    while i < n:
        c = cmd[i]
        if c == "\\" and not sq:
            i += 2
            continue
        if c == "'":
            sq = not sq
        elif (
            not sq and c in "$<>" and cmd.startswith("(", i + 1) and not cmd.startswith("((", i + 1)
        ):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(cmd[j], 0)
                j += 1
            out.append(cmd[i + 2 : j - 1])
            i = j
            continue
        elif not sq and c == "`":
            j = cmd.find("`", i + 1)
            out.append(cmd[i + 1 :] if j == -1 else cmd[i + 1 : j])
            if j == -1:
                break
            i = j + 1
            continue
        i += 1
    return out


_REDIR_RE = re.compile(r"^(\d*|&)(>>|>\||>&|>|<<<|<<|<>|<&|<)(.*)$")


def split_redirections(tokens: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Separate argv from redirections. Returns ``(argv, [(op, target), ...])``."""
    argv: list[str] = []
    redirs: list[tuple[str, str]] = []
    skip = False
    for idx, tok in enumerate(tokens):
        if skip:
            skip = False
            continue
        m = _REDIR_RE.match(tok)
        if m:
            op, target = m.group(2), m.group(3)
            if not target and idx + 1 < len(tokens):
                target, skip = tokens[idx + 1], True
            redirs.append((op, target))
        else:
            argv.append(tok)
    return argv, redirs


def norm_path(p: str, cwd: str) -> str:
    p = os.path.expandvars(os.path.expanduser(p))
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.normpath(p)


def is_critical(path: str) -> bool:
    return path == "/" or path.rstrip("/") in CRITICAL_PATHS


def is_sensitive(path: str) -> bool:
    return path in SENSITIVE_FILES or path.startswith(SENSITIVE_PREFIXES)


def short_flags(args: Iterable[str]) -> set[str]:
    flags: set[str] = set()
    for a in args:
        if a == "--":
            break
        if a.startswith("--"):
            flags.add(a.split("=", 1)[0])
        elif a.startswith("-") and len(a) > 1:
            flags.update(f"-{ch}" for ch in a[1:])
    return flags


def positional(args: list[str]) -> list[str]:
    out, end = [], False
    for a in args:
        if end:
            out.append(a)
        elif a == "--":
            end = True
        elif not a.startswith("-") or a == "-":
            out.append(a)
    return out


# --------------------------------------------------------------------------- #
# MFA challenge, kill switch, rate limiter
# --------------------------------------------------------------------------- #
@dataclass
class Challenge:
    code: str
    subject: str
    expires: float


class MFAGate:
    """One-time typed challenge code, plus TOTP when FIREFLY_TOTP_SECRET is set.

    The code is shown to the human on the HUD/terminal; voice cannot satisfy it.
    """

    ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion

    def __init__(self, totp_secret: str | None = None, ttl: float = 120.0):
        self.totp_secret = totp_secret
        self.ttl = ttl
        self._active: Challenge | None = None

    @property
    def totp_enabled(self) -> bool:
        return bool(self.totp_secret)

    def issue(self, subject: str) -> Challenge:
        code = "".join(secrets.choice(self.ALPHABET) for _ in range(6))
        self._active = Challenge(code, subject, time.monotonic() + self.ttl)
        return self._active

    def verify(self, subject: str, code: str, totp: str | None = None) -> bool:
        ch, self._active = self._active, None  # single use, success or not
        if ch is None or time.monotonic() > ch.expires or ch.subject != subject:
            return False
        if not hmac.compare_digest(ch.code.encode(), code.strip().upper().encode()):
            return False
        if self.totp_enabled:
            try:
                import pyotp
            except ImportError:
                return False  # fail closed: configured but unverifiable
            if (
                not totp
                or not self.totp_secret
                or not pyotp.TOTP(self.totp_secret).verify(totp.strip(), valid_window=1)
            ):
                return False
        return True


class KillSwitch:
    """Emergency stop: in-process event + on-disk STOP file (``firefly stop``)."""

    def __init__(self, stop_file: Path):
        self.stop_file = stop_file
        self._event = threading.Event()

    def trigger(self, reason: str = "manual") -> None:
        self._event.set()
        self.stop_file.parent.mkdir(parents=True, exist_ok=True)
        self.stop_file.write_text(f"{time.time()} {reason}\n")

    def reset(self) -> None:
        self._event.clear()
        self.stop_file.unlink(missing_ok=True)

    @property
    def engaged(self) -> bool:
        return self._event.is_set() or self.stop_file.exists()


class RateLimiter:
    """Sliding one-second window limiter for GUI input actions."""

    def __init__(self, per_second: float):
        self.limit = max(1, int(per_second))
        self._hits: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self._hits and now - self._hits[0] > 1.0:
            self._hits.popleft()
        if len(self._hits) >= self.limit:
            return False
        self._hits.append(now)
        return True


# --------------------------------------------------------------------------- #
# The guardrail engine
# --------------------------------------------------------------------------- #
def _f(v: Verdict, rule: str, risk: Risk, action: Action, reason: str, seg: str = "") -> None:
    v.add(Finding(rule, risk, action, reason, seg))


class Guardrails:
    MAX_LEN = 8192
    MAX_DEPTH = 4
    IMPACT_FILE_CAP = 20_000
    IMPACT_TIME_CAP = 2.0
    BULK_FILES = 500
    BULK_BYTES = 1 << 30  # 1 GiB

    def __init__(
        self,
        auto_approve_max_risk: Risk | int = Risk.LOW,
        simulate_packages: bool = True,
        cwd: str | None = None,
    ):
        # Never allow auto-approval above MEDIUM, whatever the config says.
        self.auto_approve_max_risk = Risk(min(int(auto_approve_max_risk), int(Risk.MEDIUM)))
        self.simulate_packages = simulate_packages
        self.cwd = cwd or os.getcwd()

    # ------------------------------------------------------------------ API
    def check_command(self, command: str, cwd: str | None = None) -> Verdict:
        v = Verdict(subject=command, kind="shell")
        if not command or not command.strip():
            _f(v, "empty", Risk.LOW, Action.BLOCK, "empty command")
            return v
        self._analyse(command, v, cwd or self.cwd, depth=0)
        self._finalise(v)
        return v

    def check_typed_text(self, text: str, target_is_terminal: bool = True) -> Verdict:
        """Typing into a terminal is shell execution by another name."""
        v = Verdict(subject=text, kind="type")
        if CONTROL_CHARS_RE.search(text):
            _f(
                v,
                "control-chars",
                Risk.HIGH,
                Action.BLOCK,
                "typed text contains control/bidi characters",
            )
        if target_is_terminal:
            for line in text.splitlines():
                if not line.strip():
                    continue
                sub = Verdict(subject=line, kind="shell")
                self._analyse(line, sub, self.cwd, depth=0)
                for fnd in sub.findings:
                    v.add(fnd)
                v.requires_sudo |= sub.requires_sudo
                v.impact = v.impact or sub.impact
        self._finalise(v)
        return v

    def check_hotkey(self, keys: list[str]) -> Verdict:
        alias = {
            "control": "ctrl",
            "del": "delete",
            "win": "super",
            "meta": "super",
            "cmd": "super",
            "return": "enter",
            "prtsc": "sysrq",
            "print": "sysrq",
        }
        norm = frozenset(alias.get(k.lower().strip(), k.lower().strip()) for k in keys)
        v = Verdict(subject="+".join(sorted(norm)), kind="hotkey")
        for combo, why in DANGEROUS_HOTKEYS.items():
            if combo <= norm:
                _f(v, "dangerous-hotkey", Risk.HIGH, Action.CONFIRM, why)
        if {"ctrl", "alt"} <= norm and any(re.fullmatch(r"f\d{1,2}", k) for k in norm):
            _f(v, "vt-switch", Risk.MEDIUM, Action.CONFIRM, "switches virtual terminal")
        if norm in TERMINAL_HOTKEYS:
            _f(v, "paste", Risk.MEDIUM, Action.CONFIRM, "pastes clipboard (unknown content)")
        self._finalise(v)
        return v

    # ----------------------------------------------------------- internals
    def _finalise(self, v: Verdict) -> None:
        if v.action is Action.ALLOW and (v.risk > self.auto_approve_max_risk or v.requires_sudo):
            v.action = Action.CONFIRM
            if v.requires_sudo and v.risk < Risk.MEDIUM:
                v.risk = Risk.MEDIUM

    def _analyse(self, cmd: str, v: Verdict, cwd: str, depth: int) -> None:
        if depth > self.MAX_DEPTH:
            _f(
                v,
                "nesting-depth",
                Risk.CRITICAL,
                Action.BLOCK,
                "command nesting too deep to verify",
                cmd,
            )
            return
        if len(cmd) > self.MAX_LEN:
            _f(v, "too-long", Risk.HIGH, Action.BLOCK, f"command exceeds {self.MAX_LEN} chars")
            return
        if CONTROL_CHARS_RE.search(cmd):
            _f(
                v,
                "control-chars",
                Risk.CRITICAL,
                Action.BLOCK,
                "contains NUL/escape/bidi characters (terminal or trojan-source injection)",
            )
            return
        normalized = unicodedata.normalize("NFKC", cmd)
        if normalized != cmd:
            _f(
                v,
                "unicode-homoglyph",
                Risk.HIGH,
                Action.CONFIRM,
                "non-canonical unicode; analysing NFKC form",
            )
            cmd = normalized

        # Whole-string signatures that survive any tokenisation trick.
        if FORK_BOMB_RE.search(cmd) or FORK_LOOP_RE.search(cmd):
            _f(v, "fork-bomb", Risk.CRITICAL, Action.BLOCK, "fork bomb pattern", cmd)
        if REVERSE_SHELL_RE.search(cmd):
            _f(v, "reverse-shell", Risk.CRITICAL, Action.BLOCK, "reverse/bind shell pattern", cmd)
        if re.search(r"--no-preserve-root\b", cmd):
            _f(
                v,
                "no-preserve-root",
                Risk.CRITICAL,
                Action.BLOCK,
                "--no-preserve-root is never allowed",
            )

        # Feature 102: Red-team evasion defenses
        if re.search(
            r"\b(?:base64\s+-(?:d|-decode)|openssl\s+enc\s+-d)\b[^\n|;&]*\|\s*(?:bash|sh|zsh|dash)\b",
            cmd,
            re.IGNORECASE,
        ):
            _f(
                v,
                "obfuscated-base64",
                Risk.CRITICAL,
                Action.BLOCK,
                "obfuscated base64 decoded shell execution detected",
                cmd,
            )
        if re.search(
            r"printf\s+['\"][^'\"]*\\(?:x[0-9a-fA-F]{2}|[0-7]{3})[^'\"]*['\"][^\n|;&]*\|\s*(?:bash|sh)\b",
            cmd,
            re.IGNORECASE,
        ):
            _f(
                v,
                "obfuscated-hex",
                Risk.CRITICAL,
                Action.BLOCK,
                "obfuscated hex/octal shell execution detected",
                cmd,
            )
        if re.search(r"\brev\b[^\n|;&]*\|\s*(?:bash|sh)\b", cmd, re.IGNORECASE):
            _f(
                v,
                "obfuscated-rev",
                Risk.CRITICAL,
                Action.BLOCK,
                "reversed string shell execution trick detected",
                cmd,
            )
        if re.search(
            r"<<\s*['\"]?(?:EOF|STOP|SH)['\"]?[^\n]*\n.*?\b(?:rm\s+-[a-zA-Z]*r|mkfs|dd\s+if=)",
            cmd,
            re.IGNORECASE | re.DOTALL,
        ):
            _f(
                v,
                "heredoc-dangerous",
                Risk.CRITICAL,
                Action.BLOCK,
                "heredoc containing dangerous destructive commands detected",
                cmd,
            )
        if re.search(r"/(?:bin|usr/bin)/(?:\?\?+|r\?)\s+-[a-zA-Z]*r", cmd, re.IGNORECASE):
            _f(
                v,
                "wildcard-binary-evasion",
                Risk.CRITICAL,
                Action.BLOCK,
                "wildcard path evasion on critical binaries detected",
                cmd,
            )

        # Feature 91: Policy-as-code rule engine integration
        try:
            from firefly.security.policy import default_policy_engine

            policy_fnd = default_policy_engine.evaluate_command(cmd, cwd)
            if policy_fnd:
                v.add(policy_fnd)
        except Exception:
            pass

        for sub in extract_substitutions(cmd):
            self._analyse(sub, v, cwd, depth + 1)

        segs, balanced = split_segments(cmd)
        if not balanced:
            _f(
                v,
                "unbalanced",
                Risk.HIGH,
                Action.BLOCK,
                "unbalanced quotes/brackets: cannot verify what would run",
            )
        prev: str | None = None
        for op, seg in segs:
            if depth == 0:
                v.segments.append(seg)
            prev, cwd = self._segment(seg, op, prev, v, cwd, depth)

    def _peel(self, argv: list[str], v: Verdict, seg: str) -> list[str]:
        """Strip env assignments and wrapper commands, recording privilege escalation."""
        guard = 0
        while argv and guard < 16:
            guard += 1
            head = argv[0]
            if head in SHELL_KEYWORDS:
                argv = argv[1:]
                continue
            if head in SHELL_TERMINATORS:
                return []
            if head in ("for", "select", "case", "function"):
                return []  # header only; its body arrives as later segments
            if re.match(r"^[A-Za-z_]\w*=", head):
                if re.match(
                    r"^(LD_PRELOAD|LD_LIBRARY_PATH|LD_AUDIT|PATH|BASH_ENV|ENV|PROMPT_COMMAND)=",
                    head,
                ):
                    _f(
                        v,
                        "env-hijack",
                        Risk.HIGH,
                        Action.CONFIRM,
                        f"overrides {head.split('=')[0]}",
                        seg,
                    )
                argv = argv[1:]
                continue
            name = os.path.basename(head)
            if name in ELEVATORS:
                v.requires_sudo = True
                if name == "su":
                    rest = argv[1:]
                    if "-c" in rest and rest.index("-c") + 1 < len(rest):
                        return ["bash", "-c", rest[rest.index("-c") + 1]]
                    _f(
                        v,
                        "interactive-root",
                        Risk.HIGH,
                        Action.BLOCK,
                        "interactive root shell cannot be supervised",
                        seg,
                    )
                    return []
            if name not in WRAPPERS:
                break
            if (
                name == "sudo"
                and any(a in ("-s", "-i", "--shell", "--login") for a in argv[1:])
                and len(positional(argv[1:])) == 0
            ):
                _f(
                    v,
                    "interactive-root",
                    Risk.HIGH,
                    Action.BLOCK,
                    "interactive root shell cannot be supervised",
                    seg,
                )
                return []
            if name == "chroot":
                argv = argv[2:] if len(argv) > 2 else []
                continue
            # drop wrapper + its options (and option arguments)
            consume = WRAPPER_ARG_OPTS.get(name, set())
            i = 1
            while i < len(argv) and argv[i].startswith("-"):
                if argv[i] == "--":
                    i += 1
                    break
                i += 2 if argv[i] in consume else 1
            if name == "timeout" and i < len(argv):
                i += 1  # duration
            if name in ("nice",) and i < len(argv) and re.fullmatch(r"-?\d+", argv[i]):
                i += 1
            argv = argv[i:]
        return argv

    def _segment(
        self, seg: str, op: str, prev: str | None, v: Verdict, cwd: str, depth: int
    ) -> tuple[str | None, str]:
        # Strip a leading subshell/group so "(rm -rf /)" or "{ ...; }" is analysed.
        inner = seg.strip()
        if (inner.startswith("(") and inner.endswith(")")) or (
            inner.startswith("{") and inner.endswith("}")
        ):
            self._analyse(inner[1:-1].strip().rstrip(";"), v, cwd, depth + 1)
            return None, cwd
        try:
            tokens = shlex.split(seg, comments=True, posix=True)
        except ValueError:
            tokens = seg.split()
            _f(v, "unparseable", Risk.HIGH, Action.CONFIRM, "could not tokenise segment", seg)
        if not tokens:
            return None, cwd
        argv, redirs = split_redirections(tokens)
        for rop, target in redirs:
            self._check_redirect(rop, target, v, seg, cwd)
        argv = self._peel(argv, v, seg)
        if not argv:
            return None, cwd
        name = os.path.basename(argv[0])
        args = argv[1:]

        # Piping into an interpreter: curl ... | sh
        if op in ("|", "|&") and name in INTERPRETERS and not positional(args):
            fetched = prev in ("curl", "wget", "fetch", "aria2c", "nc", "base64", "xxd", "openssl")
            _f(
                v,
                "pipe-to-shell",
                Risk.HIGH if fetched else Risk.MEDIUM,
                Action.CONFIRM,
                f"pipes {'downloaded ' if fetched else ''}data into {name}",
                seg,
            )

        # Recurse into inline code.
        if name in SHELLS and "-c" in short_flags(args):
            shell_args = positional(args)
            if shell_args:
                self._analyse(shell_args[0], v, cwd, depth + 1)
            return name, cwd
        if name == "eval" or (name in ("source", ".") and args and args[0] == "/dev/stdin"):
            self._analyse(" ".join(args), v, cwd, depth + 1)
            _f(v, "eval", Risk.MEDIUM, Action.CONFIRM, "dynamic evaluation", seg)
            return name, cwd
        if name in INTERPRETERS - SHELLS and short_flags(args) & {"-c", "-e", "-E", "-r"}:
            code = " ".join(positional(args))
            self._inline_code(code, v, seg, cwd, depth)

        if name == "cd":
            target = positional(args)[0] if positional(args) else "~"
            return name, norm_path(target, cwd)

        handler = getattr(self, f"_r_{re.sub(r'[^a-z0-9]', '_', name)}", None)
        if name.startswith("mkfs") or name in (
            "mke2fs",
            "mkswap",
            "wipefs",
            "blkdiscard",
            "sgdisk",
            "sfdisk",
            "gdisk",
            "cfdisk",
            "fdisk",
            "parted",
            "badblocks",
            "hdparm",
            "nvme",
            "zpool",
            "pvcreate",
            "vgremove",
            "lvremove",
            "mdadm",
        ):
            self._r_disk(name, args, v, seg)
        elif handler:
            handler(args, v, seg, cwd)
        elif name in SAFE_COMMANDS:
            pass
        elif name in WRITE_LOW_COMMANDS:
            _f(v, "write-op", Risk.LOW, Action.ALLOW, f"{name} modifies state", seg)
        else:
            _f(
                v,
                "unknown-command",
                Risk.LOW,
                Action.ALLOW,
                f"'{name}' not in known catalogue",
                seg,
            )

        # Generic: touching a block device or kernel surface in any argument.
        for a in args:
            if KERNEL_SURFACE_RE.search(a) and name not in SAFE_COMMANDS:
                _f(
                    v,
                    "kernel-surface",
                    Risk.CRITICAL,
                    Action.BLOCK,
                    f"touches kernel interface {a}",
                    seg,
                )
        return name, cwd

    def _inline_code(self, code: str, v: Verdict, seg: str, cwd: str, depth: int) -> None:
        """Best-effort scan of python/perl one-liners for shell-outs and deletions."""
        for m in re.finditer(
            r"""(?:os\.system|subprocess\.\w+|popen|system|exec)\s*\(\s*\[?\s*(['"])(.+?)\1""", code
        ):
            self._analyse(m.group(2), v, cwd, depth + 1)
        if re.search(r"shutil\.rmtree|os\.remove|os\.unlink|unlink\s*\(|rmdir|\.rmtree", code):
            _f(v, "inline-delete", Risk.HIGH, Action.CONFIRM, "inline script deletes files", seg)
            for p in re.findall(
                r"""(?:rmtree|remove|unlink|rmdir)\s*\(\s*['"]([^'"]+)['"]""", code
            ):
                if is_critical(norm_path(p, cwd)):
                    _f(
                        v,
                        "inline-delete-critical",
                        Risk.CRITICAL,
                        Action.BLOCK,
                        f"deletes {p}",
                        seg,
                    )
        if re.search(r"/dev/(sd|nvme|mmcblk|vd)", code):
            _f(
                v,
                "inline-blockdev",
                Risk.CRITICAL,
                Action.BLOCK,
                "inline script touches a block device",
                seg,
            )

    def _check_redirect(self, op: str, target: str, v: Verdict, seg: str, cwd: str) -> None:
        if (
            op.startswith("<")
            or target.startswith("&")
            or target in ("/dev/null", "/dev/stdout", "/dev/stderr", "-")
        ):
            return
        path = norm_path(target, cwd)
        if BLOCK_DEVICE_RE.match(path):
            _f(
                v,
                "write-blockdev",
                Risk.CRITICAL,
                Action.BLOCK,
                f"redirects output onto {path}",
                seg,
            )
        elif KERNEL_SURFACE_RE.search(path):
            _f(
                v,
                "write-kernel",
                Risk.CRITICAL,
                Action.BLOCK,
                f"writes kernel interface {path}",
                seg,
            )
        elif path in UNWRITABLE_FILES and op in (">", ">|"):
            _f(v, "truncate-system-file", Risk.CRITICAL, Action.BLOCK, f"truncates {path}", seg)
        elif path.startswith("/etc/sudoers"):
            _f(v, "sudoers", Risk.CRITICAL, Action.MFA, f"modifies {path}", seg)
        elif is_sensitive(path):
            _f(v, "write-sensitive", Risk.HIGH, Action.CONFIRM, f"writes {path}", seg)
        elif path.startswith(("/etc/", "/usr/", "/boot/", "/var/lib/", "/lib")):
            _f(v, "write-system", Risk.MEDIUM, Action.CONFIRM, f"writes system path {path}", seg)
        elif os.path.isdir(path) or is_critical(path):
            _f(v, "write-dir", Risk.HIGH, Action.BLOCK, f"redirect onto directory {path}", seg)

    # ------------------------------------------------------- impact predictor
    def predict_impact(self, targets: list[str], cwd: str, recursive: bool) -> ImpactReport:
        rep = ImpactReport(targets=list(targets))
        deadline = time.monotonic() + self.IMPACT_TIME_CAP
        seen_dev: set[int] = set()
        for t in targets:
            matches = (
                glob.glob(norm_path(t, cwd)) if any(c in t for c in "*?[") else [norm_path(t, cwd)]
            )
            if not matches:
                rep.notes.append(f"target not found: {t}")
            for m in matches:
                try:
                    st = os.lstat(m)
                except OSError:
                    rep.notes.append(f"cannot stat {m}")
                    continue
                seen_dev.add(st.st_dev)
                if os.path.isdir(m) and not os.path.islink(m):
                    rep.dirs += 1
                    if not recursive:
                        continue
                    for root, dirs, files in os.walk(m, onerror=lambda e: None):
                        rep.dirs += len(dirs)
                        for fn in files:
                            p = os.path.join(root, fn)
                            try:
                                rep.bytes += os.lstat(p).st_size
                            except OSError:
                                pass
                            rep.files += 1
                            if len(rep.sample) < 8:
                                rep.sample.append(p)
                        if os.path.ismount(root) and root != m:
                            rep.notes.append(f"crosses mount point {root}")
                        if rep.files > self.IMPACT_FILE_CAP or time.monotonic() > deadline:
                            rep.truncated = True
                            break
                else:
                    rep.files += 1
                    rep.bytes += st.st_size
                    if len(rep.sample) < 8:
                        rep.sample.append(m)
        if len(seen_dev) > 1:
            rep.notes.append("targets span multiple filesystems")
        return rep

    def _attach_impact(
        self, v: Verdict, seg: str, targets: list[str], cwd: str, recursive: bool, verb: str
    ) -> None:
        rep = self.predict_impact(targets, cwd, recursive)
        v.impact = rep
        if rep.truncated or rep.files > self.BULK_FILES or rep.bytes > self.BULK_BYTES:
            _f(
                v,
                "bulk-operation",
                Risk.HIGH,
                Action.CONFIRM,
                f"{verb} affects {rep.files}{'+' if rep.truncated else ''} files / {_fmt_bytes(rep.bytes)}",
                seg,
            )

    # ------------------------------------------------------------- per-command
    def _targets_check(
        self, verb: str, targets: list[str], recursive: bool, v: Verdict, seg: str, cwd: str
    ) -> bool:
        """Shared protection for rm/chmod/chown/mv/... Returns True if blocked."""
        blocked = False
        for t in targets:
            if re.search(r"\$\{?\w+", t) and not os.path.expandvars(t) != t:
                _f(
                    v,
                    "unresolved-var",
                    Risk.HIGH,
                    Action.CONFIRM,
                    f"{verb} target '{t}' depends on an unset variable",
                    seg,
                )
            path = norm_path(t, cwd)
            base = path
            if any(c in path for c in "*?["):
                base = os.path.dirname(path.split("*")[0].split("?")[0].split("[")[0]) or "/"
                if is_critical(base) and (recursive or verb in ("rm", "mv", "shred")):
                    _f(
                        v,
                        "glob-critical",
                        Risk.CRITICAL,
                        Action.BLOCK,
                        f"{verb} glob over protected directory {base}",
                        seg,
                    )
                    blocked = True
                    continue
            if is_critical(path):
                _f(
                    v,
                    "protected-path",
                    Risk.CRITICAL,
                    Action.BLOCK,
                    f"{verb} on protected path {path}",
                    seg,
                )
                blocked = True
            elif is_sensitive(path):
                _f(
                    v,
                    "sensitive-file",
                    Risk.HIGH,
                    Action.MFA if verb in ("rm", "shred") else Action.CONFIRM,
                    f"{verb} on sensitive file {path}",
                    seg,
                )
            elif path.startswith(
                ("/usr/", "/etc/", "/boot/", "/var/lib/", "/lib", "/bin", "/sbin", "/opt/")
            ):
                _f(
                    v,
                    "system-path",
                    Risk.HIGH,
                    Action.CONFIRM,
                    f"{verb} inside system tree {path}",
                    seg,
                )
        return blocked

    def _r_rm(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        flags = short_flags(args)
        recursive = bool(flags & {"-r", "-R", "--recursive"})
        targets = positional(args)
        if not targets:
            return
        if self._targets_check("rm", targets, recursive, v, seg, cwd):
            return
        _f(
            v,
            "delete",
            Risk.MEDIUM if recursive or len(targets) > 3 else Risk.LOW,
            Action.CONFIRM if recursive else Action.ALLOW,
            f"deletes {len(targets)} target(s)",
            seg,
        )
        self._attach_impact(v, seg, targets, cwd, recursive, "rm")

    _r_unlink = _r_rm

    def _r_rmdir(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        self._targets_check("rmdir", positional(args), False, v, seg, cwd)

    def _r_shred(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        targets = positional(args)
        if any(BLOCK_DEVICE_RE.match(norm_path(t, cwd)) for t in targets):
            _f(v, "shred-device", Risk.CRITICAL, Action.BLOCK, "shred on a block device", seg)
            return
        if not self._targets_check("shred", targets, False, v, seg, cwd):
            _f(v, "irreversible", Risk.HIGH, Action.CONFIRM, "shred is irreversible", seg)
            self._attach_impact(v, seg, targets, cwd, False, "shred")

    def _r_truncate(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        for t in positional(args):
            p = norm_path(t, cwd)
            if BLOCK_DEVICE_RE.match(p) or p in UNWRITABLE_FILES or is_critical(p):
                _f(v, "truncate-critical", Risk.CRITICAL, Action.BLOCK, f"truncate {p}", seg)
        _f(v, "truncate", Risk.MEDIUM, Action.CONFIRM, "truncates files", seg)

    def _r_dd(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        kv = dict(a.split("=", 1) for a in args if "=" in a)
        of = kv.get("of")
        if of:
            p = norm_path(of, cwd)
            if BLOCK_DEVICE_RE.match(p) or (
                p.startswith("/dev/") and p not in ("/dev/null", "/dev/zero")
            ):
                _f(v, "dd-device", Risk.CRITICAL, Action.BLOCK, f"dd writes raw device {p}", seg)
                return
            if is_critical(p) or is_sensitive(p):
                _f(v, "dd-system", Risk.CRITICAL, Action.BLOCK, f"dd overwrites {p}", seg)
                return
            _f(v, "dd-write", Risk.MEDIUM, Action.CONFIRM, f"dd writes {p}", seg)
        else:
            _f(v, "dd-read", Risk.LOW, Action.ALLOW, "dd to stdout", seg)

    def _r_disk(self, name: str, args: list[str], v: Verdict, seg: str) -> None:
        readonly = name in ("fdisk", "sfdisk", "parted", "gdisk", "sgdisk") and (
            short_flags(args) & {"-l", "--list", "-p", "--print"} or "print" in args
        )
        if name == "hdparm" and not any(
            a.startswith("--security") or a.startswith("--trim") or a in ("--fwdownload", "-z")
            for a in args
        ):
            readonly = True
        if name == "nvme" and args[:1] in (["list"], ["smart-log"], ["id-ctrl"]):
            readonly = True
        if readonly:
            _f(v, "disk-read", Risk.LOW, Action.ALLOW, f"{name} read-only query", seg)
        else:
            _f(
                v,
                "disk-format",
                Risk.CRITICAL,
                Action.BLOCK,
                f"{name} can destroy partitions/filesystems — run it yourself",
                seg,
            )

    def _r_cryptsetup(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if any(
            a in ("luksFormat", "erase", "luksErase", "luksKillSlot", "reencrypt") for a in args
        ):
            _f(v, "crypt-destroy", Risk.CRITICAL, Action.BLOCK, "destroys LUKS headers/keys", seg)
        else:
            _f(v, "crypt", Risk.HIGH, Action.CONFIRM, "cryptsetup operation", seg)

    def _chperm(self, verb: str, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        flags = short_flags(args)
        recursive = bool(flags & {"-R", "--recursive"})
        pos = positional(args)
        mode, targets = (pos[0], pos[1:]) if pos else ("", [])
        if self._targets_check(verb, targets, recursive, v, seg, cwd) and recursive:
            return
        if verb == "chmod" and re.search(
            r"(^|[^0-7])[0-7]?[0-7]?7[0-7]?7$|o\+w|a\+w|\+s|u\+s|g\+s|^[4267]\d{3}$", mode
        ):
            _f(
                v,
                "weak-perms",
                Risk.HIGH,
                Action.CONFIRM,
                f"chmod {mode} (world-writable or setuid)",
                seg,
            )
        if recursive:
            _f(v, "recursive-perms", Risk.MEDIUM, Action.CONFIRM, f"recursive {verb}", seg)
            self._attach_impact(v, seg, targets, cwd, True, verb)
        else:
            _f(v, "perms", Risk.LOW, Action.ALLOW, verb, seg)

    def _r_chmod(self, args, v, seg, cwd):  # noqa: ANN001
        self._chperm("chmod", args, v, seg, cwd)

    def _r_chown(self, args, v, seg, cwd):  # noqa: ANN001
        self._chperm("chown", args, v, seg, cwd)

    def _r_chgrp(self, args, v, seg, cwd):  # noqa: ANN001
        self._chperm("chgrp", args, v, seg, cwd)

    def _r_chattr(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if any(a.startswith("-") and "i" in a for a in args):
            _f(
                v,
                "chattr-immutable",
                Risk.HIGH,
                Action.MFA,
                "removes immutable flag (tamper protection)",
                seg,
            )
        else:
            _f(v, "chattr", Risk.MEDIUM, Action.CONFIRM, "changes file attributes", seg)

    def _r_mv(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        pos = positional(args)
        if len(pos) < 2:
            return
        sources, dest = pos[:-1], pos[-1]
        if norm_path(dest, cwd) == "/dev/null":
            _f(
                v,
                "mv-devnull",
                Risk.CRITICAL,
                Action.BLOCK,
                "moving files into /dev/null destroys them",
                seg,
            )
            return
        if self._targets_check("mv", sources, True, v, seg, cwd):
            return
        dp = norm_path(dest, cwd)
        if is_sensitive(dp) or dp in UNWRITABLE_FILES:
            _f(v, "mv-overwrite-sensitive", Risk.CRITICAL, Action.MFA, f"overwrites {dp}", seg)
        _f(v, "move", Risk.LOW, Action.ALLOW, "moves files", seg)

    def _r_cp(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        pos = positional(args)
        if len(pos) >= 2:
            dp = norm_path(pos[-1], cwd)
            if BLOCK_DEVICE_RE.match(dp):
                _f(v, "cp-device", Risk.CRITICAL, Action.BLOCK, f"copies onto raw device {dp}", seg)
            elif dp in UNWRITABLE_FILES:
                _f(v, "cp-overwrite-system", Risk.CRITICAL, Action.MFA, f"overwrites {dp}", seg)
            elif is_sensitive(dp) or dp.startswith(("/etc/", "/usr/", "/boot/")):
                _f(v, "cp-system", Risk.HIGH, Action.CONFIRM, f"writes into {dp}", seg)
        _f(v, "copy", Risk.LOW, Action.ALLOW, "copies files", seg)

    def _r_tee(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        for t in positional(args):
            self._check_redirect(
                ">>" if {"-a", "--append"} & short_flags(args) else ">", t, v, seg, cwd
            )

    def _r_ln(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        pos = positional(args)
        if pos and "-f" in short_flags(args) | {"-f" if "--force" in args else ""}:
            dp = norm_path(pos[-1], cwd)
            if is_sensitive(dp) or is_critical(dp):
                _f(v, "ln-hijack", Risk.CRITICAL, Action.BLOCK, f"force-links over {dp}", seg)

    def _r_find(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        destructive = "-delete" in args or any(
            a in ("-exec", "-execdir", "-ok", "-okdir")
            and i + 1 < len(args)
            and os.path.basename(args[i + 1]) in ("rm", "shred", "chmod", "chown", "mv", "truncate")
            for i, a in enumerate(args)
        )
        if not destructive:
            if "-exec" in args or "-execdir" in args:
                i = args.index("-exec") if "-exec" in args else args.index("-execdir")
                inner = " ".join(a for a in args[i + 1 :] if a not in (";", "+", "\\;", "{}"))
                if inner:
                    self._analyse(inner, v, cwd, 1)
            return
        roots = [a for a in args if not a.startswith(("-", "(", ")", "!"))][:1] or ["."]
        if self._targets_check("find-delete", roots, True, v, seg, cwd):
            return
        _f(v, "find-delete", Risk.HIGH, Action.CONFIRM, "find with destructive action", seg)
        self._attach_impact(v, seg, roots, cwd, True, "find")

    def _r_kill(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        pids = positional(args)
        if any(p in ("1", "-1") for p in pids) or "-1" in args[-1:]:
            _f(v, "kill-init", Risk.CRITICAL, Action.BLOCK, "kills init / every process", seg)
        else:
            _f(v, "kill", Risk.LOW, Action.ALLOW, "signals processes", seg)

    def _r_pkill(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        pats = positional(args)
        if ("-u" in args and "root" in args) or any(
            p
            in (
                "systemd",
                "init",
                "Xorg",
                "Xwayland",
                "gnome-shell",
                "kwin_wayland",
                "sway",
                "sshd",
                "dbus-daemon",
            )
            for p in pats
        ):
            _f(v, "kill-system", Risk.HIGH, Action.CONFIRM, "kills system/session processes", seg)
        else:
            _f(v, "pkill", Risk.MEDIUM, Action.CONFIRM, "pattern-based process kill", seg)

    _r_killall = _r_pkill

    def _r_killall5(self, args, v, seg, cwd):  # noqa: ANN001
        _f(v, "kill-all", Risk.CRITICAL, Action.BLOCK, "killall5 terminates everything", seg)

    def _power(self, args, v, seg, cwd):  # noqa: ANN001
        _f(v, "power", Risk.HIGH, Action.CONFIRM, "shuts down / reboots the machine", seg)

    _r_shutdown = _r_reboot = _r_poweroff = _r_halt = _power

    def _r_init(self, args, v, seg, cwd):  # noqa: ANN001
        if args[:1] in (["0"], ["6"], ["1"]):
            self._power(args, v, seg, cwd)

    _r_telinit = _r_init

    def _r_systemctl(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        pos = positional(args)
        verb = pos[0] if pos else ""
        units = pos[1:]
        if verb in (
            "status",
            "list-units",
            "list-unit-files",
            "is-active",
            "is-enabled",
            "show",
            "cat",
            "list-timers",
            "is-failed",
            "",
        ):
            return
        if verb in (
            "poweroff",
            "reboot",
            "halt",
            "kexec",
            "suspend",
            "hibernate",
            "emergency",
            "rescue",
            "isolate",
            "soft-reboot",
        ):
            self._power(args, v, seg, cwd)
            return
        if verb in ("stop", "disable", "mask", "kill") and any(
            SECURITY_SERVICES.match(u) for u in units
        ):
            _f(
                v,
                "disable-security",
                Risk.CRITICAL,
                Action.MFA,
                f"{verb} security service {' '.join(units)}",
                seg,
            )
            return
        user = "--user" in args
        _f(
            v,
            "service",
            Risk.LOW if user else Risk.MEDIUM,
            Action.ALLOW if user else Action.CONFIRM,
            f"systemctl {verb} {' '.join(units)}",
            seg,
        )

    def _r_service(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if len(args) >= 2 and args[1] == "stop" and SECURITY_SERVICES.match(args[0]):
            _f(v, "disable-security", Risk.CRITICAL, Action.MFA, f"stops {args[0]}", seg)
        elif len(args) >= 2 and args[1] != "status":
            _f(v, "service", Risk.MEDIUM, Action.CONFIRM, f"service {args[0]} {args[1]}", seg)

    def _r_ufw(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if (
            args[:1] in (["disable"], ["reset"])
            or "allow" in args
            and ("any" in args or "0.0.0.0/0" in args)
        ):
            _f(v, "disable-security", Risk.CRITICAL, Action.MFA, f"ufw {' '.join(args)}", seg)
        elif args[:1] not in (["status"], ["app"], []):
            _f(v, "firewall-change", Risk.MEDIUM, Action.CONFIRM, f"ufw {' '.join(args)}", seg)

    def _r_iptables(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if short_flags(args) & {"-F", "-X", "--flush", "--delete-chain", "-Z"} or (
            "-P" in args and "ACCEPT" in args
        ):
            _f(
                v,
                "disable-security",
                Risk.CRITICAL,
                Action.MFA,
                "flushes firewall / default ACCEPT",
                seg,
            )
        elif short_flags(args) & {"-L", "-S", "--list"}:
            return
        else:
            _f(v, "firewall-change", Risk.MEDIUM, Action.CONFIRM, "modifies firewall rules", seg)

    _r_ip6tables = _r_iptables

    def _r_nft(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if "flush" in args or "delete" in args:
            _f(v, "disable-security", Risk.CRITICAL, Action.MFA, "flushes nftables rules", seg)
        elif not (args[:1] == ["list"] or args[:2] == ["-a", "list"]):
            _f(v, "firewall-change", Risk.MEDIUM, Action.CONFIRM, "modifies nftables", seg)

    def _r_setenforce(self, args, v, seg, cwd):  # noqa: ANN001
        if args[:1] in (["0"], ["Permissive"], ["permissive"]):
            _f(
                v,
                "disable-security",
                Risk.CRITICAL,
                Action.MFA,
                "disables SELinux enforcement",
                seg,
            )

    def _r_aa_teardown(self, args, v, seg, cwd):  # noqa: ANN001
        _f(v, "disable-security", Risk.CRITICAL, Action.MFA, "unloads all AppArmor profiles", seg)

    _r_aa_disable = _r_aa_complain = _r_aa_teardown

    def _r_sysctl(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        writes = [a for a in args if "=" in a] + (["-w"] if "-w" in args else [])
        if (
            any(
                re.search(
                    r"randomize_va_space|kptr_restrict|dmesg_restrict|yama|unprivileged_bpf|"
                    r"perf_event_paranoid|modules_disabled|kexec_load_disabled",
                    a,
                )
                for a in args
            )
            and writes
        ):
            _f(v, "disable-security", Risk.CRITICAL, Action.MFA, "weakens kernel hardening", seg)
        elif writes or "-p" in args:
            _f(v, "sysctl", Risk.MEDIUM, Action.CONFIRM, "changes kernel parameters", seg)

    def _r_modprobe(self, args, v, seg, cwd):  # noqa: ANN001
        _f(v, "kernel-module", Risk.HIGH, Action.CONFIRM, "loads/unloads kernel modules", seg)

    _r_insmod = _r_rmmod = _r_modprobe

    def _r_visudo(self, args, v, seg, cwd):  # noqa: ANN001
        if not ({"-c", "--check"} & short_flags(args)):
            _f(v, "sudoers", Risk.CRITICAL, Action.MFA, "edits sudoers", seg)

    def _r_passwd(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if short_flags(args) & {"-d", "--delete", "-u"}:
            _f(v, "disable-security", Risk.CRITICAL, Action.MFA, "removes/unlocks a password", seg)
        else:
            _f(v, "passwd", Risk.HIGH, Action.CONFIRM, "changes credentials", seg)

    def _r_usermod(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if any(
            g in " ".join(args)
            for g in ("sudo", "wheel", "admin", "root", "docker", "disk", "shadow")
        ):
            _f(v, "privilege-grant", Risk.CRITICAL, Action.MFA, "grants a privileged group", seg)
        else:
            _f(v, "user-admin", Risk.HIGH, Action.CONFIRM, "modifies user accounts", seg)

    _r_useradd = _r_userdel = _r_groupmod = _r_gpasswd = _r_chpasswd = _r_usermod

    def _r_crontab(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if "-r" in short_flags(args):
            _f(v, "crontab-remove", Risk.HIGH, Action.CONFIRM, "removes all cron jobs", seg)
        elif "-l" not in short_flags(args):
            _f(
                v,
                "crontab-edit",
                Risk.MEDIUM,
                Action.CONFIRM,
                "installs cron jobs (persistence)",
                seg,
            )

    def _r_history(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if short_flags(args) & {"-c", "-w", "-d"}:
            _f(v, "anti-forensics", Risk.HIGH, Action.CONFIRM, "clears shell history", seg)

    def _r_unset(self, args, v, seg, cwd):  # noqa: ANN001
        if "HISTFILE" in args:
            _f(v, "anti-forensics", Risk.HIGH, Action.CONFIRM, "disables shell history", seg)

    def _r_journalctl(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if any(a.startswith(("--vacuum", "--rotate", "--flush")) for a in args):
            _f(
                v,
                "disable-security",
                Risk.HIGH,
                Action.MFA,
                "deletes system logs (audit trail)",
                seg,
            )

    def _r_auditctl(self, args, v, seg, cwd):  # noqa: ANN001
        if "-D" in args or ("-e" in args and "0" in args):
            _f(v, "disable-security", Risk.CRITICAL, Action.MFA, "disables kernel auditing", seg)

    def _r_mokutil(self, args, v, seg, cwd):  # noqa: ANN001
        if any(a in ("--disable-validation", "--reset", "--delete") for a in args):
            _f(v, "disable-security", Risk.CRITICAL, Action.MFA, "weakens Secure Boot", seg)

    def _r_mount(self, args, v, seg, cwd):  # noqa: ANN001
        if positional(args):
            _f(v, "mount", Risk.MEDIUM, Action.CONFIRM, "mounts/remounts a filesystem", seg)

    _r_umount = _r_swapoff = _r_mount

    def _r_git(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        joined = " ".join(args)
        if re.search(r"\bpush\b.*(--force\b|-f\b|--mirror|--delete|\s:\S)", joined):
            _f(v, "git-force", Risk.MEDIUM, Action.CONFIRM, "rewrites remote history", seg)
        elif re.search(
            r"\breset\b.*--hard|\bclean\b.*-\w*[fdx]|\bcheckout\b\s+--?\s+\.|\bfilter-branch\b|\breflog expire",
            joined,
        ):
            _f(v, "git-destructive", Risk.MEDIUM, Action.CONFIRM, "discards local work", seg)

    def _r_docker(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        joined = " ".join(args)
        if re.search(r"--privileged|-v\s+/:/|--volume[= ]/:|--pid[= ]host|--net[= ]host", joined):
            _f(
                v,
                "container-escape",
                Risk.HIGH,
                Action.CONFIRM,
                "container gets host-level access",
                seg,
            )
        if re.search(r"\b(system|volume|image|container)\s+prune\b|\brm\b.*-f", joined):
            _f(v, "docker-prune", Risk.MEDIUM, Action.CONFIRM, "removes containers/volumes", seg)

    _r_podman = _r_docker

    def _r_pip(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if "--break-system-packages" in args:
            _f(v, "pip-system", Risk.HIGH, Action.CONFIRM, "modifies system python packages", seg)
        elif args[:1] in (["install"], ["uninstall"]):
            _f(v, "pip", Risk.LOW, Action.ALLOW, f"pip {args[0]}", seg)

    _r_pip3 = _r_pip

    # ---- package managers (with apt dry-run simulation) ----
    def _pkg(self, mgr: str, args: list[str], v: Verdict, seg: str) -> None:
        pos = positional(args)
        verb = pos[0] if pos else ""
        pkgs = pos[1:]
        removing = (
            verb in ("remove", "purge", "autoremove", "erase", "autopurge")
            or (mgr == "pacman" and any(a.startswith("-R") for a in args))
            or (mgr == "dpkg" and short_flags(args) & {"-r", "-P", "--remove", "--purge"})
        )
        if mgr == "dpkg" and short_flags(args) & {"--force-all", "--force-remove-essential"}:
            _f(v, "pkg-force", Risk.CRITICAL, Action.BLOCK, "forces essential package removal", seg)
            return
        if removing:
            for p in pkgs:
                if ESSENTIAL_PACKAGES.match(p.split("=")[0]):
                    _f(
                        v,
                        "remove-essential",
                        Risk.CRITICAL,
                        Action.BLOCK,
                        f"removes essential package {p}",
                        seg,
                    )
                    return
            _f(v, "pkg-remove", Risk.HIGH, Action.CONFIRM, f"{mgr} {verb} {' '.join(pkgs)}", seg)
            if mgr in ("apt", "apt-get") and self.simulate_packages:
                self._simulate_apt(verb, pkgs, v, seg)
        elif verb in ("install", "upgrade", "full-upgrade", "dist-upgrade", "reinstall") or (
            mgr == "pacman" and any(a.startswith("-S") for a in args)
        ):
            _f(v, "pkg-install", Risk.MEDIUM, Action.CONFIRM, f"{mgr} {verb} {' '.join(pkgs)}", seg)
        elif (
            verb in ("update", "search", "show", "list", "policy", "info", "-Q", "-Ss") or not verb
        ):
            pass
        else:
            _f(v, "pkg-other", Risk.MEDIUM, Action.CONFIRM, f"{mgr} {verb}", seg)

    def _simulate_apt(self, verb: str, pkgs: list[str], v: Verdict, seg: str) -> None:
        if not shutil.which("apt-get"):
            return
        try:
            out = subprocess.run(
                ["apt-get", "-s", "-q", verb, *pkgs],
                capture_output=True,
                text=True,
                timeout=20,
                env={**os.environ, "LC_ALL": "C"},
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            return
        removed = re.findall(r"^Remv (\S+)", out, flags=re.M)
        rep = v.impact or ImpactReport()
        rep.simulation = f"apt would remove {len(removed)} package(s): " + " ".join(removed[:40])
        v.impact = rep
        essential = [p for p in removed if ESSENTIAL_PACKAGES.match(p)]
        if essential:
            _f(
                v,
                "remove-essential",
                Risk.CRITICAL,
                Action.BLOCK,
                f"dependency chain removes essential packages: {', '.join(essential)}",
                seg,
            )
        elif len(removed) > 20:
            _f(
                v,
                "bulk-pkg-remove",
                Risk.HIGH,
                Action.CONFIRM,
                f"cascades to {len(removed)} packages",
                seg,
            )

    def _r_apt(self, args, v, seg, cwd):  # noqa: ANN001
        self._pkg("apt", args, v, seg)

    def _r_apt_get(self, args, v, seg, cwd):  # noqa: ANN001
        self._pkg("apt-get", args, v, seg)

    def _r_dnf(self, args, v, seg, cwd):  # noqa: ANN001
        self._pkg("dnf", args, v, seg)

    _r_yum = _r_dnf

    def _r_pacman(self, args, v, seg, cwd):  # noqa: ANN001
        self._pkg("pacman", args, v, seg)

    def _r_dpkg(self, args, v, seg, cwd):  # noqa: ANN001
        self._pkg("dpkg", args, v, seg)

    def _r_snap(self, args, v, seg, cwd):  # noqa: ANN001
        self._pkg("snap", args, v, seg)

    def _r_flatpak(self, args, v, seg, cwd):  # noqa: ANN001
        self._pkg("flatpak", args, v, seg)

    def _r_sed(self, args: list[str], v: Verdict, seg: str, cwd: str) -> None:
        if any(a.startswith("-i") or a == "--in-place" for a in args):
            for t in positional(args)[1:]:
                p = norm_path(t, cwd)
                if p in UNWRITABLE_FILES or p.startswith("/etc/sudoers"):
                    _f(v, "edit-critical", Risk.CRITICAL, Action.MFA, f"in-place edit of {p}", seg)
                elif is_sensitive(p) or p.startswith(("/etc/", "/usr/", "/boot/")):
                    _f(v, "edit-system", Risk.HIGH, Action.CONFIRM, f"in-place edit of {p}", seg)
            _f(v, "edit", Risk.LOW, Action.ALLOW, "in-place edit", seg)
