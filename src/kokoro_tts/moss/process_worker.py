"""MOSS 进程级隔离 worker（已废弃）。

.. deprecated::
    本模块已废弃。MOSS 现在统一使用 ``workers.process_worker.EngineProcessClient``，
    与 Kokoro / ZipVoice 采用完全相同的进程隔离基础设施。

    为向后兼容保留此文件，但其中的 ``MossProcessClient`` /
    ``MossProcessTimeoutError`` 不再是 MOSS 的实际实现路径，
    也不再从 ``kokoro_tts.moss`` 包导出。
"""

from __future__ import annotations

import warnings

from ..workers.process_worker import (
    EngineProcessClient as _EngineProcessClient,
    EngineProcessTimeoutError as _EngineProcessTimeoutError,
)


class MossProcessTimeoutError(_EngineProcessTimeoutError):
    """已废弃：请使用 ``workers.process_worker.EngineProcessTimeoutError``。"""


class MossProcessClient(_EngineProcessClient):
    """已废弃：请使用 ``workers.process_worker.EngineProcessClient``。

    保留一个薄兼容层，避免旧导入路径或测试代码实例化时直接崩溃。
    新代码应改为 ``EngineProcessClient(engine_id="moss", requested_provider=...)``。
    """

    def __init__(self, *args, provider: str | None = None, engine_id: str = "moss", requested_provider: str | None = None, **kwargs):
        warnings.warn(
            "MossProcessClient is deprecated; use EngineProcessClient(engine_id='moss') instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if args:
            # 旧代码通常使用关键字；若传了位置参数，保持 EngineProcessClient 的
            # Python TypeError 行为，避免错误地猜测参数语义。
            super().__init__(*args, engine_id=engine_id, requested_provider=requested_provider or provider, **kwargs)
            return
        super().__init__(engine_id=engine_id, requested_provider=requested_provider or provider, **kwargs)


__all__ = [
    "MossProcessClient",
    "MossProcessTimeoutError",
]
