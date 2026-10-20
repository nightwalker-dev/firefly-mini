"""Speech-to-Text (STT), Wake-Word Detection, and Voice-to-Action Execution Loop."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

from firefly.core.config import settings
from firefly.voice.vad import vad
from firefly.voice.wake_word import wake_matcher

# Attempt faster_whisper import
try:
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]

    HAS_FASTER_WHISPER = True
except ImportError:
    WhisperModel = None  # type: ignore[assignment]
    HAS_FASTER_WHISPER = False


class VoiceListener:
    """Listens for voice commands, trims silence, matches wake-words, and triggers agent actions."""

    def __init__(
        self,
        wake_word: Optional[str] = None,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.wake_word = (wake_word or settings.wake_word).lower()
        self.model_name = model_name or settings.whisper_model
        self.device = device or settings.whisper_device
        self._model = None
        self.mock_transcription: Optional[str] = None

        self.recorder = (
            shutil.which("parecord") or shutil.which("arecord") or shutil.which("ffmpeg")
        )

    def _get_whisper_model(self):
        if not HAS_FASTER_WHISPER or WhisperModel is None:
            return None
        if self._model is None:
            dev = "cuda" if self.device == "cuda" else ("cpu" if self.device == "cpu" else "auto")
            compute_type = "float16" if dev == "cuda" else "int8"
            try:
                self._model = WhisperModel(self.model_name, device=dev, compute_type=compute_type)
            except Exception:
                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        return self._model

    def record_audio(
        self, duration_sec: float = 4.0, output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Records microphone input for specified duration."""
        if not self.recorder:
            return None

        if not output_path:
            fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="firefly_voice_")
            os.close(fd)
            output_path = Path(tmp)

        try:
            if "arecord" in self.recorder:
                cmd = [
                    "arecord",
                    "-d",
                    str(int(duration_sec)),
                    "-f",
                    "cd",
                    "-t",
                    "wav",
                    str(output_path),
                ]
            elif "parecord" in self.recorder:
                cmd = [
                    "timeout",
                    str(duration_sec),
                    "parecord",
                    "--file-format=wav",
                    str(output_path),
                ]
            else:
                # ffmpeg
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "pulse",
                    "-i",
                    "default",
                    "-t",
                    str(duration_sec),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(output_path),
                ]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if output_path.exists() and output_path.stat().st_size > 1000:
                # Apply VAD silence trimming before transcription (Feature 85)
                return vad.trim_silence(output_path)
        except Exception:
            pass

        return None

    def transcribe(self, audio_path: Path) -> str:
        """Transcribes a WAV file into text using Whisper or active mock."""
        if self.mock_transcription is not None:
            return self.mock_transcription

        if not audio_path.exists():
            return ""

        model = self._get_whisper_model()
        if model:
            try:
                segments, _ = model.transcribe(str(audio_path), beam_size=2, language="en")
                text = " ".join([seg.text for seg in segments]).strip()
                return text
            except Exception:
                pass

        # Fallback to local whisper CLI if installed
        whisper_cli = shutil.which("whisper")
        if whisper_cli:
            try:
                subprocess.run(
                    [whisper_cli, str(audio_path), "--model", "tiny.en", "--output_format", "txt"],
                    capture_output=True,
                    text=True,
                )
                txt_file = audio_path.with_suffix(".txt")
                if txt_file.exists():
                    txt = txt_file.read_text().strip()
                    txt_file.unlink(missing_ok=True)
                    return txt
            except Exception:
                pass

        return ""

    def listen_and_transcribe(self, duration_sec: float = 4.0) -> str:
        """Records audio and returns text transcription."""
        if self.mock_transcription is not None:
            return self.mock_transcription

        wav = self.record_audio(duration_sec=duration_sec)
        if not wav:
            return ""
        try:
            return self.transcribe(wav)
        finally:
            wav.unlink(missing_ok=True)

    def check_wake_word(self, text: str) -> Tuple[bool, str]:
        """Checks for exact or fuzzy wake word matches and returns remaining command payload."""
        matched, command, _ = wake_matcher.match(text)
        return matched, command

    # -------------------------------------------------------------------------
    # Feature 88: Voice-to-Action Execution Loop
    # -------------------------------------------------------------------------
    async def run_voice_loop(
        self,
        agent: Any,
        duration_sec: float = 4.0,
        max_iterations: Optional[int] = None,
        callback: Optional[Any] = None,
    ) -> None:
        """Runs the continuous listen-think-speak voice loop."""
        from firefly.voice.speaker import speaker

        speaker.chirp()
        iterations = 0

        while True:
            if max_iterations and iterations >= max_iterations:
                break
            iterations += 1

            # 1. Listen & Transcribe
            transcript = self.listen_and_transcribe(duration_sec=duration_sec)
            if not transcript:
                await asyncio.sleep(0.5)
                continue

            # 2. Check wake word
            triggered, command = self.check_wake_word(transcript)
            if triggered and command:
                speaker.beep()
                # 3. Dispatch to agent ReAct loop
                response = await agent.chat(command)
                # 4. Speak back sanitized response
                speaker.speak(response)
                if callback:
                    callback(command, response)

            await asyncio.sleep(0.2)


listener = VoiceListener()
