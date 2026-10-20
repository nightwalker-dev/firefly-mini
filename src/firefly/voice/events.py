"""Acoustic EventBus Synchronizer linking system events to cyber-feline soundbites."""

from __future__ import annotations

from typing import Optional

from firefly.core.events import Event, EventBus
from firefly.voice.speaker import CyberSpeaker, speaker


class AudioEventSubscriber:
    """Listens to EventBus topics and plays procedural soundbites for agent feedback."""

    def __init__(self, speaker_instance: Optional[CyberSpeaker] = None):
        self.speaker = speaker_instance or speaker

    def attach(self, bus: EventBus) -> None:
        """Registers acoustic event handlers to the given EventBus."""

        def on_turn_started(event: Event) -> None:
            self.speaker.beep()

        def on_turn_finished(event: Event) -> None:
            self.speaker.purr()

        def on_guardrail_blocked(event: Event) -> None:
            self.speaker.hiss()

        def on_mfa_prompt(event: Event) -> None:
            self.speaker.alert()

        def on_healing_success(event: Event) -> None:
            self.speaker.fanfare()

        bus.subscribe("agent.turn_started", on_turn_started)
        bus.subscribe("agent.turn_finished", on_turn_finished)
        bus.subscribe("guardrail.blocked", on_guardrail_blocked)
        bus.subscribe("guardrail.mfa_prompt", on_mfa_prompt)
        bus.subscribe("healing.repaired", on_healing_success)


audio_events = AudioEventSubscriber()
