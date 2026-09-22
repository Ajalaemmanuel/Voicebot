import shutil
import struct
import wave

import pytest

from recorder import DualTrackRecorder, convert_to_compressed


def pcm16(*samples: int) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def test_write_frame_rejects_odd_byte_length():
    recorder = DualTrackRecorder(sample_rate=8000)

    with pytest.raises(ValueError, match="sample_width"):
        recorder.write_caller_frame(b"\x01\x02\x03")


def test_finalize_writes_valid_stereo_wav(tmp_path):
    recorder = DualTrackRecorder(sample_rate=8000)
    recorder.write_caller_frame(pcm16(100, 200, 300))
    recorder.write_agent_frame(pcm16(10, 20, 30))

    out_path = recorder.finalize(tmp_path / "audio.wav")

    with wave.open(str(out_path), "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 3
        frames = wav_file.readframes(3)

    samples = struct.unpack("<6h", frames)
    # interleaved as (caller, agent) per frame -> left, right, left, right...
    assert samples == (100, 10, 200, 20, 300, 30)


def test_finalize_pads_shorter_track_with_silence(tmp_path):
    recorder = DualTrackRecorder(sample_rate=8000)
    recorder.write_caller_frame(pcm16(1, 2, 3, 4, 5))
    recorder.write_agent_frame(pcm16(9, 9))

    out_path = recorder.finalize(tmp_path / "audio.wav")

    with wave.open(str(out_path), "rb") as wav_file:
        assert wav_file.getnframes() == 5
        frames = wav_file.readframes(5)

    samples = struct.unpack("<10h", frames)
    assert samples == (1, 9, 2, 9, 3, 0, 4, 0, 5, 0)


def test_finalize_with_no_audio_writes_empty_wav(tmp_path):
    recorder = DualTrackRecorder(sample_rate=8000)

    out_path = recorder.finalize(tmp_path / "audio.wav")

    with wave.open(str(out_path), "rb") as wav_file:
        assert wav_file.getnframes() == 0


def test_finalize_creates_parent_directories(tmp_path):
    recorder = DualTrackRecorder(sample_rate=8000)
    recorder.write_caller_frame(pcm16(1))

    out_path = recorder.finalize(tmp_path / "nested" / "audio.wav")

    assert out_path.exists()


def test_convert_to_compressed_rejects_unsupported_format(tmp_path):
    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"")

    with pytest.raises(ValueError, match="output_format"):
        convert_to_compressed(wav_path, output_format="flac")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_convert_to_compressed_produces_playable_ogg(tmp_path):
    recorder = DualTrackRecorder(sample_rate=8000)
    recorder.write_caller_frame(pcm16(*range(0, 800, 4)))
    recorder.write_agent_frame(pcm16(*range(0, 400, 4)))
    wav_path = recorder.finalize(tmp_path / "audio.wav")

    ogg_path = convert_to_compressed(wav_path, output_format="ogg")

    assert ogg_path.exists()
    assert ogg_path.stat().st_size > 0
