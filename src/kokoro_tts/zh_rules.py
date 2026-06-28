"""Lightweight Chinese prosody and polyphone rules for TTS input."""

from __future__ import annotations

import re

from .text.polyphone import apply_polyphone_overrides, detect_polyphones
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_LONG_CHINESE_RUN_RE = re.compile(r"[\u4e00-\u9fff]{24,}")
_SENTENCE_END = "。！？!?"
_ANY_PUNCT = "。！？!？；;，,、：:"
_PAUSE_PUNCT = "，"

_LEXICON = {
    "往事",
    "知多少",
    "小楼",
    "昨夜",
    "又东风",
    "故国",
    "不堪",
    "回首",
    "月明中",
    "雕栏玉砌",
    "朱颜",
    "只是",
    "恰似",
    "一江春水",
    "向东流",
}
_MAX_WORD_LEN = max(len(word) for word in _LEXICON)

def _has_chinese(text: str) -> bool:
    return bool(_CHINESE_RE.search(text))


def _ends_with_sentence_punctuation(text: str) -> bool:
    return bool(text) and text[-1] in _SENTENCE_END


def _contains_pause(text: str) -> bool:
    return any(ch in _ANY_PUNCT for ch in text)


def _fallback_cut(run: str) -> list[str]:
    words: list[str] = []
    index = 0
    while index < len(run):
        matched = ""
        for size in range(min(_MAX_WORD_LEN, len(run) - index), 1, -1):
            candidate = run[index : index + size]
            if candidate in _LEXICON:
                matched = candidate
                break
        if matched:
            words.append(matched)
            index += len(matched)
        else:
            words.append(run[index])
            index += 1
    return words


def segment_chinese_words(run: str) -> list[str]:
    """Segment a Chinese run using jieba when available, with a small fallback."""
    try:
        import jieba

        words = [word for word in jieba.cut(run, HMM=True) if word.strip()]
        return words or [run]
    except Exception:
        return _fallback_cut(run)


def _chunk_words(words: list[str], max_chars: int = 16) -> list[str]:
    chunks: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + len(word) > max_chars:
            chunks.append(current)
            current = word
        else:
            current += word
    if current:
        chunks.append(current)
    return chunks


def _punctuate_long_run(match: re.Match[str]) -> str:
    run = match.group(0)
    chunks = _chunk_words(segment_chinese_words(run))
    return _PAUSE_PUNCT.join(chunks)


def apply_auto_punctuation(text: str) -> str:
    """Add conservative pause marks for long or poetry-like Chinese input."""
    if not _has_chinese(text):
        return text

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if len(lines) > 1:
        punctuated_lines: list[str] = []
        for index, line in enumerate(lines):
            if _ends_with_sentence_punctuation(line) or line[-1:] in "，,；;":
                punctuated_lines.append(line)
            elif index == len(lines) - 1:
                punctuated_lines.append(line + "。")
            else:
                punctuated_lines.append(line + "，")
        normalized = "".join(punctuated_lines)

    normalized = _LONG_CHINESE_RUN_RE.sub(_punctuate_long_run, normalized)
    return normalized


def normalize_chinese_rules(text: str, model: str = "kokoro") -> str:
    text = apply_auto_punctuation(text)
    return apply_polyphone_overrides(text, model=model)
