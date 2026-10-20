"""Voice Activity Detection (VAD) and Silence Trimming Engine."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Dict, List, Optional


class VoiceActivityDetector:
    """Detects human speech and eliminates leading/trailing silence from microphone recordings."""

    def __init__(self, energy_threshold: float = 280.0, frame_duration_ms: int = 30):
        self.energy_threshold = energy_threshold
        self.frame_duration_ms = frame_duration_ms

    @staticmethod
    def calculate_rms(samples: List[int]) -> float:
        """Computes Root Mean Square (RMS) amplitude energy of a sample block."""
        if not samples:
            return 0.0
        sum_squares = sum(s * s for s in samples)
        return math.sqrt(sum_squares / len(samples))

    def is_speech(self, samples: List[int], threshold: Optional[float] = None) -> bool:
        """Determines if the sample chunk contains voice activity above noise gate."""
        th = threshold if threshold is not None else self.energy_threshold
        return self.calculate_rms(samples) >= th

    def analyze_audio_file(self, wav_path: Path) -> Dict[str, float | bool]:
        """Analyzes a WAV file returning metrics on noise floor and speech activity."""
        if not wav_path.exists():
            return {"mean_rms": 0.0, "max_rms": 0.0, "has_speech": False}

        with wave.open(str(wav_path), "r") as wf:
            n_frames = wf.getnframes()
            if n_frames == 0:
                return {"mean_rms": 0.0, "max_rms": 0.0, "has_speech": False}
            raw = wf.readframes(n_frames)
            samples = list(struct.unpack(f"<{n_frames}h", raw))

        frame_size = int(wf.getframerate() * (self.frame_duration_ms / 1000.0))
        if frame_size <= 0:
            frame_size = 1

        rms_values = []
        speech_detected = False
        for i in range(0, len(samples), frame_size):
            chunk = samples[i : i + frame_size]
            rms = self.calculate_rms(chunk)
            rms_values.append(rms)
            if rms >= self.energy_threshold:
                speech_detected = True

        mean_rms = sum(rms_values) / max(1, len(rms_values))
        max_rms = max(rms_values) if rms_values else 0.0

        return {
            "mean_rms": round(mean_rms, 2),
            "max_rms": round(max_rms, 2),
            "has_speech": speech_detected,
        }

    def trim_silence(
        self,
        input_wav: Path,
        output_wav: Optional[Path] = None,
        padding_frames: int = 3,
    ) -> Path:
        """Strips leading and trailing silence from a WAV recording."""
        if not input_wav.exists():
            return input_wav

        with wave.open(str(input_wav), "r") as wf:
            params = wf.getparams()
            n_frames = wf.getnframes()
            if n_frames == 0:
                return input_wav
            raw = wf.readframes(n_frames)
            samples = list(struct.unpack(f"<{n_frames}h", raw))
            sample_rate = wf.getframerate()

        frame_size = int(sample_rate * (self.frame_duration_ms / 1000.0))
        if frame_size <= 0:
            frame_size = 1

        chunks = [samples[i : i + frame_size] for i in range(0, len(samples), frame_size)]
        speech_indices = [
            idx for idx, ch in enumerate(chunks) if self.calculate_rms(ch) >= self.energy_threshold
        ]

        if not speech_indices:
            # Entire clip is silence; leave unchanged
            return input_wav

        start_chunk = max(0, speech_indices[0] - padding_frames)
        end_chunk = min(len(chunks), speech_indices[-1] + padding_frames + 1)

        trimmed_samples = []
        for ch in chunks[start_chunk:end_chunk]:
            trimmed_samples.extend(ch)

        out_path = output_wav or input_wav.with_name(f"{input_wav.stem}_trimmed.wav")
        with wave.open(str(out_path), "w") as out_wf:
            out_wf.setparams(params)
            out_raw = struct.pack(f"<{len(trimmed_samples)}h", *trimmed_samples)
            out_wf.writeframes(out_raw)

        return out_path


vad = VoiceActivityDetector()
