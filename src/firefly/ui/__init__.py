"""Firefly Mini Visual Appeal & Cyberpunk UI Subsystem."""

from __future__ import annotations

from firefly.ui.avatar import CatAvatarAnimator, CatMood, CatMoodEngine, CatState, avatar_animator
from firefly.ui.desktop import DesktopIntegrationManager, desktop_manager
from firefly.ui.formatter import OutputFormatter, output_formatter
from firefly.ui.hud import TerminalHUD, hud
from firefly.ui.telemetry import (
    TelemetryHistory,
    render_gauge_bar,
    render_sparkline,
    telemetry_engine,
)
from firefly.ui.themes import ContrastVerifier, CyberTheme, ThemeManager, theme_manager
from firefly.ui.vision_overlay import VisionOverlayAnnotator, vision_annotator
from firefly.ui.widgets import (
    render_glitch_text,
    render_gradient_banner,
    render_neon_progress,
    render_paw_breadcrumbs,
    render_ports_table,
    render_process_tree,
    render_unified_diff,
)

__all__ = [
    "CatAvatarAnimator",
    "CatMood",
    "CatMoodEngine",
    "CatState",
    "ContrastVerifier",
    "CyberTheme",
    "DesktopIntegrationManager",
    "OutputFormatter",
    "TelemetryHistory",
    "TerminalHUD",
    "ThemeManager",
    "VisionOverlayAnnotator",
    "avatar_animator",
    "desktop_manager",
    "hud",
    "output_formatter",
    "render_gauge_bar",
    "render_glitch_text",
    "render_gradient_banner",
    "render_neon_progress",
    "render_paw_breadcrumbs",
    "render_ports_table",
    "render_process_tree",
    "render_sparkline",
    "render_unified_diff",
    "telemetry_engine",
    "theme_manager",
    "vision_annotator",
]
