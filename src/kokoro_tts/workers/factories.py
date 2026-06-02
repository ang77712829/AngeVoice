"""可杀死模型 worker 的运行时工厂。

每个工厂都在子进程内构造一个非隔离运行时。新增隔离模型时只需要
在这里注册工厂，并通过常规模型注册表暴露产品适配器；API 进程的
生命周期客户端保持不变。
"""

from __future__ import annotations

from collections.abc import Callable

WorkerFactory = Callable[[object, str | None], object]


def _kokoro_factory(config, _requested_provider: str | None):
    from ..engine import TTSEngine

    return TTSEngine(config)


def _moss_factory(config, requested_provider: str | None):
    """在子进程内实例化 MOSS 引擎（无进程隔离，进程本身即是隔离层）。"""
    from ..moss_engine import MossNanoEngine

    provider = str(requested_provider or "cpu").strip().lower()
    return MossNanoEngine(config, execution_provider=provider, engine_id="moss", process_isolation=False)


def _zipvoice_factory(config, requested_provider: str | None):
    from ..zipvoice.engine import ZipVoiceEngine

    return ZipVoiceEngine(config, requested_provider=requested_provider, process_isolation=False)


WORKER_ENGINE_FACTORIES: dict[str, WorkerFactory] = {
    "kokoro": _kokoro_factory,
    "moss": _moss_factory,
    "zipvoice": _zipvoice_factory,
}


def supported_worker_engines() -> tuple[str, ...]:
    return tuple(sorted(WORKER_ENGINE_FACTORIES))


def create_worker_engine(config, engine_id: str, requested_provider: str | None = None):
    try:
        factory = WORKER_ENGINE_FACTORIES[str(engine_id)]
    except KeyError as exc:
        raise ValueError(f"通用 worker 暂不支持该模型：{engine_id}") from exc
    return factory(config, requested_provider)
