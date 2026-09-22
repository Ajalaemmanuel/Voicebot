"""In-process dual-track call recording — no LiveKit Egress / cloud storage
dependency (see docs/DECISIONS.md #7).

Both the practice agent's SIP audio track and our own published TTS track are
captured independently as raw PCM16 mono frames as they arrive, then muxed
into a single stereo WAV at finalize() time: left channel = our bot (caller),
right channel = the practice's agent. A subsequent ffmpeg pass (see
convert_to_compressed) produces the OGG/MP3 required for submission.
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

_SAMPLE_WIDTH_BYTES = 2  # PCM16


class DualTrackRecorder:
    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self._caller_buffer = bytearray()
        self._agent_buffer = bytearray()

    def write_caller_frame(self, pcm_bytes: bytes) -> None:
        self._validate(pcm_bytes)
        self._caller_buffer.extend(pcm_bytes)

    def write_agent_frame(self, pcm_bytes: bytes) -> None:
        self._validate(pcm_bytes)
        self._agent_buffer.extend(pcm_bytes)

    @staticmethod
    def _validate(pcm_bytes: bytes) -> None:
        if len(pcm_bytes) % _SAMPLE_WIDTH_BYTES != 0:
            raise ValueError(
                f"PCM frame length {len(pcm_bytes)} is not a multiple of "
                f"sample_width={_SAMPLE_WIDTH_BYTES}"
            )

    def finalize(self, wav_path: Path) -> Path:
        wav_path = Path(wav_path)
        wav_path.parent.mkdir(parents=True, exist_ok=True)

        caller = np.frombuffer(bytes(self._caller_buffer), dtype="<i2")
        agent = np.frombuffer(bytes(self._agent_buffer), dtype="<i2")

        n_frames = max(len(caller), len(agent))
        caller = np.pad(caller, (0, n_frames - len(caller)))
        agent = np.pad(agent, (0, n_frames - len(agent)))

        interleaved = np.empty(n_frames * 2, dtype="<i2")
        interleaved[0::2] = caller
        interleaved[1::2] = agent

        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(_SAMPLE_WIDTH_BYTES)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(interleaved.tobytes())

        return wav_path


def convert_to_compressed(wav_path: Path, output_format: str = "ogg") -> Path:
    """Shell out to ffmpeg to produce the OGG/MP3 required for submission.

    Not unit-tested (see docs/DECISIONS.md #10) — covered by a smoke test
    that skips when ffmpeg isn't on PATH, and exercised for real by the
    actual verification calls.
    """
    if output_format not in {"ogg", "mp3"}:
        raise ValueError(f"Unsupported output_format: {output_format}")

    wav_path = Path(wav_path)
    out_path = wav_path.with_suffix(f".{output_format}")
    codec_args = ["-c:a", "libopus"] if output_format == "ogg" else ["-c:a", "libmp3lame"]

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), *codec_args, str(out_path)],
        check=True,
        capture_output=True,
    )
    return out_path
