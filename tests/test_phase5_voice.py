"""Comprehensive test suite for Phase 5: Voice & Audio Subsystem (Features 81-90)."""

import wave

import pytest
from typer.testing import CliRunner

from firefly.cli import app
from firefly.core.events import Event, EventBus
from firefly.voice.events import AudioEventSubscriber
from firefly.voice.listener import VoiceListener
from firefly.voice.speaker import CyberSpeaker
from firefly.voice.synthesizer import ProceduralAudioSynthesizer
from firefly.voice.vad import VoiceActivityDetector
from firefly.voice.wake_word import WakeWordMatcher


# ==============================================================================
# Feature 81: Procedural Mathematical Sound Synthesis
# ==============================================================================
def test_procedural_sound_synthesizer(tmp_path):
    synth = ProceduralAudioSynthesizer(output_dir=tmp_path / "sounds")

    sounds = ["chirp", "purr", "alert", "beep", "hiss", "meow", "fanfare", "glitch"]
    for snd in sounds:
        wav_file = synth.synthesize(snd, force_regenerate=True)
        assert wav_file.exists()
        assert wav_file.stat().st_size > 1000

        # Validate standard 16-bit PCM WAV container
        with wave.open(str(wav_file), "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 22050
            assert wf.getnframes() > 100


# ==============================================================================
# Feature 82: Audio Player & Volume Control
# ==============================================================================
def test_speaker_volume_and_mute(tmp_path):
    spk = CyberSpeaker()
    spk.set_volume(0.5)
    assert spk.volume == 0.5

    spk.set_volume(1.5)  # Clamped to 1.0
    assert spk.volume == 1.0

    spk.set_muted(True)
    assert spk.is_muted is True
    # When muted, playback is bypassed immediately
    assert spk._play_wav(tmp_path / "nonexistent.wav") is False

    spk.set_muted(False)
    assert spk.is_muted is False


# ==============================================================================
# Features 83 & 84: Speech Formatting and Secret Scrubbing
# ==============================================================================
def test_clean_text_for_speech_secret_redaction():
    raw_text = (
        "# Cyber System Report\n"
        "Here is the result with **bold** text and `echo 'cyber'` command.\n"
        "User token is ghp_123456789012345678901234567890123456 and password is password='SuperSecret'.\n"
        "Link: [Documentation](https://example.com/doc) and code:\n"
        "```python\ndef run(): pass\n```"
    )
    cleaned = CyberSpeaker.clean_text_for_speech(raw_text)

    # 1. No secret leakage
    assert "ghp_1234567890" not in cleaned
    assert "SuperSecret" not in cleaned
    assert "API key hidden" in cleaned
    assert "secret hidden" in cleaned

    # 2. Markdown stripped for clean natural voice
    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "https://example.com" not in cleaned
    assert "Documentation" in cleaned
    assert "code block omitted" in cleaned


# ==============================================================================
# Feature 85: Voice Activity Detection (VAD) & Silence Trimming
# ==============================================================================
def test_vad_silence_detection_and_trimming(tmp_path):
    detector = VoiceActivityDetector(energy_threshold=200.0)

    # Pure silence chunk
    silence = [0] * 500
    assert detector.calculate_rms(silence) == 0.0
    assert detector.is_speech(silence) is False

    # Loud tone chunk
    loud = [2000] * 500
    assert detector.calculate_rms(loud) > 1000.0
    assert detector.is_speech(loud) is True

    # Silence trimming test with synthesized chirp
    synth = ProceduralAudioSynthesizer(output_dir=tmp_path)
    chirp_wav = synth.synthesize("chirp")
    analysis = detector.analyze_audio_file(chirp_wav)
    assert analysis["has_speech"] is True
    assert analysis["mean_rms"] > 50.0

    trimmed = detector.trim_silence(chirp_wav, output_wav=tmp_path / "chirp_trimmed.wav")
    assert trimmed.exists()
    assert trimmed.stat().st_size > 500


# ==============================================================================
# Feature 86: Speech-to-Text Transcription with Mock Mode
# ==============================================================================
def test_listener_transcription_mock(tmp_path):
    lst = VoiceListener()
    lst.mock_transcription = "firefly check system status"

    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"RIFFdummyWAVEfmt ")

    res = lst.transcribe(dummy_wav)
    assert res == "firefly check system status"

    res_live = lst.listen_and_transcribe()
    assert res_live == "firefly check system status"


