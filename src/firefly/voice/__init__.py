"""Firefly Mini Voice & Audio Subsystem."""

from __future__ import annotations

from firefly.voice.events import AudioEventSubscriber, audio_events
from firefly.voice.listener import VoiceListener, listener
from firefly.voice.speaker import CyberSpeaker, speaker
from firefly.voice.synthesizer import ProceduralAudioSynthesizer, sound_synthesizer
from firefly.voice.vad import VoiceActivityDetector, vad
from firefly.voice.wake_word import WakeWordMatcher, wake_matcher

__all__ = [
    "AudioEventSubscriber",
    "CyberSpeaker",
    "ProceduralAudioSynthesizer",
    "VoiceActivityDetector",
    "VoiceListener",
    "WakeWordMatcher",
    "audio_events",
    "listener",
    "sound_synthesizer",
    "speaker",
    "vad",
    "wake_matcher",
]
