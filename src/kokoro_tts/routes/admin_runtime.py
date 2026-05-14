"""Runtime helpers for AngeVoice admin routes."""

from __future__ import annotations

import os
from pathlib import Path

from .admin_models import AdminConfigPatch


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 12:
        return value[:2] + "***"
    return value[:6] + "..." + value[-4:]


def security_snapshot(cfg, *, reveal: bool = False) -> dict:
    key = cfg.api_key or ""
    key_file = Path(getattr(cfg, "api_key_file", "") or "")
    return {
        "api_key_enabled": bool(key),
        "api_key_preview": mask_secret(key),
        "api_key": key if reveal else "",
        "api_key_auto_generated": bool(getattr(cfg, "api_key_auto_generated", False)),
        "api_key_file": str(key_file) if str(key_file) else "",
        "api_key_file_exists": bool(key_file.exists()) if str(key_file) else False,
        "admin_allow_api_key": bool(getattr(cfg, "admin_allow_api_key", False)),
    }


def config_snapshot(cfg) -> dict:
    return {
        "enabled_models": cfg.enabled_models,
        "default_model": cfg.default_model,
        "max_concurrent_requests": cfg.max_concurrent_requests,
        "request_timeout_seconds": cfg.request_timeout_seconds,
        "idle_timeout_seconds": cfg.model_idle_timeout_seconds,
        "idle_check_interval": cfg.model_idle_check_interval,
        "idle_unload_current": getattr(cfg, "model_idle_unload_current", True),
        "moss_execution_provider": cfg.moss_execution_provider,
        "moss_stream_chunk_seconds": cfg.moss_stream_chunk_seconds,
        "moss_realtime_streaming_decode": cfg.moss_realtime_streaming_decode,
        "moss_process_isolation_enabled": cfg.moss_process_isolation_enabled,
        "moss_quality_gate_enabled": cfg.moss_quality_gate_enabled,
        "rate_limit_qps": cfg.rate_limit_qps,
        "rate_limit_burst": cfg.rate_limit_burst,
        "max_queue_length": cfg.max_queue_length,
        "trust_proxy_headers": getattr(cfg, "trust_proxy_headers", False),
        "public_status_endpoints": getattr(cfg, "public_status_endpoints", True),
        "model_source": getattr(cfg, "model_source", "auto"),
        "model_source_effective": getattr(cfg, "model_source_effective", "auto"),
        "model_source_hf_reachable": getattr(cfg, "model_source_hf_reachable", None),
        "model_source_modelscope_reachable": getattr(cfg, "model_source_modelscope_reachable", None),
    }


def apply_config_patch(cfg, patch: AdminConfigPatch) -> tuple[list[str], list[str], bool]:
    changed: list[str] = []
    restart_required: list[str] = []
    rebuild_moss = False
    restart_fields = {"max_concurrent_requests", "rate_limit_qps", "rate_limit_burst", "max_queue_length", "trust_proxy_headers"}
    for name, value in patch.model_dump(exclude_none=True).items():
        if name == "model_source":
            value = str(value).strip().lower()
            cfg.model_source_effective = "auto"
            cfg.model_source_country = ""
            cfg.model_source_hf_reachable = None
            cfg.model_source_modelscope_reachable = None
        if name == "moss_process_isolation_enabled" and bool(value) != bool(getattr(cfg, name)):
            rebuild_moss = True
        setattr(cfg, name, value)
        changed.append(name)
        if name in restart_fields:
            restart_required.append(name)
    return changed, restart_required, rebuild_moss


def rotate_api_key(cfg) -> str:
    from ..config_api_key import generate_api_key

    key = generate_api_key()
    cfg.api_key = key
    cfg.api_key_auto_generated = True
    key_file = Path(getattr(cfg, "api_key_file", "") or cfg.output_dir / ".angevoice-api-key").expanduser()
    cfg.api_key_file = key_file
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(key + "\n", encoding="utf-8")
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    os.environ["KOKORO_API_KEY"] = key
    return key
