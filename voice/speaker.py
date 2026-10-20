"""Backward-compatibility shim for voice.speaker -> firefly.voice.speaker."""

from __future__ import annotations

from firefly.voice.speaker import *  # noqa: F401, F403
from firefly.voice.speaker import CyberSpeaker, speaker

__all__ = ["CyberSpeaker", "speaker"]
