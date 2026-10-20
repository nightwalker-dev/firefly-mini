"""Cyber Feline Voice Synthesizer, Audio Dispatcher, and Secret-Scrubbed TTS Engine."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from firefly.core.config import settings
from firefly.memory.redactor import SecretRedactor
from firefly.voice.synthesizer import sound_synthesizer


class CyberSpeaker:
    """Handles feline acoustic telemetry, volume control, and speech synthesis."""

    def __init__(
        self,
        piper_bin: Optional[str] = None,
        piper_model: Optional[str] = None,
        volume: float = 1.0,
    ):
        self.piper_bin = piper_bin or settings.piper_bin
        self.piper_model = piper_model or settings.piper_model
        self.has_piper = shutil.which(self.piper_bin) is not None
        self.volume = max(0.0, min(1.0, volume))
        self.is_muted = False

        # Audio player auto-detection priority
        self.player = (
            shutil.which("pw-play")
            or shutil.which("paplay")
            or shutil.which("aplay")
            or shutil.which("ffplay")
        )

    def set_volume(self, level: float) -> None:
        """Sets output volume between 0.0 (silent) and 1.0 (max)."""
        self.volume = max(0.0, min(1.0, level))

    def set_muted(self, muted: bool = True) -> None:
        """Mutes or unmutes audio playback."""
        self.is_muted = muted

    def _play_wav(self, wav_path: Path) -> bool:
        """Dispatches WAV playback to the active system audio server."""
        if self.is_muted or self.volume <= 0.0 or not wav_path.exists():
            return False

        import sys

        if sys.platform == "win32":
            try:
                import winsound

                winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
                return True
            except Exception:
                pass

        if not self.player:
            return False

        try:
            if "pw-play" in self.player:
                vol_arg = f"--volume={self.volume}"
                subprocess.run(
                    [self.player, vol_arg, str(wav_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif "paplay" in self.player:
                vol_int = int(self.volume * 65536)
                subprocess.run(
                    [self.player, f"--volume={vol_int}", str(wav_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif "ffplay" in self.player:
                vol_int = int(self.volume * 100)
                subprocess.run(
                    [
                        self.player,
                        "-nodisp",
                        "-autoexit",
                        "-loglevel",
                        "quiet",
                        "-volume",
                        str(vol_int),
                        str(wav_path),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # aplay
                subprocess.run(
                    [self.player, str(wav_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Feature 81: Procedural Soundbite Synthesis
    # -------------------------------------------------------------------------
    def generate_sound(self, sound_type: str) -> Optional[Path]:
        """Synthesizes cyber feline audio waves on the fly."""
        try:
            return sound_synthesizer.synthesize(sound_type)
        except Exception:
            return None

    def play_sound(self, sound_type: str) -> bool:
        """Plays the synthesized sound effect."""
        wav = self.generate_sound(sound_type)
        if wav:
            return self._play_wav(wav)
        return False

    def chirp(self) -> bool:
        return self.play_sound("chirp")

    def purr(self) -> bool:
        return self.play_sound("purr")

    def alert(self) -> bool:
        return self.play_sound("alert")

    def beep(self) -> bool:
        return self.play_sound("beep")

    def hiss(self) -> bool:
        return self.play_sound("hiss")

    def meow(self) -> bool:
        return self.play_sound("meow")

    def fanfare(self) -> bool:
        return self.play_sound("fanfare")

    def glitch(self) -> bool:
        return self.play_sound("glitch")

    # -------------------------------------------------------------------------
    # Features 83 & 84: Clean & Secret-Scrubbed Text-To-Speech (TTS)
    # -------------------------------------------------------------------------
    @classmethod
    def clean_text_for_speech(cls, text: str) -> str:
        """Strips markdown code blocks, links, ANSI codes, and replaces secret tokens."""
        # 1. Scrub secrets first (Feature 84)
        sanitized = SecretRedactor.redact(text)
        sanitized = sanitized.replace("[REDACTED_API_TOKEN]", "API key hidden")
        sanitized = sanitized.replace("[REDACTED_SECRET]", "secret hidden")
        sanitized = sanitized.replace("[REDACTED_TOTP_SEED]", "TOTP seed hidden")
        sanitized = sanitized.replace("[REDACTED_SUDO_INPUT]", "credential hidden")

        # 2. Strip ANSI escape sequences
        cleaned = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", sanitized)
        # 3. Remove code blocks ```...```
        cleaned = re.sub(r"```[\s\S]*?```", "code block omitted", cleaned)
        # 4. Remove inline backticks `code`
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        # 5. Simplify markdown links [text](url) -> text (must be before bracket strip)
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        # 6. Strip URLs
        cleaned = re.sub(r"https?://\S+", "", cleaned)
        # 7. Strip Rich markup brackets (e.g. [bold cyan]...[/])
        cleaned = re.sub(r"\[/?(?:bold|dim|italic|#\w+|\w+)[^\]]*\]", "", cleaned)
        # 8. Strip bold/italics
        cleaned = cleaned.replace("**", "").replace("*", "")
        # 9. Strip markdown headers (#, ##) and list bullets
        cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^[-•]\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.replace("#", "")

        # 10. Collapse whitespace
        return " ".join(cleaned.split()).strip()

    def speak(self, text: str) -> bool:
        """Speaks sanitized text via Piper TTS or fallback speech engines."""
        if self.is_muted or self.volume <= 0.0:
            return False

        spoken_text = self.clean_text_for_speech(text)
        if not spoken_text:
            return False

        # 1. Piper TTS
        if self.has_piper and self.piper_model and Path(self.piper_model).exists():
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_wav = Path(f.name)
            try:
                cmd = [
                    self.piper_bin,
                    "--model",
                    self.piper_model,
                    "--output_file",
                    str(tmp_wav),
                ]
                proc = subprocess.run(cmd, input=spoken_text.encode("utf-8"), capture_output=True)
                if proc.returncode == 0 and tmp_wav.exists():
                    self._play_wav(tmp_wav)
                    return True
            finally:
                tmp_wav.unlink(missing_ok=True)

        # 2. espeak-ng / espeak fallback (with cyber feline pitch/speed)
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            try:
                subprocess.run(
                    [espeak, "-v", "en-us", "-p", "75", "-s", "170", spoken_text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                return True
            except Exception:
                pass

        # 3. spd-say fallback
        spd_say = shutil.which("spd-say")
        if spd_say:
            try:
                subprocess.run(
                    [spd_say, "-p", "50", "-r", "10", spoken_text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                return True
            except Exception:
                pass

        # 4. Windows PowerShell SAPI fallback
        import sys

        if sys.platform == "win32":
            try:
                escaped = spoken_text.replace("'", "''")
                ps_cmd = (
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$synth.Speak('{escaped}')"
                )
                from firefly.core.platform import hidden_window_kwargs

                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    **hidden_window_kwargs(),
                )
                return True
            except Exception:
                pass

        # 5. Fallback procedural sound acknowledgement
        self.chirp()
        return True


speaker = CyberSpeaker()
