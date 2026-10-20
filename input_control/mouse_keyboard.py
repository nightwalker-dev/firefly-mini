"""Backward-compatibility shim for input_control.mouse_keyboard -> firefly.input.mouse_keyboard."""

from __future__ import annotations

from firefly.input.mouse_keyboard import *  # noqa: F401, F403
from firefly.input.mouse_keyboard import InputController

__all__ = ["InputController"]
