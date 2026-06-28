"""Span protection for text normalization.

The TN layer may aggressively rewrite technical strings. Protecting spans keeps
model names, paths, URLs, versions, and units stable while still allowing real
calendar dates such as ``2026.1.10`` to be normalized.
"""

from __future__ import annotations

import re

_PROTECTED_SPAN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:AngeVoice|Live2D|CPU|GPU|RTF|API|TTS|ZipVoice|MOSS|Kokoro)\b", re.IGNORECASE),
    re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\[^\s，。！？；：]+"),
    re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    re.compile(r"\bv\d+(?:\.\d+){1,4}\b", re.IGNORECASE),
    re.compile(r"\b(?!19\d{2}[./-]\d{1,2}[./-]\d{1,2})(?!20\d{2}[./-]\d{1,2}[./-]\d{1,2})\d+(?:\.\d+){2,4}\b"),
    re.compile(r"\b(?:Python|CUDA|PyTorch|Torch|cuDNN)\s+\d+(?:\.\d+){1,3}\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+){1,3}\s*(?:版本|版)"),
    re.compile(r"(?:版本|版)\s*\d+(?:\.\d+){1,3}\b"),
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|km|GB|MB|KB|TB|Mbps|Gbps|Hz|kHz|MHz|GHz|ms|s|V|W|G)\b",
        re.IGNORECASE,
    ),
)


def _span_token(index: int) -> str:
    chars: list[str] = []
    value = index
    while True:
        chars.append(chr(ord("A") + (value % 26)))
        value //= 26
        if value == 0:
            break
    return "ANGEPROTECTED" + "".join(chars)


def protect_spans(text: str) -> tuple[str, dict[str, str]]:
    spans: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        token = _span_token(len(spans))
        spans[token] = match.group(0)
        return token

    protected = str(text)
    for pattern in _PROTECTED_SPAN_PATTERNS:
        protected = pattern.sub(repl, protected)
    return protected, spans


def restore_spans(text: str, spans: dict[str, str]) -> str:
    restored = str(text)
    for token, original in reversed(tuple(spans.items())):
        restored = restored.replace(token, original)
    return restored
