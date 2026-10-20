"""Heuristic correction engines: typo detection, package suggestions, fuzzy path resolution, and dry-run flags."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Comprehensive database of common system binaries and developer utilities
COMMON_SYSTEM_BINARIES: List[str] = [
    "apt",
    "apt-get",
    "awk",
    "bash",
    "cat",
    "cd",
    "chmod",
    "chown",
    "cp",
    "curl",
    "df",
    "diff",
    "dig",
    "docker",
    "dpkg",
    "du",
    "echo",
    "fastfetch",
    "feh",
    "ffmpeg",
    "find",
    "git",
    "grep",
    "grim",
    "head",
    "htop",
    "ifconfig",
    "ip",
    "journalctl",
    "jq",
    "kill",
    "less",
    "ln",
    "ls",
    "make",
    "mkdir",
    "mv",
    "nano",
    "nc",
    "neofetch",
    "netstat",
    "nginx",
    "ollama",
    "pacman",
    "patch",
    "pip",
    "ps",
    "pytest",
    "python3",
    "rm",
    "rsync",
    "scrot",
    "sed",
    "sh",
    "sort",
    "ssh",
    "sudo",
    "swaybg",
    "systemctl",
    "tail",
    "tar",
    "tee",
    "top",
    "touch",
    "tree",
    "uname",
    "uptime",
    "vim",
    "wget",
    "which",
    "whoami",
    "wtype",
    "xargs",
    "xdotool",
    "ydotool",
    "zip",
    "zsh",
]

# Command-not-found database mapping missing binaries to distribution packages
COMMAND_PACKAGE_MAP: Dict[str, Dict[str, str]] = {
    "dig": {"debian": "dnsutils", "arch": "bind", "fedora": "bind-utils"},
    "nslookup": {"debian": "dnsutils", "arch": "bind", "fedora": "bind-utils"},
    "ifconfig": {"debian": "net-tools", "arch": "net-tools", "fedora": "net-tools"},
    "netstat": {"debian": "net-tools", "arch": "net-tools", "fedora": "net-tools"},
    "rg": {"debian": "ripgrep", "arch": "ripgrep", "fedora": "ripgrep"},
    "feh": {"debian": "feh", "arch": "feh", "fedora": "feh"},
    "swaybg": {"debian": "swaybg", "arch": "swaybg", "fedora": "swaybg"},
    "grim": {"debian": "grim", "arch": "grim", "fedora": "grim"},
    "scrot": {"debian": "scrot", "arch": "scrot", "fedora": "scrot"},
    "ydotool": {"debian": "ydotool", "arch": "ydotool", "fedora": "ydotool"},
    "wtype": {"debian": "wtype", "arch": "wtype", "fedora": "wtype"},
    "xdotool": {"debian": "xdotool", "arch": "xdotool", "fedora": "xdotool"},
    "ffmpeg": {"debian": "ffmpeg", "arch": "ffmpeg", "fedora": "ffmpeg"},
    "jq": {"debian": "jq", "arch": "jq", "fedora": "jq"},
    "htop": {"debian": "htop", "arch": "htop", "fedora": "htop"},
    "tree": {"debian": "tree", "arch": "tree", "fedora": "tree"},
    "fastfetch": {"debian": "fastfetch", "arch": "fastfetch", "fedora": "fastfetch"},
    "neofetch": {"debian": "neofetch", "arch": "neofetch", "fedora": "neofetch"},
    "curl": {"debian": "curl", "arch": "curl", "fedora": "curl"},
    "wget": {"debian": "wget", "arch": "wget", "fedora": "wget"},
    "rsync": {"debian": "rsync", "arch": "rsync", "fedora": "rsync"},
    "7z": {"debian": "p7zip-full", "arch": "p7zip", "fedora": "p7zip"},
    "unzip": {"debian": "unzip", "arch": "unzip", "fedora": "unzip"},
}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Damerau-Levenshtein edit distance between two strings with transpositions."""
    d: dict[tuple[int, int], int] = {}
    len1 = len(s1)
    len2 = len(s2)
    for i in range(-1, len1 + 1):
        d[(i, -1)] = i + 1
    for j in range(-1, len2 + 1):
        d[(-1, j)] = j + 1

    for i in range(len1):
        for j in range(len2):
            cost = 0 if s1[i] == s2[j] else 1
            d[(i, j)] = min(
                d[(i - 1, j)] + 1,  # deletion
                d[(i, j - 1)] + 1,  # insertion
                d[(i - 1, j - 1)] + cost,  # substitution
            )
            if i > 0 and j > 0 and s1[i] == s2[j - 1] and s1[i - 1] == s2[j]:
                d[(i, j)] = min(d[(i, j)], d[(i - 2, j - 2)] + 1)  # transposition
    return d[(len1 - 1, len2 - 1)]


