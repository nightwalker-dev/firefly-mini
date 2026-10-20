"""Backward-compatibility shim for input_control.vision_ground -> firefly.input.vision_ground."""

from __future__ import annotations

from firefly.input.vision_ground import *  # noqa: F401, F403
from firefly.input.vision_ground import VisionGrounder

__all__ = ["VisionGrounder"]
