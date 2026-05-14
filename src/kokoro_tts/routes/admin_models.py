"""Pydantic models for AngeVoice admin APIs."""

from pydantic import BaseModel, Field


class AdminModelAction(BaseModel):
    include_current: bool = True
    force: bool = False


class AdminSingleModelAction(BaseModel):
    force: bool = False


class AdminSwitchModelAction(BaseModel):
    model: str
    unload_previous: bool | None = None
    load: bool = True


class AdminApiKeyAction(BaseModel):
    rotate: bool = True


class AdminConfigPatch(BaseModel):
    default_speed: float | None = Field(default=None, ge=0.5, le=2.0)
    max_concurrent_requests: int | None = Field(default=None, ge=1, le=64)
    request_timeout_seconds: float | None = Field(default=None, ge=1, le=3600)
    model_idle_timeout_seconds: float | None = Field(default=None, ge=0, le=86400)
    model_idle_check_interval: float | None = Field(default=None, ge=5, le=3600)
    moss_stream_chunk_seconds: float | None = Field(default=None, ge=0.05, le=2.0)
    moss_realtime_streaming_decode: bool | None = None
    moss_quality_gate_enabled: bool | None = None
    moss_process_isolation_enabled: bool | None = None
    rate_limit_qps: float | None = Field(default=None, ge=0, le=1000)
    rate_limit_burst: int | None = Field(default=None, ge=0, le=10000)
    max_queue_length: int | None = Field(default=None, ge=0, le=10000)
    trust_proxy_headers: bool | None = None
    public_status_endpoints: bool | None = None
    model_source: str | None = Field(default=None, pattern="^(auto|huggingface|modelscope)$")

