"""Shared request validation helpers for all public TTS entry points."""

from __future__ import annotations

import re

from fastapi import HTTPException


NO_SYNTHESIZABLE_TEXT_CODE = "NO_SYNTHESIZABLE_TEXT"
NO_SYNTHESIZABLE_TEXT_MESSAGE = "未检测到可合成的中文或英文文本"
NO_SYNTHESIZABLE_TEXT_HINT = "当前内容包含代码、数字或符号，暂不适合直接语音合成"


def no_synthesizable_text_detail(*, request_id: str = "", reason: str = "") -> dict[str, str]:
    detail = {
        "code": NO_SYNTHESIZABLE_TEXT_CODE,
        "message": NO_SYNTHESIZABLE_TEXT_MESSAGE,
        "hint": NO_SYNTHESIZABLE_TEXT_HINT,
    }
    if request_id:
        detail["request_id"] = str(request_id)
    if reason:
        detail["debug_reason"] = str(reason)
    return detail


def raise_no_synthesizable_text(*, request_id: str = "", reason: str = "") -> None:
    raise HTTPException(status_code=400, detail=no_synthesizable_text_detail(request_id=request_id, reason=reason))


def is_no_synthesizable_text_error(exc: BaseException) -> bool:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return detail.get("code") == NO_SYNTHESIZABLE_TEXT_CODE
        return _looks_like_no_speech_runtime_message(str(detail))
    return _looks_like_no_speech_runtime_message(str(exc))


def websocket_error_frame_from_http(exc: HTTPException, *, request_id: str = "") -> dict[str, str]:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or "BAD_REQUEST")
        message = str(detail.get("message") or "请求参数无效")
    else:
        code = NO_SYNTHESIZABLE_TEXT_CODE if _looks_like_no_speech_runtime_message(str(detail)) else "BAD_REQUEST"
        message = NO_SYNTHESIZABLE_TEXT_MESSAGE if code == NO_SYNTHESIZABLE_TEXT_CODE else str(detail or "请求参数无效")
    frame = {"type": "error", "code": code, "message": message}
    if request_id:
        frame["request_id"] = request_id
    return frame


def no_synthesizable_text_frame(*, request_id: str = "") -> dict[str, str]:
    frame = {"type": "error", "code": NO_SYNTHESIZABLE_TEXT_CODE, "message": NO_SYNTHESIZABLE_TEXT_MESSAGE}
    if request_id:
        frame["request_id"] = request_id
    return frame


def normalize_text_input(value: object) -> str:
    """Normalize user supplied text without changing semantic content."""

    return str(value if value is not None else "").strip()


def validate_text_input(value: object, *, max_length: int, field_name: str = "text") -> str:
    """Validate and return a normalized text value.

    This is intentionally used by every HTTP, WebSocket and batch entry point so
    the public API cannot bypass ``KOKORO_MAX_TEXT_LENGTH`` accidentally.
    """

    text = normalize_text_input(value)
    if not text:
        raise HTTPException(status_code=400, detail=f"缺少 {field_name} 参数")
    limit = max(1, int(max_length))
    if len(text) > limit:
        raise HTTPException(status_code=400, detail=f"文本过长，上限 {limit} 字符，当前 {len(text)} 字符")
    return text


def validate_tts_text(value: object, cfg, *, field_name: str = "text") -> str:
    return validate_text_input(value, max_length=int(getattr(cfg, "max_text_length", 10000)), field_name=field_name)


def is_moss_model_id(model_id: object) -> bool:
    return str(model_id or "").strip().lower().startswith("moss")


def validate_model_speed(model_id: object, speed: object) -> float:
    """Validate ``speed`` and reject unsupported MOSS speed control.

    MOSS-TTS-Nano runtime currently ignores/does not expose stable speed control.
    Failing fast avoids the front-end being honest while API users can still pass
    a misleading value.
    """

    try:
        value = float(speed)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="speed 必须是数字") from None
    if is_moss_model_id(model_id) and abs(value - 1.0) > 1e-6:
        raise HTTPException(status_code=400, detail="MOSS-TTS-Nano 暂不支持语速调节，请使用 speed=1.0")
    return value


