"""Cyberpunk Holographic Theme Engine and A11y Contrast Verifier for Firefly Mini."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class CyberTheme:
    """Cyberpunk color scheme definitions with primary and accent tones."""

    name: str
    display_name: str
    bg_dark: str
    bg_panel: str
    fg_text: str
    neon_primary: str  # Main brand/highlight tone (e.g. electric cyan)
    neon_secondary: str  # Complementary tone (e.g. neon violet)
    accent_amber: str  # Warm accent / status indicator
    success_green: str
    danger_red: str
    dim_text: str
    border_color: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "bg_dark": self.bg_dark,
            "bg_panel": self.bg_panel,
            "fg_text": self.fg_text,
            "neon_primary": self.neon_primary,
            "neon_secondary": self.neon_secondary,
            "accent_amber": self.accent_amber,
            "success_green": self.success_green,
            "danger_red": self.danger_red,
            "dim_text": self.dim_text,
            "border_color": self.border_color,
        }


# Preset Cyberpunk Palettes
THEMES: Dict[str, CyberTheme] = {
    "tokyo-night": CyberTheme(
        name="tokyo-night",
        display_name="Tokyo Night Neon",
        bg_dark="#0B0A10",
        bg_panel="#14121F",
        fg_text="#E0DEF4",
        neon_primary="#00F0FF",  # Electric Cyan
        neon_secondary="#BD93F9",  # Neon Violet
        accent_amber="#FFB86C",  # Flame Amber
        success_green="#50FA7B",  # Neon Mint
        danger_red="#FF5555",
        dim_text="#6E6A86",
        border_color="#3E2F5B",
    ),
    "catppuccin-mocha": CyberTheme(
        name="catppuccin-mocha",
        display_name="Catppuccin Mocha Feline",
        bg_dark="#1E1E2E",
        bg_panel="#181825",
        fg_text="#CDD6F4",
        neon_primary="#89DCEB",  # Sky
        neon_secondary="#CBA6F7",  # Mauve
        accent_amber="#FAB387",  # Peach
        success_green="#A6E3A1",  # Green
        danger_red="#F38BA8",  # Red
        dim_text="#6C7086",  # Overlay0
        border_color="#45475A",
    ),
    "cyber-matrix": CyberTheme(
        name="cyber-matrix",
        display_name="Matrix Cyber-Green",
        bg_dark="#080C08",
        bg_panel="#0F1810",
        fg_text="#D2FCD2",
        neon_primary="#00FF66",  # Phosphor Green
        neon_secondary="#00E5FF",  # Neon Cyan
        accent_amber="#FFD700",  # Amber Glow
        success_green="#00FF66",
        danger_red="#FF2255",
        dim_text="#3B6E47",
        border_color="#03451A",
    ),
    "synthwave-84": CyberTheme(
        name="synthwave-84",
        display_name="Synthwave '84 Sunset",
        bg_dark="#1A102F",
        bg_panel="#261B4E",
        fg_text="#FFF5F5",
        neon_primary="#00F0FF",  # Rad Cyan
        neon_secondary="#FF007F",  # Laser Pink
        accent_amber="#FFE600",  # Neon Sunset
        success_green="#72F1B8",
        danger_red="#FE4450",
        dim_text="#848BBD",
        border_color="#614D85",
    ),
    "dracula-dark": CyberTheme(
        name="dracula-dark",
        display_name="Dracula Cyber-Vampire",
        bg_dark="#282A36",
        bg_panel="#21222C",
        fg_text="#F8F8F2",
        neon_primary="#8BE9FD",  # Cyan
        neon_secondary="#BD93F9",  # Purple
        accent_amber="#FFB86C",  # Orange
        success_green="#50FA7B",  # Green
        danger_red="#FF5555",
        dim_text="#6272A4",  # Comment
        border_color="#44475A",
    ),
}

DEFAULT_THEME_NAME = "tokyo-night"


class ContrastVerifier:
    """WCAG 2.1 Color Contrast and A11y Ratio Validator."""

    @staticmethod
    def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
        clean = hex_code.lstrip("#")
        if len(clean) == 3:
            clean = "".join(c * 2 for c in clean)
        return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)

    @staticmethod
    def relative_luminance(hex_code: str) -> float:
        """Calculates relative luminance according to WCAG 2.1 specs."""
        r, g, b = ContrastVerifier.hex_to_rgb(hex_code)
        channels = []
        for v in (r, g, b):
            v_norm = v / 255.0
            if v_norm <= 0.03928:
                channels.append(v_norm / 12.92)
            else:
                channels.append(((v_norm + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    @classmethod
    def calculate_contrast_ratio(cls, fg_hex: str, bg_hex: str) -> float:
        """Computes contrast ratio between two hex colors: (L1 + 0.05) / (L2 + 0.05)."""
        l1 = cls.relative_luminance(fg_hex)
        l2 = cls.relative_luminance(bg_hex)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def meets_wcag_aa(cls, fg_hex: str, bg_hex: str, large_text: bool = False) -> bool:
        """Checks if contrast ratio meets WCAG AA (4.5:1 normal, 3:1 large)."""
        ratio = cls.calculate_contrast_ratio(fg_hex, bg_hex)
        threshold = 3.0 if large_text else 4.5
        return ratio >= threshold

    @staticmethod
    def is_no_color_active() -> bool:
        """Checks if the user environment specifies NO_COLOR or non-interactive terminal."""
        if os.environ.get("NO_COLOR"):
            return True
        term = os.environ.get("TERM", "").lower()
        return term in ("dumb", "linux", "")


class ThemeManager:
    """Manages active theme state and runtime color adjustments."""

    def __init__(self, default_theme: str = DEFAULT_THEME_NAME):
        self._current_theme_name = default_theme if default_theme in THEMES else DEFAULT_THEME_NAME

    @property
    def current(self) -> CyberTheme:
        return THEMES[self._current_theme_name]

    def set_theme(self, name: str) -> bool:
        if name in THEMES:
            self._current_theme_name = name
            return True
        return False

    def list_themes(self) -> List[CyberTheme]:
        return list(THEMES.values())

    def get_theme_names(self) -> List[str]:
        return list(THEMES.keys())

    def verify_all_themes_a11y(self) -> Dict[str, bool]:
        """Validates that all themes pass WCAG contrast between fg_text and bg_dark."""
        results: Dict[str, bool] = {}
        for name, theme in THEMES.items():
            results[name] = ContrastVerifier.meets_wcag_aa(theme.fg_text, theme.bg_dark)
        return results

    def format_markup(self, text: str, role: str) -> str:
        """Wraps text in theme-specific Rich markup or plain text if NO_COLOR."""
        if ContrastVerifier.is_no_color_active():
            # Strip any markup brackets if dumb terminal
            return re.sub(r"\[/?.*?\]", "", text)

        theme = self.current
        color_map = {
            "primary": theme.neon_primary,
            "secondary": theme.neon_secondary,
            "amber": theme.accent_amber,
            "success": theme.success_green,
            "danger": theme.danger_red,
            "text": theme.fg_text,
            "dim": theme.dim_text,
        }
        color = color_map.get(role, theme.neon_primary)
        return f"[{color}]{text}[/]"


theme_manager = ThemeManager()
