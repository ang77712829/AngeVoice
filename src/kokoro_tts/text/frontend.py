"""Small model-aware frontend facade for synthesis text preparation."""

from __future__ import annotations

import logging

from ..zh_rules import normalize_chinese_rules
from .legacy import normalize_calendar_dates, normalize_text_for_tts as normalize_with_legacy
from .protection import protect_spans, restore_spans
from .tn import TextNormalizerUnavailable, normalize_with_wetext

logger = logging.getLogger(__name__)

_WARNED_TN_FALLBACKS: set[str] = set()
_TN_ENGINE_ALIASES = {
    "": None,
    "default": None,
    "auto": None,
    "wetext": "wetext",
    "standard": "wetext",
    "legacy": "legacy",
    "builtin": "legacy",
    "angevoice": "legacy",
    "off": "off",
    "none": "off",
    "false": "off",
    "0": "off",
}

def _model_family(model: str) -> str:
    raw = str(model or "kokoro").strip().lower()
    if raw.startswith("moss"):
        return "moss"
    if raw.startswith("zipvoice"):
        return "zipvoice"
    return "kokoro"


def _tn_engine(cfg: object) -> str:
    raw = str(getattr(cfg, "angevoice_tn_engine", "wetext") or "wetext").strip().lower()
    if raw in {"0", "false", "no", "off", "none"}:
        return "off"
    if raw in {"legacy", "builtin", "angevoice"}:
        return "legacy"
    return "wetext"


class _TextFrontendConfigOverride:
    def __init__(self, base: object, *, angevoice_tn_engine: str):
        self._base = base
        self.angevoice_tn_engine = angevoice_tn_engine

    def __getattr__(self, name: str):
        return getattr(self._base, name)


def normalize_tn_engine_choice(value: object) -> str | None:
    """Return a supported TN engine name, or None for the configured default."""

    raw = str(value or "").strip().lower().replace("-", "_")
    if raw not in _TN_ENGINE_ALIASES:
        raise ValueError("text_normalization must be wetext, legacy, off, or default")
    return _TN_ENGINE_ALIASES[raw]


def cfg_with_tn_engine(cfg: object, value: object) -> object:
    """Apply a request-scoped TN override without mutating the global config."""

    engine = normalize_tn_engine_choice(value)
    if engine is None:
        return cfg
    return _TextFrontendConfigOverride(cfg, angevoice_tn_engine=engine)


def _legacy_normalize(text: str, *, model: str) -> str:
    return normalize_with_legacy(text, model=model)


def _warn_tn_fallback(engine: str, exc: Exception) -> None:
    if engine in _WARNED_TN_FALLBACKS:
        return
    _WARNED_TN_FALLBACKS.add(engine)
    logger.warning("Text normalization backend %s unavailable; falling back to legacy rules: %s", engine, exc)


def normalize_for_model(text: str, cfg: object, *, model: str = "kokoro", field_name: str = "text") -> str:
    """Normalize text once for the requested model family."""

    if not text:
        return text
    family = _model_family(model)
    protected, spans = protect_spans(str(text))
    engine = _tn_engine(cfg)

    if engine == "off":
        normalized = normalize_chinese_rules(protected, model=family)
    elif engine == "legacy":
        normalized = _legacy_normalize(protected, model=family)
    else:
        try:
            normalized = normalize_with_wetext(normalize_calendar_dates(protected))
            normalized = normalize_chinese_rules(normalized, model=family)
        except TextNormalizerUnavailable as exc:
            _warn_tn_fallback(engine, exc)
            normalized = _legacy_normalize(protected, model=family)

    return restore_spans(normalized, spans)


def _reset_frontend_state_for_tests() -> None:
    _WARNED_TN_FALLBACKS.clear()