_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_DIGIT_RE = re.compile(r"\d")
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_JSON_LIKE_RE = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.S)
_CODE_KEYWORD_RE = re.compile(
    r"(?i)(?:\b(?:def|class|function|const|let|var|import|from|return|if|else|for|while|try|except|catch)\b|console\.log|print\s*\()"
)
_LOG_LINE_RE = re.compile(r"(?i)^(?:\[?\d{4}[-/]\d{2}[-/]\d{2}|\d{2}:\d{2}:\d{2}|INFO|WARN|WARNING|ERROR|DEBUG|Traceback|File \"|Exception:)")
_CONVERTIBLE_NUMERIC_RE = re.compile(
    r"^\s*(?:[+-]?\d{1,8}(?:\.\d{1,8})?%?|[+-]?\d{1,5}\.?|(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\s*$"
)


def _looks_like_no_speech_runtime_message(message: str) -> bool:
    text = str(message or "")
    return any(
        marker in text
        for marker in (
            "integer division or modulo by zero",
            "ZeroDivisionError",
            "No English or Chinese characters found",
            "tokens_lens",
            "zero tokens",
        )
    )


def _has_speech_characters(text: str) -> bool:
    return bool(_CHINESE_RE.search(text) or _LATIN_WORD_RE.search(text))


def _mostly_symbolic(text: str) -> bool:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return True
    speech_or_digit = sum(1 for ch in chars if _CHINESE_RE.match(ch) or ch.isalpha() or ch.isdigit())
    return speech_or_digit / max(1, len(chars)) < 0.25


def _line_looks_like_code_or_log(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _LOG_LINE_RE.search(stripped):
        return True
    if _URL_RE.search(stripped):
        return True
    if _CODE_KEYWORD_RE.search(stripped) and re.search(r"[{}();:=]", stripped):
        return True
    if re.search(r"[{}();]", stripped) and re.search(r"[=<>]|=>|//|/\*|\*/", stripped):
        return True
    if re.match(r"^[A-Za-z]:\\|^/[^\s]+", stripped):
        return True
    return False


def _looks_like_convertible_numeric_text(text: str) -> bool:
    return bool(_CONVERTIBLE_NUMERIC_RE.fullmatch(str(text or "").strip()))


def _looks_like_non_natural_text(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return True
    if _looks_like_convertible_numeric_text(stripped):
        return False
    if _mostly_symbolic(stripped) and not _DIGIT_RE.search(stripped):
        return True
    if _URL_RE.fullmatch(stripped):
        return True
    if "```" in stripped:
        return True
    if _JSON_LIKE_RE.match(stripped) and (":" in stripped or '"' in stripped):
        return True
    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) >= 2:
        bad = sum(1 for line in lines if _line_looks_like_code_or_log(line))
        if bad / len(lines) >= 0.5:
            return True
    elif _line_looks_like_code_or_log(stripped):
        return True
    if _URL_RE.search(stripped) and not _CHINESE_RE.search(stripped):
        return True
    return False


def prepare_text_for_synthesis(value: object, cfg, *, model_id: str = "", field_name: str = "text", request_id: str = "") -> str:
    """返回进入模型前的可合成文本；代码/URL/纯符号返回结构化错误。"""

    text = validate_tts_text(value, cfg, field_name=field_name)
    if not _looks_like_convertible_numeric_text(text) and _looks_like_non_natural_text(text):
        raise_no_synthesizable_text(request_id=request_id, reason=f"{field_name}: non-natural text")
    from .engine import normalize_text_for_tts
    from .text_segmenter import normalize_text_for_segmentation

    cleaned = normalize_text_for_segmentation(text)
    cleaned = normalize_text_for_tts(cleaned, model=str(model_id or "kokoro"))
    cleaned = normalize_text_for_segmentation(cleaned)
    if not cleaned or _looks_like_non_natural_text(cleaned) or not _has_speech_characters(cleaned):
        raise_no_synthesizable_text(request_id=request_id, reason=f"{field_name}: no tokenizable speech after normalization")
    return cleaned
