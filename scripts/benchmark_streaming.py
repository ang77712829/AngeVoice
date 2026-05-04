#!/usr/bin/env python3
"""Benchmark AngeVoice HTTP and WebSocket latency.

The script can also compare another WebSocket service, for example:

  python scripts/benchmark_streaming.py \
    --angevoice-http http://127.0.0.1:8101 \
    --angevoice-ws ws://127.0.0.1:8101/ws/v1/tts \
    --compare-ws ws://127.0.0.1:8000 \
    --compare-name gesla-kokoro-zh-streaming

Notes:
- AngeVoice WS protocol expects the initial payload without a type field.
- Some third-party services use a different protocol; use --compare-mode gesla for
  a common payload shape from kokoro-zh-streaming README.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass

import websockets

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


DEFAULT_TEXT = (
    "AngeVoice 是基于 Kokoro v1.1 模型构建的中文 TTS 服务，"
    "这个脚本用于测试首包延迟、总耗时和流式段落数量。"
)


@dataclass
class RunResult:
    ok: bool
    first_audio_ms: float | None
    total_ms: float
    chunks: int
    error: str | None = None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = min(len(values) - 1, max(0, round((len(values) - 1) * p)))
    return values[k]


def summarize(name: str, results: list[RunResult]) -> None:
    ok = [r for r in results if r.ok]
    first = [r.first_audio_ms for r in ok if r.first_audio_ms is not None]
    total = [r.total_ms for r in ok]
    print(f"\n== {name} ==")
    print(f"runs: {len(results)}, ok: {len(ok)}, failed: {len(results) - len(ok)}")
    if first:
        print(f"first audio ms: avg={statistics.mean(first):.1f}, p50={percentile(first, .50):.1f}, p95={percentile(first, .95):.1f}")
    if total:
        print(f"total ms:       avg={statistics.mean(total):.1f}, p50={percentile(total, .50):.1f}, p95={percentile(total, .95):.1f}")
    if ok:
        print(f"chunks:         avg={statistics.mean([r.chunks for r in ok]):.1f}")
    failures = [r.error for r in results if not r.ok and r.error]
    if failures:
        print("sample error:", failures[0])


async def bench_angevoice_ws(url: str, text: str, voice: str, speed: float) -> RunResult:
    started = time.perf_counter()
    first_audio = None
    chunks = 0
    try:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({"text": text, "voice": voice, "speed": speed, "format": "pcm_s16le", "binary": False}, ensure_ascii=False))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
                if isinstance(raw, bytes):
                    chunks += 1
                    if first_audio is None:
                        first_audio = time.perf_counter()
                    continue
                msg = json.loads(raw)
                if msg.get("type") == "audio":
                    chunks += 1
                    if first_audio is None:
                        first_audio = time.perf_counter()
                if msg.get("type") in {"done", "cancelled", "error"}:
                    if msg.get("type") == "error":
                        return RunResult(False, None, (time.perf_counter() - started) * 1000, chunks, msg.get("message"))
                    break
        return RunResult(True, (first_audio - started) * 1000 if first_audio else None, (time.perf_counter() - started) * 1000, chunks)
    except Exception as exc:
        return RunResult(False, None, (time.perf_counter() - started) * 1000, chunks, str(exc))


async def bench_compare_ws(url: str, text: str, voice: str, speed: float, mode: str) -> RunResult:
    started = time.perf_counter()
    first_audio = None
    chunks = 0
    try:
        async with websockets.connect(url, max_size=None) as ws:
            if mode == "gesla":
                payload = {"type": "tts", "text": text, "speed": speed, "reference_id": voice, "sample_rate": 24000}
            else:
                payload = {"text": text, "voice": voice, "speed": speed}
            await ws.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
                if isinstance(raw, bytes):
                    chunks += 1
                    if first_audio is None:
                        first_audio = time.perf_counter()
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                msg_type = msg.get("type", "")
                if msg_type in {"audio", "audio_pcm", "audio_chunk"} or "data" in msg:
                    chunks += 1
                    if first_audio is None:
                        first_audio = time.perf_counter()
                if msg_type in {"done", "complete", "completed", "error"}:
                    if msg_type == "error":
                        return RunResult(False, None, (time.perf_counter() - started) * 1000, chunks, msg.get("message"))
                    break
        return RunResult(True, (first_audio - started) * 1000 if first_audio else None, (time.perf_counter() - started) * 1000, chunks)
    except Exception as exc:
        return RunResult(False, None, (time.perf_counter() - started) * 1000, chunks, str(exc))


def bench_angevoice_http(base_url: str, text: str, voice: str, speed: float) -> RunResult:
    if requests is None:
        return RunResult(False, None, 0.0, 0, "requests not installed")
    started = time.perf_counter()
    try:
        resp = requests.post(
            base_url.rstrip("/") + "/v1/audio/speech",
            json={"model": "kokoro", "input": text, "voice": voice, "speed": speed, "response_format": "wav"},
            timeout=120,
        )
        elapsed = (time.perf_counter() - started) * 1000
        if not resp.ok:
            return RunResult(False, None, elapsed, 0, resp.text[:300])
        return RunResult(True, elapsed, elapsed, 1)
    except Exception as exc:
        return RunResult(False, None, (time.perf_counter() - started) * 1000, 0, str(exc))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark AngeVoice and optional comparison TTS service")
    parser.add_argument("--angevoice-http", default="http://127.0.0.1:8101")
    parser.add_argument("--angevoice-ws", default="ws://127.0.0.1:8101/ws/v1/tts")
    parser.add_argument("--compare-ws", default="")
    parser.add_argument("--compare-name", default="compare")
    parser.add_argument("--compare-mode", choices=["generic", "gesla"], default="gesla")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--voice", default="zm_010")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    http_results = [bench_angevoice_http(args.angevoice_http, args.text, args.voice, args.speed) for _ in range(args.runs)]
    ws_results = [await bench_angevoice_ws(args.angevoice_ws, args.text, args.voice, args.speed) for _ in range(args.runs)]
    summarize("AngeVoice HTTP", http_results)
    summarize("AngeVoice WebSocket", ws_results)

    if args.compare_ws:
        compare_results = [await bench_compare_ws(args.compare_ws, args.text, args.voice, args.speed, args.compare_mode) for _ in range(args.runs)]
        summarize(args.compare_name, compare_results)


if __name__ == "__main__":
    asyncio.run(main())
