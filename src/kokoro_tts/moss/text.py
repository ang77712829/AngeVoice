"""MOSS 文本清洗与分段工具。"""

from __future__ import annotations

from ..engine import normalize_text_for_tts
from ..text_segmenter import normalize_text_for_segmentation, segment_text_natural


def clean_text(text: str, *, apply_angevoice_rules: bool, model: str = "moss") -> str:
    """清理输入文本，并按配置应用 AngeVoice 中文规则。"""

    cleaned = normalize_text_for_segmentation(text)
    if apply_angevoice_rules:
        cleaned = normalize_text_for_tts(cleaned, model=model)
    return normalize_text_for_segmentation(cleaned)


def segment_text(text: str, *, max_text_length: int, segment_length: int, single_newline_policy: str = "auto") -> list[str]:
    """按中英文自然标点、段落和长度拆分 MOSS 输入。"""

    return segment_text_natural(text, max_text_length=max_text_length, segment_length=segment_length, single_newline_policy=single_newline_policy)
