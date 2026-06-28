from __future__ import annotations

import sys
import types

import pytest

from kokoro_tts.config import TTSConfig, load_config
from kokoro_tts.text.frontend import normalize_for_model
from kokoro_tts.text.tn import reset_tn_caches
from kokoro_tts.validation import prepare_text_for_synthesis


@pytest.fixture(autouse=True)
def _clear_tn_cache_between_tests():
    reset_tn_caches()
    yield
    reset_tn_caches()


def _install_fake_wetext(monkeypatch, normalizer_cls):
    tn_mod = types.ModuleType("tn")
    chinese_mod = types.ModuleType("tn.chinese")
    normalizer_mod = types.ModuleType("tn.chinese.normalizer")
    normalizer_mod.Normalizer = normalizer_cls
    monkeypatch.setitem(sys.modules, "tn", tn_mod)
    monkeypatch.setitem(sys.modules, "tn.chinese", chinese_mod)
    monkeypatch.setitem(sys.modules, "tn.chinese.normalizer", normalizer_mod)
    reset_tn_caches()


def test_tn_engine_env_normalizes_values(monkeypatch):
    monkeypatch.setenv("ANGEVOICE_TN_ENGINE", "off")
    cfg = load_config()
    assert cfg.angevoice_tn_engine == "off"
    monkeypatch.setenv("ANGEVOICE_TN_ENGINE", "legacy")
    cfg = load_config()
    assert cfg.angevoice_tn_engine == "legacy"


def test_wetext_missing_falls_back_to_legacy_without_blocking():
    cfg = TTSConfig(angevoice_tn_engine="wetext")
    assert prepare_text_for_synthesis("3.5", cfg, model_id="zipvoice") == "三点五"
    assert normalize_for_model("AngeVoice 2.6.613 版本", cfg, model="kokoro") == "AngeVoice 2.6.613 版本"


def test_fake_wetext_backend_is_used_when_available(monkeypatch):
    class FakeNormalizer:
        def normalize(self, text):
            return text.replace("今天是2026-06-11", "今天是二零二六年六月十一日")

    _install_fake_wetext(monkeypatch, FakeNormalizer)
    cfg = TTSConfig(angevoice_tn_engine="wetext")
    assert normalize_for_model("今天是2026-06-11", cfg, model="kokoro") == "今天是二零二六年六月十一日"


@pytest.mark.parametrize("source", ["2026.1.10", "2026.1.10日", "2026-1-10", "2026/1/10"])
def test_calendar_dates_are_not_treated_as_versions(source):
    cfg = TTSConfig(angevoice_tn_engine="legacy")
    assert normalize_for_model(source, cfg, model="kokoro") == "二零二六年一月十日"


def test_wetext_path_preserves_angevoice_calendar_date_before_backend(monkeypatch):
    class PassthroughNormalizer:
        def normalize(self, text):
            return text

    _install_fake_wetext(monkeypatch, PassthroughNormalizer)
    cfg = TTSConfig(angevoice_tn_engine="wetext")
    assert normalize_for_model("2026.1.10日", cfg, model="kokoro") == "二零二六年一月十日"


def test_external_tn_cannot_damage_protected_versions_and_terms(monkeypatch):
    class AggressiveNormalizer:
        def normalize(self, text):
            return (
                text.replace("AngeVoice", "Ange Voice")
                .replace("2.6.613", "二点六.613")
                .replace("Python 3.10", "Python 三点一零")
                .replace("CUDA 12.1", "CUDA 十二点一")
                .replace("Live2D", "Live 二 D")
                .replace("3.5mm", "三点五毫米")
            )

    _install_fake_wetext(monkeypatch, AggressiveNormalizer)
    cfg = TTSConfig(angevoice_tn_engine="wetext")
    text = "AngeVoice 2.6.613 版本 Python 3.10 CUDA 12.1 Live2D 3.5mm"
    assert normalize_for_model(text, cfg, model="kokoro") == text


def test_model_proxy_is_isolated_to_kokoro():
    cfg = TTSConfig(angevoice_tn_engine="legacy")
    assert "银杭" in prepare_text_for_synthesis("银行行长", cfg, model_id="kokoro")
    assert "银杭" not in prepare_text_for_synthesis("银行行长", cfg, model_id="moss")
    assert "银杭" not in prepare_text_for_synthesis("银行行长", cfg, model_id="zipvoice")
    assert prepare_text_for_synthesis("银行行长", cfg, model_id="zipvoice") == "银行行长"


@pytest.mark.parametrize(
    "text",
    [
        "https://example.com/a?b=1",
        "D:\\AI\\work\\AngeVoice-main",
        "192.168.1.2",
        "Python 3.10",
        "CUDA 12.1",
        "3.5 版本",
        "The cable is 3.5mm.",
    ],
)
def test_protected_spans_survive_wetext_path(monkeypatch, text):
    class NoisyNormalizer:
        def normalize(self, value):
            return value.replace("3.5", "三点五").replace("12.1", "十二点一").replace("3.10", "三点一零")

    _install_fake_wetext(monkeypatch, NoisyNormalizer)
    cfg = TTSConfig(angevoice_tn_engine="wetext")
    assert normalize_for_model(text, cfg, model="zipvoice") == text
