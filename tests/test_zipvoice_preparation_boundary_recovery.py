from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace


class _FakeWorker:
    is_loaded = True
    alive = True
    is_healthy = True
    pid = 123
    last_exit_reason = ""

    def __init__(self):
        self.calls = []

    def request(self, method, payload, timeout):
        self.calls.append((method, payload, timeout))
        return b"RIFF"

    def stream(self, payload, timeout, cancel_check=None):
        self.calls.append(("stream", payload, timeout))
        yield {"type": "done"}


def _worker_engine():
    from kokoro_tts.zipvoice.engine import ZipVoiceEngine

    engine = ZipVoiceEngine.__new__(ZipVoiceEngine)
    engine.cfg = SimpleNamespace(request_timeout_seconds=5.0, max_text_length=10000)
    engine.public_id = "zipvoice"
    engine._worker = _FakeWorker()
    engine._state_lock = nullcontext()
    return engine


def test_zipvoice_synthesize_skips_prepare_when_flags_are_set(monkeypatch):
    from kokoro_tts.zipvoice import engine as engine_module

    def fail_prepare(*args, **kwargs):
        raise AssertionError("prepare_text_for_synthesis should not run for prepared ZipVoice text")

    monkeypatch.setattr(engine_module, "prepare_text_for_synthesis", fail_prepare)
    engine = _worker_engine()

    engine.synthesize(
        "prepared text",
        "voice",
        1.0,
        prompt_audio_path="/tmp/ref.wav",
        prompt_text="prepared prompt",
        text_prepared=True,
        prompt_text_prepared=True,
    )

    payload = engine._worker.calls[0][1]
    assert payload["text"] == "prepared text"
    assert payload["prompt_text"] == "prepared prompt"
    assert payload["text_prepared"] is True
    assert payload["prompt_text_prepared"] is True


def test_zipvoice_stream_payload_keeps_prepared_flags(monkeypatch):
    from kokoro_tts.zipvoice import engine as engine_module

    def fail_prepare(*args, **kwargs):
        raise AssertionError("prepare_text_for_synthesis should not run for prepared ZipVoice stream")

    monkeypatch.setattr(engine_module, "prepare_text_for_synthesis", fail_prepare)
    engine = _worker_engine()

    frames = list(
        engine.synthesize_stream(
            "prepared text",
            "voice",
            1.0,
            "pcm_s16le",
            prompt_audio_path="/tmp/ref.wav",
            prompt_text="prepared prompt",
            text_prepared=True,
            prompt_text_prepared=True,
        )
    )

    assert frames == [{"type": "done"}]
    payload = engine._worker.calls[0][1]
    assert payload["text_prepared"] is True
    assert payload["prompt_text_prepared"] is True
