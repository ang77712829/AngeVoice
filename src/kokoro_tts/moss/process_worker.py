"""MOSS 进程级隔离 worker。

CUDA/ONNX Runtime 偶发硬卡死时，线程池无法真正取消底层调用。
本模块把 MOSS 推理放入独立子进程，主进程超时后可以终止子进程，
从而避免主 Web 服务被卡死的 runtime 拖住。
"""

from __future__ import annotations

from contextlib import suppress
import multiprocessing as mp
import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Callable, Iterator


@dataclass(frozen=True)
class MossWorkerResult:
    """子进程返回给主进程的一条消息。"""

    request_id: str
    kind: str
    payload: object


class MossProcessTimeoutError(TimeoutError):
    """MOSS 子进程请求超时。"""


class MossProcessClient:
    """持有一个 MOSS worker 子进程，并提供同步请求/流式请求接口。"""

    def __init__(self, *, config, provider: str, engine_id: str, logger=None):
        self.config = config
        self.provider = provider
        self.engine_id = engine_id
        self.logger = logger
        self._ctx = mp.get_context("spawn")
        self._command_queue = None
        self._result_queue = None
        self._process: mp.Process | None = None
        self._lifecycle_lock = threading.RLock()
        # One MOSS runtime must have only one result-queue consumer. This mirrors
        # the generic worker contract used by Kokoro/ZipVoice and prevents
        # concurrent HTTP/WebSocket requests from stealing each other's frames.
        self._request_lock = threading.RLock()

    @property
    def alive(self) -> bool:
        process = self._process
        return bool(process is not None and process.is_alive())

    @property
    def pid(self) -> int | None:
        """PID of the live isolated MOSS worker, when available."""

        return self._process.pid if self.alive and self._process is not None else None

    def start(self) -> None:
        """按需启动 worker 子进程。"""

        with self._lifecycle_lock:
            if self.alive:
                return
            # A killed or cancelled worker may leave commands/results behind.
            # A new queue generation makes the next wake-up deterministic.
            self._command_queue = self._ctx.Queue()
            self._result_queue = self._ctx.Queue()
            self._process = self._ctx.Process(
                target=_worker_main,
                args=(self.config, self.provider, self.engine_id, self._command_queue, self._result_queue),
                name=f"{self.engine_id}-process-worker",
                daemon=True,
            )
            self._process.start()

    def close(self, *, kill: bool = False) -> None:
        """关闭 worker；强制取消可绕过请求锁中断卡死推理。"""

        if kill:
            with self._lifecycle_lock:
                self._close_locked(kill=True)
            return
        with self._request_lock, self._lifecycle_lock:
            self._close_locked(kill=False)

    def _close_locked(self, *, kill: bool) -> None:
        process = self._process
        if process is None:
            self._discard_queues()
            return
        grace = float(getattr(self.config, "moss_process_kill_grace_seconds", 2.0) or 2.0)
        if process.is_alive() and not kill:
            try:
                if self._command_queue is not None:
                    self._command_queue.put_nowait((uuid.uuid4().hex, "shutdown", {}))
            except Exception:
                pass
            process.join(timeout=grace)
        if process.is_alive():
            process.terminate()
            process.join(timeout=grace)
        if process.is_alive():
            process.kill()
            process.join(timeout=min(1.0, grace))
        self._process = None
        self._discard_queues()

    def request(self, command: str, payload: dict | None = None, *, timeout: float) -> object:
        """发送一次普通请求，并等待单个结果。"""

        with self._request_lock:
            request_id = self._send(command, payload or {})
            result = self._wait_for(request_id, timeout=timeout)
            if result.kind == "error":
                raise RuntimeError(str(result.payload))
            if result.kind != "result":
                raise RuntimeError(f"MOSS worker returned unexpected message: {result.kind}")
            return result.payload

    def stream(
        self,
        command: str,
        payload: dict | None = None,
        *,
        timeout: float,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Iterator[dict]:
        """发送一次流式请求；同一 Worker 的结果消费严格串行。"""

        with self._request_lock:
            request_id = self._send(command, payload or {})
            idle_timeout = max(1.0, float(timeout))
            deadline = time.monotonic() + idle_timeout
            while True:
                if cancel_check is not None:
                    try:
                        if cancel_check():
                            self.close(kill=True)
                            return
                    except Exception:
                        if self.logger:
                            self.logger.debug("MOSS worker cancel_check 失败", exc_info=True)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.close(kill=True)
                    raise MossProcessTimeoutError(f"MOSS worker stream idle timed out after {timeout}s")
                process = self._process
                if process is not None and not process.is_alive():
                    raise RuntimeError(f"MOSS worker exited unexpectedly with code {process.exitcode}")
                try:
                    raw = self._require_result_queue().get(timeout=min(0.2, remaining))
                except queue.Empty:
                    continue
                result = MossWorkerResult(*raw)
                if result.request_id != request_id:
                    if self.logger:
                        self.logger.debug("丢弃过期 MOSS worker 流式消息：%s", result.request_id)
                    continue
                deadline = time.monotonic() + idle_timeout
                if result.kind == "event":
                    yield result.payload
                    continue
                if result.kind == "done":
                    return
                if result.kind == "error":
                    raise RuntimeError(str(result.payload))
                raise RuntimeError(f"MOSS worker returned unexpected stream message: {result.kind}")

    def _send(self, command: str, payload: dict) -> str:
        self.start()
        request_id = uuid.uuid4().hex
        if self._command_queue is None:
            raise RuntimeError("MOSS worker command queue is unavailable")
        self._command_queue.put((request_id, command, payload))
        return request_id

    def _wait_for(self, request_id: str, *, timeout: float) -> MossWorkerResult:
        deadline = time.monotonic() + max(0.01, float(timeout))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.close(kill=True)
                raise MossProcessTimeoutError(f"MOSS worker timed out after {timeout}s")
            process = self._process
            if process is not None and not process.is_alive():
                raise RuntimeError(f"MOSS worker exited unexpectedly with code {process.exitcode}")
            try:
                raw = self._require_result_queue().get(timeout=min(0.2, remaining))
            except queue.Empty:
                continue
            result = MossWorkerResult(*raw)
            if result.request_id == request_id:
                return result
            # 当前实现串行使用 worker。若看到非当前请求，直接丢弃并记录；
            # 这样可避免旧请求残留污染当前请求。
            if self.logger:
                self.logger.debug("丢弃过期 MOSS worker 消息：%s", result.request_id)

    def _require_result_queue(self):
        if self._result_queue is None:
            raise RuntimeError("MOSS worker result queue is unavailable")
        return self._result_queue

    def _discard_queues(self) -> None:
        result_queue = self._result_queue
        command_queue = self._command_queue

        if result_queue is not None:
            while True:
                try:
                    result_queue.get_nowait()
                except queue.Empty:
                    break
                except Exception:
                    break

        for managed_queue in (command_queue, result_queue):
            if managed_queue is None:
                continue
            with suppress(Exception):
                managed_queue.close()
            with suppress(Exception):
                managed_queue.join_thread()

        self._command_queue = None
        self._result_queue = None


def _worker_main(config, provider: str, engine_id: str, command_queue, result_queue) -> None:
    """子进程主循环。"""

    engine = None

    def ensure_engine():
        nonlocal engine
        if engine is None:
            from ..moss_engine import MossNanoEngine

            engine = MossNanoEngine(config, execution_provider=provider, engine_id=engine_id, process_isolation=False)
            engine.load()
        return engine

    while True:
        request_id, command, payload = command_queue.get()
        if command == "shutdown":
            try:
                if engine is not None:
                    engine.unload()
            finally:
                result_queue.put((request_id, "result", {"ok": True}))
            return
        try:
            current = ensure_engine()
            if command == "load":
                result_queue.put((request_id, "result", current.metadata()))
            elif command == "metadata":
                result_queue.put((request_id, "result", current.metadata()))
            elif command == "voices":
                result_queue.put((request_id, "result", current.get_voices()))
            elif command == "synthesize_array":
                result = current.synthesize_array(**payload)
                result_queue.put((request_id, "result", result))
            elif command == "synthesize_stream":
                for item in current.synthesize_stream(**payload):
                    result_queue.put((request_id, "event", item))
                result_queue.put((request_id, "done", None))
            elif command == "unload":
                current.unload()
                engine = None
                result_queue.put((request_id, "result", {"ok": True}))
            else:
                raise RuntimeError(f"未知 MOSS worker 命令：{command}")
        except BaseException as exc:  # noqa: BLE001 - 子进程必须把所有异常传回主进程
            result_queue.put((request_id, "error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
