#!/usr/bin/env python3
"""Analyze AngeVoice/MOSS WAV quality for clipping and long-silence issues."""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

import numpy as np


def _read_wav(path: Path) -> tuple[np.ndarray, int, int]:
    with wave.open(str(path), "rb") as wf:
        channels = int(wf.getnchannels())
        sample_rate = int(wf.getframerate())
        sample_width = int(wf.getsampwidth())
        frames = int(wf.getnframes())
        raw = wf.readframes(frames)
    if sample_width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sample_width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"unsupported WAV sample width: {sample_width} bytes")
    if channels > 1:
        data = data.reshape(-1, channels)
    else:
        data = data.reshape(-1, 1)
    return data, sample_rate, channels


def _silence_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    i = 0
    n = int(mask.size)
    while i < n:
        if not bool(mask[i]):
            i += 1
            continue
        start = i
        while i < n and bool(mask[i]):
            i += 1
        runs.append((start, i))
    return runs


def analyze(path: Path, *, silence_db: float = -45.0, long_silence_ms: float = 1000.0) -> dict:
    audio, sample_rate, channels = _read_wav(path)
    if audio.size == 0:
        return {"path": str(path), "ok": False, "reason": "empty audio"}
    mono_env = np.max(np.abs(audio), axis=1)
    threshold = float(10.0 ** (float(silence_db) / 20.0))
    silence_mask = mono_env <= threshold
    runs = _silence_runs(silence_mask)
    long_threshold = int(sample_rate * max(0.0, float(long_silence_ms)) / 1000.0)
    long_runs = [(s, e) for s, e in runs if e - s >= long_threshold]
    max_run = max((e - s for s, e in runs), default=0)
    return {
        "path": str(path),
        "ok": True,
        "duration_seconds": round(float(audio.shape[0] / sample_rate), 3),
        "sample_rate": sample_rate,
        "channels": channels,
        "samples": int(audio.shape[0]),
        "rms_dbfs": round(float(20.0 * np.log10(max(1e-12, np.sqrt(np.mean(audio ** 2))))), 3),
        "peak_dbfs": round(float(20.0 * np.log10(max(1e-12, float(np.max(np.abs(audio)))))), 3),
        "clip_ratio": round(float(np.mean(np.abs(audio) >= 0.999)), 8),
        "silence_db": silence_db,
        "silence_ratio": round(float(np.mean(silence_mask)), 6),
        "long_silence_count": len(long_runs),
        "max_silence_ms": round(float(max_run * 1000.0 / sample_rate), 3),
        "long_silence_ranges": [
            {"start": round(s / sample_rate, 3), "end": round(e / sample_rate, 3), "ms": round((e - s) * 1000.0 / sample_rate, 1)}
            for s, e in long_runs[:50]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a WAV file for TTS quality issues.")
    parser.add_argument("wav", type=Path)
    parser.add_argument("--silence-db", type=float, default=-45.0)
    parser.add_argument("--long-silence-ms", type=float, default=1000.0)
    args = parser.parse_args()
    print(json.dumps(analyze(args.wav, silence_db=args.silence_db, long_silence_ms=args.long_silence_ms), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