# ==============================================================================
# Feature 87: Fuzzy and Phonetic Wake-Word Matching
# ==============================================================================
def test_wake_word_fuzzy_matching():
    matcher = WakeWordMatcher(wake_words=["firefly", "hey firefly", "cyber cat"])

    # 1. Exact match
    ok, cmd, conf = matcher.match("firefly open htop")
    assert ok is True
    assert cmd == "open htop"
    assert conf == 1.0

    # 2. Multi-word wake word
    ok, cmd, conf = matcher.match("hey firefly check memory usage")
    assert ok is True
    assert cmd == "check memory usage"
    assert conf == 1.0

    # 3. Fuzzy match (accents / audio artifacts: flyerfly -> firefly)
    ok, cmd, conf = matcher.match("flyerfly clean temp directory")
    assert ok is True
    assert cmd == "clean temp directory"
    assert conf >= 0.5

    # 4. Completely unrelated text (no trigger)
    ok, cmd, conf = matcher.match("echo 'just compiling python'")
    assert ok is False
    assert conf == 0.0


# ==============================================================================
# Feature 88: Voice-to-Action Execution Loop
# ==============================================================================
@pytest.mark.asyncio
async def test_voice_to_action_loop():
    lst = VoiceListener()
    lst.mock_transcription = "firefly show disk space"

    # Mock agent
    class MockAgent:
        async def chat(self, prompt: str) -> str:
            assert prompt == "show disk space"
            return "Disk space has 85GB free."

    agent = MockAgent()
    dispatched_calls = []

    def on_success(cmd, response):
        dispatched_calls.append((cmd, response))

    await lst.run_voice_loop(agent, max_iterations=1, callback=on_success)
    assert len(dispatched_calls) == 1
    assert dispatched_calls[0][0] == "show disk space"
    assert "85GB" in dispatched_calls[0][1]


# ==============================================================================
# Feature 89: Acoustic EventBus Synchronizer
# ==============================================================================
def test_acoustic_eventbus_sync():
    bus = EventBus()

    class SpySpeaker:
        def __init__(self):
            self.calls = []

        def beep(self):
            self.calls.append("beep")

        def purr(self):
            self.calls.append("purr")

        def hiss(self):
            self.calls.append("hiss")

        def alert(self):
            self.calls.append("alert")

        def fanfare(self):
            self.calls.append("fanfare")

    spy = SpySpeaker()
    sub = AudioEventSubscriber(speaker_instance=spy)  # type: ignore[arg-type]
    sub.attach(bus)

    bus.publish_sync(Event(topic="agent.turn_started"))
    assert "beep" in spy.calls

    bus.publish_sync(Event(topic="guardrail.blocked"))
    assert "hiss" in spy.calls

    bus.publish_sync(Event(topic="guardrail.mfa_prompt"))
    assert "alert" in spy.calls

    bus.publish_sync(Event(topic="healing.repaired"))
    assert "fanfare" in spy.calls

    bus.publish_sync(Event(topic="agent.turn_finished"))
    assert "purr" in spy.calls


# ==============================================================================
# Feature 90: CLI Commands for Voice Subsystem
# ==============================================================================
def test_voice_cli_subcommands():
    runner = CliRunner()

    # Test sound synthesis
    res_sfx = runner.invoke(app, ["voice", "test-sfx", "chirp"])
    assert res_sfx.exit_code == 0
    assert "Sound 'chirp'" in res_sfx.stdout

    # Test TTS with secret scrubbing
    res_tts = runner.invoke(
        app, ["voice", "test-tts", "Token is ghp_123456789012345678901234567890123456"]
    )
    assert res_tts.exit_code == 0
    assert "API key hidden" in res_tts.stdout
    assert "ghp_1234567890" not in res_tts.stdout

    # Test VAD readiness check
    res_vad = runner.invoke(app, ["voice", "vad-check"])
    assert res_vad.exit_code == 0
    assert "VAD Noise Threshold" in res_vad.stdout
