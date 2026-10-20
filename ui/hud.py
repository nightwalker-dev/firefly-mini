"""Backward-compatibility shim for ui.hud -> firefly.ui.hud."""

from __future__ import annotations

from firefly.ui.hud import *  # noqa: F401, F403
from firefly.ui.hud import TerminalHUD, default_hud

__all__ = ["TerminalHUD", "default_hud"]
