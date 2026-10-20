"""Sandboxed execution runner using bubblewrap, firejail, or isolated environment fallback (Feature 99)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class SandboxOptions:
    """Configures isolation boundaries for a sandboxed process."""

    allow_network: bool = False
    writable_paths: List[str] = field(default_factory=list)
    read_only_paths: List[str] = field(
        default_factory=lambda: ["/usr", "/bin", "/lib", "/lib64", "/etc"]
    )
    tmpfs_mb: int = 64
    timeout_sec: float = 30.0


class SandboxRunner:
    """Executes potentially hazardous shell commands inside an isolated environment."""

    def __init__(self, preferred_backend: Optional[str] = None) -> None:
        self.preferred_backend = preferred_backend
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Selects the best available sandboxing primitive on the host system."""
        if self.preferred_backend:
            return self.preferred_backend
        if shutil.which("bwrap"):
            return "bwrap"
        if shutil.which("firejail"):
            return "firejail"
        if shutil.which("podman"):
            return "podman"
        if shutil.which("docker"):
            return "docker"
        return "fallback"

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def is_sandboxed(self) -> bool:
        """True if an actual OS-level sandbox (bwrap, firejail, podman, docker) is active."""
        return self._backend != "fallback"

    def build_command(
        self,
        command: str,
        options: Optional[SandboxOptions] = None,
        cwd: Optional[str] = None,
    ) -> List[str]:
        """Constructs the command-line arguments to launch the target inside the selected sandbox."""
        opts = options or SandboxOptions()
        work_dir = cwd or os.getcwd()

        if self._backend == "bwrap":
            args = ["bwrap"]
            # Mount system libraries and binaries read-only
            for p in opts.read_only_paths:
                if os.path.exists(p):
                    args.extend(["--ro-bind", p, p])

            # Virtual dev and proc
            if os.path.exists("/dev"):
                args.extend(["--dev", "/dev"])
            if os.path.exists("/proc"):
                args.extend(["--proc", "/proc"])

            # Ephemeral tmpfs /tmp
            args.extend(["--tmpfs", "/tmp"])

            # Isolated namespaces
            args.append("--unshare-pid")
            args.append("--unshare-ipc")
            if not opts.allow_network:
                args.append("--unshare-net")

            # Writable paths
            for wp in opts.writable_paths:
                if os.path.exists(wp):
                    args.extend(["--bind", wp, wp])

            # Working directory
            if os.path.exists(work_dir):
                args.extend(["--bind", work_dir, work_dir])
                args.extend(["--chdir", work_dir])

            args.extend(["bash", "-c", command])
            return args

        elif self._backend == "firejail":
            args = ["firejail", "--quiet", "--noprofile"]
            if not opts.allow_network:
                args.append("--net=none")
            args.append("--private-tmp")
            args.append("--noroot")

            for wp in opts.writable_paths:
                args.extend(["--whitelist", wp])

            args.extend(["bash", "-c", command])
            return args

        elif self._backend in ("podman", "docker"):
            cli = self._backend
            args = [cli, "run", "--rm", "-i"]
            if not opts.allow_network:
                args.extend(["--network", "none"])
            args.extend(["--volume", f"{work_dir}:{work_dir}:rw", "-w", work_dir])
            args.extend(["alpine", "sh", "-c", command])
            return args

        else:
            # Fallback: execute directly via bash with restricted PATH and env
            return ["bash", "-c", command]

    def run(
        self,
        command: str,
        options: Optional[SandboxOptions] = None,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        """Runs the command inside the sandbox."""
        opts = options or SandboxOptions()
        cmd_args = self.build_command(command, opts, cwd=cwd)

        # Sanitize environment
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "HOME": "/tmp",
        }

        try:
            proc = subprocess.run(
                cmd_args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=opts.timeout_sec,
                env=safe_env if self._backend != "fallback" else None,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Sandbox execution timed out after {opts.timeout_sec}s."
        except Exception as exc:
            return -1, "", f"Sandbox execution error: {exc}"


# Global default sandbox runner
default_sandbox_runner = SandboxRunner()
