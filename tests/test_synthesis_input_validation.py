from __future__ import annotations

import pytest
from fastapi import HTTPException

from kokoro_tts.config import TTSConfig
from kokoro_tts.engine import normalize_text_for_tts
from kokoro_tts.validation import NO_SYNTHESIZABLE_TEXT_CODE, prepare_text_for_synthesis


def test_zipvoice_numeric_text_is_naturalized_before_tokenizer():
    cfg = TTSConfig()
    assert prepare_text_for_synthesis("3.5", cfg, model_id="zipvoice") == "三点五"
    assert prepare_text_for_synthesis("2.", cfg, model_id="zipvoice") == "二"
    assert prepare_text_for_synthesis("50%", cfg, model_id="zipvoice") == "百分之五十"
    assert prepare_text_for_synthesis("1,000,000", cfg, model_id="zipvoice") == "一百万"
    assert prepare_text_for_synthesis("1,234.56", cfg, model_id="zipvoice") == "一千二百三十四点五六"
    assert prepare_text_for_synthesis("-42", cfg, model_id="zipvoice") == "负四十二"
    assert prepare_text_for_synthesis("-3.5", cfg, model_id="zipvoice") == "负三点五"
    assert prepare_text_for_synthesis("2026-06-11", cfg, model_id="zipvoice") == "二零二六年六月十一日"


def test_zipvoice_non_natural_text_returns_structured_error():
    cfg = TTSConfig()
    for value in ["...", "https://example.com/a?b=1", 'print("hello")', "def x():\n    return 1", '{"a": 1}']:
        with pytest.raises(HTTPException) as err:
            prepare_text_for_synthesis(value, cfg, model_id="zipvoice")
        assert err.value.status_code == 400
        assert err.value.detail["code"] == NO_SYNTHESIZABLE_TEXT_CODE
        assert "integer division" not in str(err.value.detail)


def test_plain_numeric_normalization_supports_zipvoice_tokenizable_text():
    assert normalize_text_for_tts("3.5") == "三点五"
    assert normalize_text_for_tts("2.") == "二"
    assert normalize_text_for_tts("1,000,000") == "一百万"
    assert normalize_text_for_tts("1,234.56") == "一千二百三十四点五六"
    assert normalize_text_for_tts("-42") == "负四十二"
    assert normalize_text_for_tts("-3.5") == "负三点五"
    assert normalize_text_for_tts("¥1,000") == "一千元"
    assert normalize_text_for_tts("1,234.56元") == "一千二百三十四元五角六分"


def test_normalize_text_input_preserves_falsy_non_none_values():
    from kokoro_tts.validation import normalize_text_input

    assert normalize_text_input(0) == "0"
    assert normalize_text_input(False) == "False"
    assert normalize_text_input(None) == ""
