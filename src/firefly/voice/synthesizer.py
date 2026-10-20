"""Procedural Mathematical Soundbite Synthesizer for Cyber-Cat Familiar Audio FX.

Synthesizes pure mathematical waveforms on the fly using standard library `wave`
and `math`. Requires zero external audio assets.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path
from typing import List, Optional

from firefly.core.config import settings

SAMPLE_RATE = 22050


class ProceduralAudioSynthesizer:
    """Generates procedural feline and cyberpunk soundbites."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.sounds_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(self, sound_type: str, force_regenerate: bool = False) -> Path:
        """Synthesizes or returns a cached procedural WAV soundbite."""
        out_path = self.output_dir / f"{sound_type}.wav"
        if out_path.exists() and not force_regenerate and out_path.stat().st_size > 500:
            return out_path

        samples: List[int] = []

        if sound_type == "chirp":
            samples = self._gen_chirp()
        elif sound_type == "purr":
            samples = self._gen_purr()
        elif sound_type == "alert":
            samples = self._gen_alert()
        elif sound_type == "beep":
            samples = self._gen_beep()
        elif sound_type == "hiss":
            samples = self._gen_hiss()
        elif sound_type == "meow":
            samples = self._gen_meow()
        elif sound_type in ("fanfare", "success"):
            samples = self._gen_fanfare()
        elif sound_type == "glitch":
            samples = self._gen_glitch()
        else:
            samples = self._gen_beep()

        self._write_wav(out_path, samples)
        return out_path

    def _write_wav(self, path: Path, samples: List[int]) -> None:
        """Encodes 16-bit mono signed integer samples into standard WAV format."""
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            raw = struct.pack(f"<{len(samples)}h", *samples)
            wf.writeframes(raw)

    def _gen_chirp(self) -> List[int]:
        """Rising frequency feline chirp (600Hz -> 1800Hz)."""
        duration = 0.25
        n_samples = int(SAMPLE_RATE * duration)
        samples = []
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            f = 600 + (1200 * (t / duration) ** 2)
            val = 0.5 * math.sin(2 * math.pi * f * t)
            val *= math.sin(math.pi * t / duration)  # Envelope
            samples.append(int(val * 32767))
        return samples

    def _gen_purr(self) -> List[int]:
        """Low rumbling harmonic purr with 25Hz flutter."""
        duration = 0.7
        n_samples = int(SAMPLE_RATE * duration)
        samples = []
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            flutter = 0.5 + 0.5 * math.sin(2 * math.pi * 25 * t)
            carrier = math.sin(2 * math.pi * 85 * t) + 0.4 * math.sin(2 * math.pi * 170 * t)
            val = 0.4 * carrier * flutter
            samples.append(int(val * 32767))
        return samples

    def _gen_alert(self) -> List[int]:
        """Dual-tone cybersecurity warning chime (1200Hz + 1600Hz exponential decay)."""
        duration = 0.35
        n_samples = int(SAMPLE_RATE * duration)
        samples = []
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            env = math.exp(-6 * t)
            val = 0.35 * (math.sin(2 * math.pi * 1200 * t) + math.sin(2 * math.pi * 1600 * t)) * env
            samples.append(int(val * 32767))
        return samples

    def _gen_beep(self) -> List[int]:
        """Short status pulse (950Hz)."""
        duration = 0.12
        n_samples = int(SAMPLE_RATE * duration)
        samples = []
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            env = math.sin(math.pi * t / duration)
            val = 0.3 * math.sin(2 * math.pi * 950 * t) * env
            samples.append(int(val * 32767))
        return samples

    def _gen_hiss(self) -> List[int]:
        """Defensive cyber-cat hiss (filtered high-frequency shaped noise)."""
        duration = 0.4
        n_samples = int(SAMPLE_RATE * duration)
        samples = []
        prev = 0.0
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            # High-pass filtered noise
            noise = random.uniform(-1.0, 1.0)
            high_passed = noise - prev
            prev = noise
            # Attack-decay envelope
            env = math.sin(math.pi * (t / duration) ** 0.7)
            val = 0.25 * high_passed * env
            samples.append(int(max(-1.0, min(1.0, val)) * 32767))
        return samples

    def _gen_meow(self) -> List[int]:
        """Vocalized feline meow with rising and falling pitch inflection."""
        duration = 0.45
        n_samples = int(SAMPLE_RATE * duration)
        samples = []
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            norm_t = t / duration
            # Pitch contour: 650Hz rising to 950Hz then dropping to 550Hz
            f = 650 + 300 * math.sin(math.pi * norm_t)
            carrier = math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t)
            env = math.sin(math.pi * norm_t)
            val = 0.4 * carrier * env
            samples.append(int(val * 32767))
        return samples

    def _gen_fanfare(self) -> List[int]:
        """Ascending cyber arpeggio for task resolution and self-healing (C5-E5-G5-C6)."""
        duration_per_note = 0.1
        freqs = [523.25, 659.25, 783.99, 1046.50]  # C5, E5, G5, C6
        samples = []
        for f in freqs:
            n_note = int(SAMPLE_RATE * duration_per_note)
            for i in range(n_note):
                t = i / SAMPLE_RATE
                env = math.sin(math.pi * t / duration_per_note)
                val = 0.35 * math.sin(2 * math.pi * f * t) * env
                samples.append(int(val * 32767))
        return samples

    def _gen_glitch(self) -> List[int]:
        """Bitcrush frequency modulated glitch sound."""
        duration = 0.2
        n_samples = int(SAMPLE_RATE * duration)
        samples = []
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            mod = math.sin(2 * math.pi * 60 * t)
            f = 1400 + 800 * mod
            val = 0.35 * math.sin(2 * math.pi * f * t)
            # 8-bit quantized crush
            quantized = round(val * 8) / 8.0
            samples.append(int(quantized * 32767))
        return samples


sound_synthesizer = ProceduralAudioSynthesizer()
