"""Cyberpunk Desktop Theming Engine for Firefly Mini.

Features:
- Dynamic wallpaper generation (Procedural Cyber-Cat Obsidian/Neon artwork).
- Wallpaper setting across Wayland (swaybg, hyprpaper) and X11 (feh, gsettings).
- Custom Cyberpunk Tokyo-Night / Catppuccin config generators for:
  - Kitty terminal
  - Alacritty terminal
  - Fastfetch / Neofetch
  - Bash and Zsh cyber-feline prompt themes.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw

from firefly.core.config import settings

# Color palette: Dark Obsidian, Neon Violet, Electric Cyan, Flame Amber
PALETTE = {
    "bg_dark": "#0B0A10",
    "bg_panel": "#14121F",
    "fg_text": "#E0DEF4",
    "neon_violet": "#BD93F9",
    "electric_cyan": "#00F0FF",
    "flame_amber": "#FFB86C",
    "danger_red": "#FF5555",
    "glow_purple": "#7D5BA6",
}


class DesktopThemer:
    """Manages wallpapers, terminal configs, and system desktop aesthetics."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or settings.config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.session_type = os.environ.get("XDG_SESSION_TYPE", "wayland").lower()

    # ---------------------------------------------------- Wallpaper Generation
    def generate_cyber_cat_wallpaper(
        self,
        output_path: Optional[Path] = None,
        width: int = 2560,
        height: int = 1440,
        theme: Optional[Any] = None,
    ) -> Path:
        """Generates a high-res procedural dark cyberpunk cyber-cat wallpaper."""
        from firefly.ui.themes import CyberTheme, theme_manager

        t: CyberTheme = theme if isinstance(theme, CyberTheme) else theme_manager.current
        pal = {
            "bg_dark": t.bg_dark,
            "neon_violet": t.neon_secondary,
            "electric_cyan": t.neon_primary,
            "flame_amber": t.accent_amber,
        }

        if not output_path:
            output_path = settings.data_dir / "cyber_cat_wallpaper.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)

        img = Image.new("RGB", (width, height), color=pal["bg_dark"])
        draw = ImageDraw.Draw(img)

        # 1. Subtle cyberpunk grid in background
        grid_color = "#181428"
        grid_size = 80
        for x in range(0, width, grid_size):
            draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
        for y in range(0, height, grid_size):
            draw.line([(y, 0), (width, y)], fill=grid_color, width=1)

        # 2. Isometric perspective grid lines toward horizon
        cx, cy = width // 2, height // 2
        for offset in range(-width // 2, width // 2, 120):
            draw.line([(cx + offset, height), (cx, cy + 180)], fill="#221B38", width=1)

        # 3. Holographic Cyber-Cat Silhouette (Polygonal cyber feline mask)
        scale = min(width, height) / 1080.0
        head_y = int(cy - 60 * scale)

        # Head geometric vertices
        ear_l_tip = (int(cx - 160 * scale), int(head_y - 280 * scale))
        ear_r_tip = (int(cx + 160 * scale), int(head_y - 280 * scale))
        crown = (cx, int(head_y - 120 * scale))
        cheek_l = (int(cx - 210 * scale), int(head_y + 80 * scale))
        cheek_r = (int(cx + 210 * scale), int(head_y + 80 * scale))
        chin = (cx, int(head_y + 240 * scale))
        ear_l_base = (int(cx - 90 * scale), int(head_y - 140 * scale))
        ear_r_base = (int(cx + 90 * scale), int(head_y - 140 * scale))

        # Cyber-cat outline polys
        draw.polygon(
            [ear_l_base, ear_l_tip, cheek_l, chin, cheek_r, ear_r_tip, ear_r_base, crown],
            fill="#131024",
            outline=pal["neon_violet"],
            width=max(2, int(3 * scale)),
        )

        # Inner ear neon plates
        draw.polygon(
            [
                (ear_l_base[0] - 15, ear_l_base[1] - 20),
                ear_l_tip,
                (cheek_l[0] + 30, cheek_l[1] - 40),
            ],
            fill="#1D153B",
            outline=pal["electric_cyan"],
            width=max(1, int(2 * scale)),
        )
        draw.polygon(
            [
                (ear_r_base[0] + 15, ear_r_base[1] - 20),
                ear_r_tip,
                (cheek_r[0] - 30, cheek_r[1] - 40),
            ],
            fill="#1D153B",
            outline=pal["electric_cyan"],
            width=max(1, int(2 * scale)),
        )

        # 4. Glowing Cyber Eyes (angular visor cuts)
        eye_y = int(head_y + 10 * scale)
        eye_l = [
            (int(cx - 130 * scale), eye_y),
            (int(cx - 50 * scale), int(eye_y + 25 * scale)),
            (int(cx - 65 * scale), int(eye_y + 40 * scale)),
            (int(cx - 140 * scale), int(eye_y + 15 * scale)),
        ]
        eye_r = [
            (int(cx + 130 * scale), eye_y),
            (int(cx + 50 * scale), int(eye_y + 25 * scale)),
            (int(cx + 65 * scale), int(eye_y + 40 * scale)),
            (int(cx + 140 * scale), int(eye_y + 15 * scale)),
        ]
        draw.polygon(eye_l, fill=pal["electric_cyan"], outline="#FFFFFF", width=1)
        draw.polygon(eye_r, fill=pal["electric_cyan"], outline="#FFFFFF", width=1)

        # 5. Holographic Whisker Laser Lines
        for angle in (-12, 0, 14):
            dx = int(220 * scale)
            dy = int(dx * math.tan(math.radians(angle)))
            # Left whiskers
            draw.line(
                [
                    (int(cx - 90 * scale), int(head_y + 110 * scale) + angle * 3),
                    (int(cx - 90 * scale) - dx, int(head_y + 110 * scale) + dy),
                ],
                fill=pal["flame_amber"],
                width=max(2, int(2 * scale)),
            )
            # Right whiskers
            draw.line(
                [
                    (int(cx + 90 * scale), int(head_y + 110 * scale) + angle * 3),
                    (int(cx + 90 * scale) + dx, int(head_y + 110 * scale) + dy),
                ],
                fill=pal["flame_amber"],
                width=max(2, int(2 * scale)),
            )

        # 6. Cyber Crest / Forehead Emblem
        crest = [
            (cx, int(head_y - 70 * scale)),
            (int(cx + 35 * scale), int(head_y - 30 * scale)),
            (cx, int(head_y + 10 * scale)),
            (int(cx - 35 * scale), int(head_y - 30 * scale)),
        ]
        draw.polygon(crest, fill=pal["flame_amber"], outline="#FFFFFF", width=2)

        img.save(str(output_path), "PNG")
        return output_path

    def set_wallpaper(self, wallpaper_path: Path) -> bool:
        """Applies the wallpaper using the appropriate display daemon."""
        if not wallpaper_path.exists():
            return False

        wall_str = str(wallpaper_path.resolve())

        # 0. Windows Desktop (SystemParametersInfoW)
        import sys

        if sys.platform == "win32":
            try:
                import ctypes

                # SPI_SETDESKWALLPAPER = 20, SPIF_UPDATEINIFILE = 0x01, SPIF_SENDCHANGE = 0x02
                res = ctypes.windll.user32.SystemParametersInfoW(20, 0, wall_str, 0x01 | 0x02)
                return bool(res)
            except Exception:
                pass

        # 1. swaybg (Wayland Sway/Wayfire)
        if shutil.which("swaybg"):
            try:
                subprocess.run(
                    ["pkill", "-x", "swaybg"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                subprocess.Popen(
                    ["swaybg", "-i", wall_str, "-m", "fill"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                pass

        # 2. feh (X11 / i3 / bspwm)
        if shutil.which("feh"):
            res = subprocess.run(["feh", "--bg-fill", wall_str], capture_output=True)
            if res.returncode == 0:
                return True

        # 3. GNOME / Cinnamon (gsettings)
        if shutil.which("gsettings"):
            uri = f"file://{wall_str}"
            r1 = subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
                capture_output=True,
            )
            r2 = subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
                capture_output=True,
            )
            if r1.returncode == 0 or r2.returncode == 0:
                return True

        # 4. hyprpaper (Hyprland)
        if shutil.which("hyprctl"):
            subprocess.run(["hyprctl", "hyprpaper", "preload", wall_str], capture_output=True)
            res = subprocess.run(
                ["hyprctl", "hyprpaper", "wallpaper", f",{wall_str}"], capture_output=True
            )
            if res.returncode == 0:
                return True

        # 5. KDE Plasma
        if shutil.which("plasma-apply-wallpaperimage"):
            res = subprocess.run(["plasma-apply-wallpaperimage", wall_str], capture_output=True)
            if res.returncode == 0:
                return True

        return False

    # ------------------------------------------------ Terminal Theme Configs
    def export_kitty_theme(self, out_path: Optional[Path] = None) -> Path:
        """Generates Cyberpunk Tokyo-Night config for Kitty terminal."""
        out = out_path or (Path.home() / ".config" / "kitty" / "firefly_cyberpunk.conf")
        out.parent.mkdir(parents=True, exist_ok=True)

        conf = f"""# Firefly Mini Cyberpunk Anime Theme
background {PALETTE["bg_dark"]}
foreground {PALETTE["fg_text"]}
selection_background #3E2F5B
selection_foreground #FFFFFF

cursor {PALETTE["electric_cyan"]}
cursor_text_color {PALETTE["bg_dark"]}

# Normal Colors
color0  #1A1726
color1  #FF5555
color2  #50FA7B
color3  {PALETTE["flame_amber"]}
color4  {PALETTE["neon_violet"]}
color5  #FF79C6
color6  {PALETTE["electric_cyan"]}
color7  #E0DEF4

# Bright Colors
color8  #393552
color9  #FF6E6E
color10 #69FF94
color11 #FFFFA5
color12 #D6ACFF
color13 #FF92DF
color14 #A4FFFF
color15 #FFFFFF
"""
        out.write_text(conf)
        return out

    def export_alacritty_theme(self, out_path: Optional[Path] = None) -> Path:
        """Generates Cyberpunk Tokyo-Night config for Alacritty."""
        out = out_path or (Path.home() / ".config" / "alacritty" / "firefly_cyberpunk.toml")
        out.parent.mkdir(parents=True, exist_ok=True)

        conf = f"""# Firefly Mini Cyberpunk Theme for Alacritty
[colors.primary]
background = "{PALETTE["bg_dark"]}"
foreground = "{PALETTE["fg_text"]}"

[colors.cursor]
text = "{PALETTE["bg_dark"]}"
cursor = "{PALETTE["electric_cyan"]}"

[colors.normal]
black   = "#1A1726"
red     = "#FF5555"
green   = "#50FA7B"
yellow  = "{PALETTE["flame_amber"]}"
blue    = "{PALETTE["neon_violet"]}"
magenta = "#FF79C6"
cyan    = "{PALETTE["electric_cyan"]}"
white   = "#E0DEF4"

[colors.bright]
black   = "#393552"
red     = "#FF6E6E"
green   = "#69FF94"
yellow  = "#FFFFA5"
blue    = "#D6ACFF"
magenta = "#FF92DF"
cyan    = "#A4FFFF"
white   = "#FFFFFF"
"""
        out.write_text(conf)
        return out

    def export_fastfetch_config(self, out_path: Optional[Path] = None) -> Path:
        """Generates custom Fastfetch cyberpunk cat ASCII config."""
        out = out_path or (Path.home() / ".config" / "fastfetch" / "config.jsonc")
        out.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "$schema": "https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json",
            "logo": {
                "type": "builtin",
                "source": "arch",
                "color": {"1": "magenta", "2": "cyan"},
            },
            "display": {
                "separator": " 󰄾 ",
                "color": {"keys": "magenta", "title": "cyan"},
            },
            "modules": [
                "title",
                "separator",
                {"type": "os", "key": "󰌽 OS"},
                {"type": "kernel", "key": "󰒋 Kernel"},
                {"type": "wm", "key": "󱂬 Session"},
                {"type": "terminal", "key": "󰞷 Shell"},
                {"type": "cpu", "key": "󰻠 CPU"},
                {"type": "memory", "key": "󰍛 Memory"},
                {"type": "uptime", "key": "󰅐 Uptime"},
                "colors",
            ],
        }
        out.write_text(json.dumps(data, indent=2))
        return out

    def export_shell_prompt(self, out_path: Optional[Path] = None) -> Path:
        """Generates cyber-feline terminal PS1 prompt helper."""
        out = out_path or (settings.config_dir / "firefly_prompt.sh")
        conf = r"""# Firefly Mini Cyber-Cat Terminal Prompt
# Source this file in your ~/.bashrc or ~/.zshrc
FIREFLY_CAT="(=^･ω･^=)"
export PS1="\[\033[38;5;141m\]$FIREFLY_CAT \[\033[38;5;51m\]\w \[\033[38;5;215m\]❯\[\033[00m\] "
"""
        out.write_text(conf)
        return out

    def export_wezterm_theme(self, out_path: Optional[Path] = None) -> Path:
        from firefly.ui.desktop import desktop_manager

        return desktop_manager.export_wezterm_theme(out_path=out_path)

    def export_ghostty_theme(self, out_path: Optional[Path] = None) -> Path:
        from firefly.ui.desktop import desktop_manager

        return desktop_manager.export_ghostty_theme(out_path=out_path)

    def export_foot_theme(self, out_path: Optional[Path] = None) -> Path:
        from firefly.ui.desktop import desktop_manager

        return desktop_manager.export_foot_theme(out_path=out_path)

    def export_starship_preset(self, out_path: Optional[Path] = None) -> Path:
        from firefly.ui.desktop import desktop_manager

        return desktop_manager.export_starship_preset(out_path=out_path)


themer = DesktopThemer()