def did_you_mean(
    command_str: str,
    candidates: Optional[List[str]] = None,
    max_distance: int = 2,
) -> Optional[str]:
    """Detects command typos via edit distance and suggests intended binary."""
    tokens = command_str.strip().split()
    if not tokens:
        return None
    raw_bin = tokens[0]
    # Strip any leading paths (e.g. /bin/sl -> sl)
    base_bin = Path(raw_bin).name

    pool = candidates or COMMON_SYSTEM_BINARIES
    best_candidate: Optional[str] = None
    best_dist = max_distance + 1

    for cand in pool:
        dist = levenshtein_distance(base_bin, cand)
        if dist < best_dist and dist <= max_distance:
            best_dist = dist
            best_candidate = cand

    if best_candidate and best_candidate != base_bin:
        tokens[0] = best_candidate
        return " ".join(tokens)
    return None


def suggest_package(binary_name: str, distro: str = "debian") -> Optional[Tuple[str, str]]:
    """Looks up missing binary in command-not-found DB and returns package name + install command."""
    base_name = Path(binary_name).name.lower()
    entry = COMMAND_PACKAGE_MAP.get(base_name)
    if not entry:
        return None

    distro_key = distro.lower()
    if distro_key not in entry:
        distro_key = "debian"  # fallback default

    pkg = entry[distro_key]
    if distro_key in ("debian", "ubuntu"):
        install_cmd = f"sudo apt update && sudo apt install -y {pkg}"
    elif distro_key in ("arch", "manjaro"):
        install_cmd = f"sudo pacman -S --noconfirm {pkg}"
    elif distro_key in ("fedora", "rhel", "centos"):
        install_cmd = f"sudo dnf install -y {pkg}"
    else:
        install_cmd = f"sudo apt install -y {pkg}"

    return pkg, install_cmd


def resolve_fuzzy_path(missing_path_str: str, cwd: Optional[str] = None) -> Optional[Path]:
    """Fuzzy resolves nonexistent paths to matching nearby files or directories."""
    raw_path = Path(missing_path_str)
    if not raw_path.is_absolute():
        base = Path(cwd) if cwd else Path.cwd()
        target = (base / raw_path).resolve()
    else:
        target = raw_path

    if target.exists():
        return target

    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        return None

    filename = target.name
    try:
        entries = [p.name for p in parent.iterdir()]
    except (PermissionError, OSError):
        return None

    if not entries:
        return None

    matches = difflib.get_close_matches(filename, entries, n=1, cutoff=0.6)
    if matches:
        return parent / matches[0]
    return None


def make_dry_run_command(cmd: str) -> Optional[str]:
    """Generates a dry-run / simulation version of command if supported."""
    tokens = cmd.strip().split()
    if not tokens:
        return None

    base_bin = tokens[0]

    # Package managers
    if base_bin in ("apt", "apt-get") and "install" in tokens:
        if "-s" not in tokens and "--dry-run" not in tokens:
            return f"{cmd} -s"

    if base_bin == "rsync":
        if "-n" not in tokens and "--dry-run" not in tokens:
            return f"{tokens[0]} --dry-run {' '.join(tokens[1:])}"

    if base_bin == "git":
        # git commit, push, clean support dry-run
        if any(sub in tokens for sub in ("push", "clean", "merge")):
            if "--dry-run" not in tokens:
                return f"{cmd} --dry-run"

    if base_bin == "pip" and "install" in tokens:
        if "--dry-run" not in tokens:
            return f"{cmd} --dry-run"

    if base_bin == "patch":
        if "--dry-run" not in tokens:
            return f"{cmd} --dry-run"

    return None
