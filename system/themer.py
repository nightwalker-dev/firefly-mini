"""Backward-compatibility shim for system.themer -> firefly.system.themer."""

from __future__ import annotations

from firefly.system.themer import *  # noqa: F401, F403
from firefly.system.themer import PALETTE, DesktopThemer, themer

__all__ = ["DesktopThemer", "themer", "PALETTE"]
