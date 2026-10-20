"""Cross-platform abstraction layer (Linux, Windows, macOS).

Everything that differs between operating systems lives here so the rest of
the codebase can stay OS-agnostic:

* OS detection (``IS_WINDOWS`` / ``IS_MACOS`` / ``IS_LINUX``)
* Per-user data and config directories (XDG / %APPDATA% / Application Support)
* Shell resolution (bash/sh on POSIX, PowerShell/cmd on Windows)
* Process-tree termination that works without POSIX process groups
* Best-effort private file permissions
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_NAME = "firefly-mini"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def os_name() -> str:
    """Returns a normalised OS identifier: ``windows``, ``macos``, ``linux`` or ``unix``."""
    if IS_WINDOWS:
        return "windows"
    if IS_MACOS:
        return "macos"
    if IS_LINUX:
        return "linux"
    return "unix"


def os_pretty_name() -> str:
    """Human readable OS name + release, safe on every platform (no ``os.uname``)."""
    import platform

    system = platform.system() or os_name()
    release = platform.release() or ""
    return f"{system} {release}".strip()


# --------------------------------------------------------------------------- #
# Directories
# --------------------------------------------------------------------------- #
def _env_path(var: str) -> Optional[Path]:
    val = os.environ.get(var, "").strip()
    return Path(val).expanduser() if val else None


def user_data_dir(app: str = APP_NAME) -> Path:
    """Per-user directory for databases, keys, checkpoints and logs.

    Override with ``FIREFLY_DATA_DIR``.
    """
    override = _env_path("FIREFLY_DATA_DIR")
    if override:
        return override
    home = Path.home()
    if IS_WINDOWS:
        base = _env_path("LOCALAPPDATA") or home / "AppData" / "Local"
    elif IS_MACOS:
        base = home / "Library" / "Application Support"
    else:
        base = _env_path("XDG_DATA_HOME") or home / ".local" / "share"
    return base / app


def user_config_dir(app: str = APP_NAME) -> Path:
    """Per-user directory for ``config.toml`` and generated theme files.

    Override with ``FIREFLY_CONFIG_DIR``.
    """
    override = _env_path("FIREFLY_CONFIG_DIR")
    if override:
        return override
    home = Path.home()
    if IS_WINDOWS:
        base = _env_path("APPDATA") or home / "AppData" / "Roaming"
    elif IS_MACOS:
        base = home / "Library" / "Application Support"
    else:
        base = _env_path("XDG_CONFIG_HOME") or home / ".config"
    return base / app


def secure_chmod(path: Path, mode: int) -> bool:
    """Applies POSIX permissions where supported; silently no-ops on Windows.

    On Windows, ``os.chmod`` can only toggle the read-only flag, so private
    files rely on the per-user ACLs of ``%LOCALAPPDATA%`` instead.
    """
    if IS_WINDOWS:
        return False
    try:
        os.chmod(path, mode)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# Shell resolution
# --------------------------------------------------------------------------- #
SHELL_KINDS = ("posix", "powershell", "cmd")


@dataclass(frozen=True)
class ShellSpec:
    """Describes the interpreter used to execute agent commands."""

    name: str  # e.g. "bash", "pwsh", "powershell", "cmd"
    executable: str  # absolute path or bare name
    kind: str  # "posix" | "powershell" | "cmd"

    def build_argv(self, command: str) -> List[str]:
        """Builds the argv list that runs ``command`` through this shell."""
        if self.kind == "powershell":
            # Force UTF-8 output so Python can decode non-ASCII text reliably.
            prefix = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            return [
                self.executable,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                prefix + command,
            ]
        if self.kind == "cmd":
            return [self.executable, "/d", "/s", "/c", command]
        return [self.executable, "-c", command]

    @property
    def display_name(self) -> str:
        return {"posix": self.name, "powershell": "PowerShell", "cmd": "cmd.exe"}.get(
            self.kind, self.name
        )


_POSIX_CANDIDATES = ("bash", "sh", "zsh")
_WINDOWS_CANDIDATES = ("pwsh", "powershell", "cmd")


def _spec_for(name: str) -> Optional[ShellSpec]:
    lname = name.lower().removesuffix(".exe")
    exe = shutil.which(name)
    if lname in ("pwsh", "powershell"):
        return ShellSpec(lname, exe or name, "powershell") if exe else None
    if lname == "cmd":
        exe = exe or os.environ.get("COMSPEC")
        return ShellSpec("cmd", exe, "cmd") if exe else None
    return ShellSpec(lname, exe, "posix") if exe else None


def resolve_shell(preference: str = "auto") -> ShellSpec:
    """Selects the command interpreter.

    ``preference`` may be ``auto`` (default), a shell name such as ``bash``,
    ``pwsh``, ``powershell`` or ``cmd``, or an absolute path to one of those.
    """
    pref = (preference or "auto").strip()
    if pref and pref.lower() != "auto":
        spec = _spec_for(pref)
        if spec:
            return spec
        base = Path(pref).name.lower().removesuffix(".exe")
        if Path(pref).exists():
            kind = "powershell" if base in ("pwsh", "powershell") else "posix"
            kind = "cmd" if base == "cmd" else kind
            return ShellSpec(base, pref, kind)

    candidates = _WINDOWS_CANDIDATES if IS_WINDOWS else _POSIX_CANDIDATES
    for cand in candidates:
        spec = _spec_for(cand)
        if spec:
            return spec

    # Last resort: assume the platform default exists.
    if IS_WINDOWS:
        return ShellSpec("cmd", os.environ.get("COMSPEC", "cmd.exe"), "cmd")
    return ShellSpec("sh", "/bin/sh", "posix")


# --------------------------------------------------------------------------- #
# Process management
# --------------------------------------------------------------------------- #
def new_process_group_kwargs() -> Dict[str, Any]:
    """Popen kwargs that isolate the child so the whole tree can be terminated."""
    if IS_WINDOWS:
        flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        return {"creationflags": flag}
    return {"start_new_session": True}


def hidden_window_kwargs() -> Dict[str, Any]:
    """Popen kwargs that stop helper processes flashing a console window on Windows."""
    if IS_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def kill_process_tree(pid: int, grace_sec: float = 0.5) -> int:
    """Terminates ``pid`` and all of its descendants (cross-platform via psutil).

    Sends a polite terminate first, then force-kills survivors after
    ``grace_sec``. Returns the number of processes that were signalled.
    """
    try:
        import psutil
    except ImportError:  # pragma: no cover - psutil is a hard dependency
        import signal

        try:
            os.kill(pid, signal.SIGTERM)
            return 1
        except OSError:
            return 0

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return 0

    procs = parent.children(recursive=True) + [parent]
    for p in procs:
        try:
            p.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(procs, timeout=grace_sec)
    for p in alive:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    if alive:
        psutil.wait_procs(alive, timeout=grace_sec)
    return len(procs)


def decode_output(data: Optional[bytes | str]) -> str:
    """Decodes subprocess output as UTF-8, never raising on bad bytes."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def root_path() -> Path:
    """Filesystem root of the home drive (``/`` on POSIX, ``C:\\`` on Windows)."""
    return Path(Path.home().anchor or "/")


def open_with_default_app(path: Path) -> bool:
    """Opens a file or URL with the OS default handler."""
    try:
        if IS_WINDOWS:
            os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
            return True
        opener = "open" if IS_MACOS else "xdg-open"
        if shutil.which(opener):
            subprocess.Popen(
                [opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
    except Exception:
        pass
    return False
