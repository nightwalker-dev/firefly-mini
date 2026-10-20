"""Desktop environment integration: terminal configurations, prompts, and notifications."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from firefly.core.config import settings
from firefly.ui.themes import CyberTheme, theme_manager


class DesktopIntegrationManager:
    """Exports shell prompts, terminal configs, Fastfetch presets, and sends desktop notifications."""

    def __init__(self, theme: Optional[CyberTheme] = None):
        self.theme = theme or theme_manager.current

    # -------------------------------------------------------------------------
    # Feature 64: Terminal Config Exporters (Kitty, Alacritty, WezTerm, Ghostty, Foot)
    # -------------------------------------------------------------------------
    def export_wezterm_theme(
        self, out_path: Optional[Path] = None, theme: Optional[CyberTheme] = None
    ) -> Path:
        """Generates WezTerm color scheme configuration."""
        t = theme or self.theme
        out = out_path or (settings.config_dir / "firefly_wezterm.lua")
        out.parent.mkdir(parents=True, exist_ok=True)

        content = f"""-- Firefly Mini Cyberpunk WezTerm Color Scheme
local wezterm = require 'wezterm'
return {{
  colors = {{
    foreground = '{t.fg_text}',
    background = '{t.bg_dark}',
    cursor_bg = '{t.neon_primary}',
    cursor_fg = '{t.bg_dark}',
    cursor_border = '{t.neon_primary}',
    selection_fg = '{t.fg_text}',
    selection_bg = '{t.border_color}',
    ansi = {{
      '{t.bg_panel}',
      '{t.danger_red}',
      '{t.success_green}',
      '{t.accent_amber}',
      '{t.neon_secondary}',
      '#FF79C6',
      '{t.neon_primary}',
      '{t.fg_text}',
    }},
    brights = {{
      '{t.dim_text}',
      '#FF6E6E',
      '#69FF94',
      '#FFFFA5',
      '#D6ACFF',
      '#FF92DF',
      '#A4FFFF',
      '#FFFFFF',
    }},
  }},
}}
"""
        out.write_text(content, encoding="utf-8")
        return out

    def export_ghostty_theme(
        self, out_path: Optional[Path] = None, theme: Optional[CyberTheme] = None
    ) -> Path:
        """Generates Ghostty terminal theme config."""
        t = theme or self.theme
        out = out_path or (settings.config_dir / "firefly_ghostty.config")
        out.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# Firefly Mini Cyber-Theme for Ghostty
background = {t.bg_dark}
foreground = {t.fg_text}
cursor-color = {t.neon_primary}
selection-background = {t.border_color}
selection-foreground = {t.fg_text}
palette = 0={t.bg_panel}
palette = 1={t.danger_red}
palette = 2={t.success_green}
palette = 3={t.accent_amber}
palette = 4={t.neon_secondary}
palette = 5=#FF79C6
palette = 6={t.neon_primary}
palette = 7={t.fg_text}
"""
        out.write_text(content, encoding="utf-8")
        return out

    def export_foot_theme(
        self, out_path: Optional[Path] = None, theme: Optional[CyberTheme] = None
    ) -> Path:
        """Generates Foot Wayland terminal ini config."""
        t = theme or self.theme
        out = out_path or (settings.config_dir / "firefly_foot.ini")
        out.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# Firefly Mini Foot Terminal Colors
[colors]
background={t.bg_dark.lstrip("#")}
foreground={t.fg_text.lstrip("#")}
regular0={t.bg_panel.lstrip("#")}
regular1={t.danger_red.lstrip("#")}
regular2={t.success_green.lstrip("#")}
regular3={t.accent_amber.lstrip("#")}
regular4={t.neon_secondary.lstrip("#")}
regular5=ff79c6
regular6={t.neon_primary.lstrip("#")}
regular7={t.fg_text.lstrip("#")}
"""
        out.write_text(content, encoding="utf-8")
        return out

    # -------------------------------------------------------------------------
    # Feature 66: Starship Prompt & Shell Prompts
    # -------------------------------------------------------------------------
    def export_starship_preset(
        self, out_path: Optional[Path] = None, theme: Optional[CyberTheme] = None
    ) -> Path:
        """Generates anime cyber-feline Starship prompt config."""
        t = theme or self.theme
        out = out_path or (settings.config_dir / "starship.toml")
        out.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# Firefly Mini Cyberpunk Anime Starship Prompt
format = \"\"\"
[╭─(=^･ω･^=) ](bold {t.neon_secondary})\\
$username\\
$directory\\
$git_branch\\
$git_status\\
$fill\\
$cmd_duration\\
$line_break\\
[╰─❯](bold {t.neon_primary}) \"\"\"

[directory]
style = "bold {t.neon_primary}"
truncation_length = 3
truncate_to_repo = true

[git_branch]
symbol = " "
style = "bold {t.accent_amber}"

[git_status]
style = "bold {t.danger_red}"

[cmd_duration]
min_time = 500
style = "bold {t.dim_text}"
"""
        out.write_text(content, encoding="utf-8")
        return out

    # -------------------------------------------------------------------------
    # Feature 67: Desktop Notification Dispatcher (notify-send / D-Bus)
    # -------------------------------------------------------------------------
    def send_notification(
        self,
        title: str,
        message: str,
        urgency: str = "normal",  # low, normal, critical
        play_sound: bool = True,
    ) -> bool:
        import sys

        if sys.platform == "win32":
            try:
                from firefly.core.platform import hidden_window_kwargs

                clean_msg = message.replace("'", "''")
                clean_title = title.replace("'", "''")
                ps_script = (
                    "[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null; "
                    "[reflection.assembly]::loadwithpartialname('System.Drawing') | Out-Null; "
                    "$notify = New-Object System.Windows.Forms.NotifyIcon; "
                    "$notify.Icon = [System.Drawing.SystemIcons]::Information; "
                    "$notify.Visible = $true; "
                    f"$notify.ShowBalloonTip(5000, '🐾 {clean_title}', '{clean_msg}', [System.Windows.Forms.ToolTipIcon]::Info)"
                )
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **hidden_window_kwargs(),
                )
            except Exception:
                pass
        elif shutil.which("notify-send"):
            try:
                subprocess.run(
                    [
                        "notify-send",
                        "-a",
                        "Firefly Mini",
                        "-u",
                        urgency,
                        f"🐾 {title}",
                        message,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

        if play_sound:
            try:
                from firefly.voice.speaker import speaker

                sound_map = {
                    "low": "purr",
                    "normal": "chirp",
                    "critical": "alert",
                }
                snd = sound_map.get(urgency, "chirp")
                wav = speaker.generate_sound(snd)
                if wav:
                    speaker._play_wav(wav)
            except Exception:
                pass

        return True


desktop_manager = DesktopIntegrationManager()
