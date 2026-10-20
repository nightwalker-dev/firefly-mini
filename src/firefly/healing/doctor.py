"""System self-diagnosis and readiness engine ('firefly doctor')."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import List, Optional

from rich.table import Table

from firefly.core.config import settings
from firefly.core.guardrails import KillSwitch


@dataclass
class DoctorCheck:
    """Represents a diagnostic system verification result."""

    category: str
    name: str
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    remedy: Optional[str] = None


class FireflyDoctor:
    """Performs deep system diagnostic checks across runtime, audio, display, and dependencies."""

    def __init__(self) -> None:
        self.kill_switch = KillSwitch(settings.stop_file)

    def check_python_environment(self) -> DoctorCheck:
        """Verifies Python version and environment capabilities."""
        v = sys.version_info
        ver_str = f"{v.major}.{v.minor}.{v.micro}"
        if v.major >= 3 and v.minor >= 10:
            return DoctorCheck(
                category="Runtime",
                name="Python Version",
                status="PASS",
                message=f"Python {ver_str} meets requirements (>=3.10)",
            )
        return DoctorCheck(
            category="Runtime",
            name="Python Version",
            status="FAIL",
            message=f"Python {ver_str} is outdated.",
            remedy="Upgrade to Python 3.10 or later.",
        )

    def check_guardrails_safety(self) -> DoctorCheck:
        """Verifies safety subsystems and emergency stop state."""
        if self.kill_switch.engaged:
            return DoctorCheck(
                category="Safety",
                name="Emergency Kill Switch",
                status="FAIL",
                message=f"Kill switch ENGAGED via {settings.stop_file}",
                remedy="Run 'firefly reset' to clear the stop signal.",
            )
        totp_state = "Configured" if settings.totp_secret else "Disabled (Passwordless)"
        risk_level = settings.auto_approve_max_risk
        return DoctorCheck(
            category="Safety",
            name="Guardrails Status",
            status="PASS",
            message=f"Active (Max risk floor: {risk_level}, TOTP: {totp_state})",
        )

    def check_display_backend(self) -> DoctorCheck:
        """Inspects display server protocol environment."""
        if sys.platform == "win32":
            return DoctorCheck(
                category="Display",
                name="Display Protocol",
                status="PASS",
                message="Windows Desktop active (via PyAutoGUI / MSS)",
            )

        wayland = os.environ.get("WAYLAND_DISPLAY")
        x11 = os.environ.get("DISPLAY")

        if wayland:
            return DoctorCheck(
                category="Display",
                name="Display Protocol",
                status="PASS",
                message=f"Wayland active ({wayland})",
            )
        if x11:
            return DoctorCheck(
                category="Display",
                name="Display Protocol",
                status="PASS",
                message=f"X11 active ({x11})",
            )
        return DoctorCheck(
            category="Display",
            name="Display Protocol",
            status="WARN",
            message="No active graphical display detected; operating in Headless Mode.",
            remedy="Launch inside an X11 or Wayland session for GUI automation.",
        )

    def check_multimedia_binaries(self) -> List[DoctorCheck]:
        """Audits essential and recommended external binaries."""
        is_win = sys.platform == "win32"
        binaries = [
            (
                "ffmpeg",
                "Essential for voice encoding and sound playback",
                "winget install Gyan.FFmpeg" if is_win else "sudo apt install ffmpeg",
            ),
            (
                "feh" if not is_win else "magick",
                "Wallpaper and background display engine",
                "winget install ImageMagick.ImageMagick" if is_win else "sudo apt install feh",
            ),
            (
                "ydotool" if not is_win else "powershell",
                "Keyboard and mouse simulation backend",
                "Installed by default" if is_win else "sudo apt install ydotool",
            ),
            (
                "grim" if not is_win else "python",
                "Screenshot capture backend",
                "Uses python-mss on Windows" if is_win else "sudo apt install grim",
            ),
            (
                "jq",
                "JSON processing in terminal workflows",
                "winget install jqlang.jq" if is_win else "sudo apt install jq",
            ),
        ]

        checks = []
        for binary, desc, remedy in binaries:
            path = shutil.which(binary)
            if path:
                checks.append(
                    DoctorCheck(
                        category="Dependencies",
                        name=binary,
                        status="PASS",
                        message=f"Found at {path}",
                    )
                )
            else:
                checks.append(
                    DoctorCheck(
                        category="Dependencies",
                        name=binary,
                        status="WARN",
                        message=f"Not installed ({desc})",
                        remedy=remedy,
                    )
                )
        return checks

    def check_audio_subsystem(self) -> DoctorCheck:
        """Audits audio playback capability."""
        if sys.platform == "win32":
            return DoctorCheck(
                category="Audio",
                name="Audio Engine",
                status="PASS",
                message="Windows audio engine available (winsound / PowerShell)",
            )

        audio_players = ["pw-play", "paplay", "aplay", "ffplay"]
        found = [p for p in audio_players if shutil.which(p)]
        if found:
            return DoctorCheck(
                category="Audio",
                name="Audio Engine",
                status="PASS",
                message=f"Sound output available via: {', '.join(found)}",
            )
        return DoctorCheck(
            category="Audio",
            name="Audio Engine",
            status="WARN",
            message="No system sound player detected (pw-play, paplay, aplay, or ffplay).",
            remedy="Install pipewire-pulse, pulseaudio-utils, or alsa-utils.",
        )

    def check_storage_permissions(self) -> DoctorCheck:
        """Verifies write permissions for config and telemetry directories."""
        config_dir = settings.config_dir
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            test_file = config_dir / ".doctor_write_test"
            test_file.write_text("ok")
            test_file.unlink()
            return DoctorCheck(
                category="Storage",
                name="Config Directory",
                status="PASS",
                message=f"Read/write access verified: {config_dir}",
            )
        except Exception as e:
            return DoctorCheck(
                category="Storage",
                name="Config Directory",
                status="FAIL",
                message=f"Failed write access to {config_dir}: {e}",
                remedy=f"Check folder permissions: {config_dir}",
            )

    def run_all(self) -> List[DoctorCheck]:
        """Runs the complete diagnostic suite."""
        results: List[DoctorCheck] = []
        results.append(self.check_python_environment())
        results.append(self.check_guardrails_safety())
        results.append(self.check_display_backend())
        results.append(self.check_audio_subsystem())
        results.append(self.check_storage_permissions())
        results.extend(self.check_multimedia_binaries())
        return results

    def render_table(self) -> Table:
        """Creates a formatted Rich table containing diagnosis results."""
        table = Table(
            title="🐾 Firefly Mini — System Self-Diagnosis & Readiness Report",
            header_style="bold #00F0FF",
            border_style="#BD93F9",
        )
        table.add_column("Category", style="bold white", width=14)
        table.add_column("Component", style="#50FA7B", width=22)
        table.add_column("Status", justify="center", width=8)
        table.add_column("Details", style="dim white")
        table.add_column("Recommended Remedy", style="#FFB86C")

        checks = self.run_all()
        for c in checks:
            status_style = {
                "PASS": "[bold green] PASS [/]",
                "WARN": "[bold yellow] WARN [/]",
                "FAIL": "[bold red] FAIL [/]",
            }.get(c.status, c.status)

            table.add_row(
                c.category,
                c.name,
                status_style,
                c.message,
                c.remedy or "-",
            )
        return table
