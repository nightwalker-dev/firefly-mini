"""Backward-compatibility shim for voice.listener -> firefly.voice.listener."""

from __future__ import annotations

from firefly.voice.listener import *  # noqa: F401, F403
from firefly.voice.listener import VoiceListener

__all__ = ["VoiceListener"]
