import numpy as np

from kokoro_tts.moss.postprocess import (
    clamp_pause_seconds,
    compress_long_silence,
    concat_waveforms,
    trim_silence_edges,
)


def test_compress_long_silence_stereo():
    sr = 1000
    tone = np.ones((100, 2), dtype=np.float32) * 0.2
    silence = np.zeros((2500, 2), dtype=np.float32)
    audio = np.concatenate([tone, silence, tone], axis=0)
    compressed, metrics = compress_long_silence(
        audio,
        sample_rate=sr,
        channels=2,
        threshold_db=-45,
        max_silence_ms=900,
    )
    assert compressed.shape[1] == 2
    assert compressed.shape[0] <= 100 + 900 + 100
    assert metrics["long_silence_count"] == 1
    assert metrics["max_silence_ms"] >= 2400


def test_crossfade_concat_keeps_stereo_shape():
    a = np.ones((100, 2), dtype=np.float32) * 0.2
    b = np.ones((100, 2), dtype=np.float32) * -0.2
    merged = concat_waveforms([a, b], crossfade_ms=20, sample_rate=1000, channels=2)
    assert merged.shape == (180, 2)
    assert np.max(np.abs(merged)) <= 0.21


def test_trim_silence_edges_reports_trimmed_ms():
    sr = 1000
    silence = np.zeros((100, 2), dtype=np.float32)
    tone = np.ones((200, 2), dtype=np.float32) * 0.2
    audio = np.concatenate([silence, tone, silence], axis=0)
    trimmed, start_ms, end_ms = trim_silence_edges(audio, sample_rate=sr, channels=2, threshold_db=-45, keep_ms=10)
    assert trimmed.shape[1] == 2
    assert trimmed.shape[0] == 220
    assert 80 <= start_ms <= 100
    assert 80 <= end_ms <= 100


def test_clamp_pause_seconds():
    assert clamp_pause_seconds(5.0, max_ms=650) == 0.65
    assert clamp_pause_seconds(-1.0, max_ms=650) == 0.0


def test_audio_format_aliases_and_ffmpeg_disabled_errors():
    import pytest
    from fastapi import HTTPException
    from kokoro_tts.audio_formats import normalize_response_format, supported_response_formats
    from kokoro_tts.config import TTSConfig

    cfg = TTSConfig(ffmpeg_enabled=False, mp3_enabled=False)
    assert normalize_response_format("wav", cfg) == "wav"
    assert normalize_response_format("pcm_s16le", cfg) == "pcm"
    assert supported_response_formats(cfg) == ["wav", "pcm"]
    with pytest.raises(HTTPException) as err:
        normalize_response_format("telegram_voice", cfg)
    assert err.value.status_code == 400
    assert err.value.detail["code"] == "FFMPEG_DISABLED"


def test_audio_format_transcode_invokes_expected_ogg_opus_command(monkeypatch):
    import subprocess
    from kokoro_tts.audio_formats import transcode_wav_bytes
    from kokoro_tts.config import TTSConfig

    calls = {}

    class _Proc:
        returncode = 0
        stdout = b"ogg-data"
        stderr = b""

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["kwargs"] = kwargs
        return _Proc()

    monkeypatch.setattr("kokoro_tts.audio_formats.shutil.which", lambda binary: "/usr/bin/ffmpeg")
    monkeypatch.setattr("kokoro_tts.audio_formats.subprocess.run", fake_run)
    cfg = TTSConfig(ffmpeg_enabled=True, ffmpeg_binary="ffmpeg")
    payload, media_type = transcode_wav_bytes(b"RIFF....WAVE", cfg, "telegram_voice")
    assert payload == b"ogg-data"
    assert media_type == "audio/ogg"
    assert "libopus" in calls["cmd"]
    assert calls["kwargs"]["stdout"] is subprocess.PIPE


def test_audio_format_transcode_m4a_uses_seekable_temp_file(monkeypatch):
    from pathlib import Path
    from kokoro_tts.audio_formats import transcode_wav_bytes
    from kokoro_tts.config import TTSConfig

    calls = {}

    class _Proc:
        returncode = 0
        stdout = b""
        stderr = b""

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["kwargs"] = kwargs
        output_path = Path(cmd[-1])
        assert output_path.name == "output.m4a"
        assert output_path.parent.exists()
        output_path.write_bytes(b"m4a-data")
        return _Proc()

    monkeypatch.setattr("kokoro_tts.audio_formats.shutil.which", lambda binary: "/usr/bin/ffmpeg")
    monkeypatch.setattr("kokoro_tts.audio_formats.subprocess.run", fake_run)
    cfg = TTSConfig(ffmpeg_enabled=True, ffmpeg_binary="ffmpeg")
    payload, media_type = transcode_wav_bytes(b"RIFF....WAVE", cfg, "m4a")
    assert payload == b"m4a-data"
    assert media_type == "audio/mp4"
    assert calls["cmd"][-1].endswith("output.m4a")
    assert "pipe:1" not in calls["cmd"]
