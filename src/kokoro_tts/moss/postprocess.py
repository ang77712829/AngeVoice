"""MOSS 音频后处理工具。

目标是把削峰、归一化、静音片段、流式分片等纯逻辑从主引擎中拆出，
便于单独测试，也方便后续继续优化听感。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

import numpy as np


@dataclass(frozen=True)
class MossAudioQuality:
    """一次波形后处理产生的质量指标。"""

    max_abs_before: float
    scale: float
    max_abs_after: float
    clip_ratio: float
    repaired_impulses: int = 0
    dc_offset_before: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "max_abs_before": round(self.max_abs_before, 6),
            "scale": round(self.scale, 6),
            "max_abs_after": round(self.max_abs_after, 6),
            "clip_ratio": round(self.clip_ratio, 6),
            "repaired_impulses": float(self.repaired_impulses),
            "dc_offset_before": round(self.dc_offset_before, 6),
        }


def normalize_waveform(
    waveform,
    *,
    channels: int,
    gain: float = 1.0,
    target_peak: float = 0.78,
    peak_normalize_enabled: bool = True,
    declick_enabled: bool = True,
    edge_fade_samples: int = 0,
) -> tuple[np.ndarray, MossAudioQuality]:
    """整理 MOSS 输出波形，并用温和峰值/去爆音保护降低失真风险。

    OpenMOSS 在部分参考音频、CUDA/ONNX 组合和小句子流式合成时，偶尔会
    出现很窄的瞬态尖峰或片段边缘不连续。它们不一定达到数字削波，听感上
    却会表现为“噗”“刺”“电流音”。这里做三件保守处理：

    1. 去除极小 DC offset；
    2. 只修复明显孤立的单点/双点脉冲，不改变正常声波主体；
    3. 对片段头尾做 1~3ms 的短淡入淡出，减少拼接爆音。
    """

    audio = np.asarray(waveform, dtype=np.float32)
    if audio.ndim == 0:
        audio = audio.reshape(1)
    elif audio.ndim > 2:
        audio = audio.reshape(-1, audio.shape[-1])
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)

    expected_channels = max(1, int(channels))
    if int(audio.shape[1]) != expected_channels:
        if int(audio.shape[1]) > expected_channels:
            audio = audio.mean(axis=1, keepdims=True)
        if expected_channels > int(audio.shape[1]):
            audio = np.repeat(audio[:, :1], expected_channels, axis=1)

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32, copy=False)
    dc_offset_before = float(np.mean(audio)) if audio.size else 0.0
    if audio.size:
        audio = audio - np.mean(audio, axis=0, keepdims=True).astype(np.float32)

    gain = float(gain)
    if gain != 1.0:
        audio = audio * gain

    repaired_impulses = 0
    if bool(declick_enabled):
        audio, repaired_impulses = _repair_impulses(audio)

    edge_fade_samples = max(0, int(edge_fade_samples))
    if edge_fade_samples > 0:
        audio = _apply_edge_fade(audio, edge_fade_samples)

    max_abs_before = float(np.max(np.abs(audio))) if audio.size else 0.0
    target_peak = float(target_peak)
    scale = 1.0
    if bool(peak_normalize_enabled) and max_abs_before > target_peak > 0:
        scale = target_peak / max_abs_before
        audio = audio * scale

    # tanh 软限制只作用在保护阈值以上的极端峰值，比硬 clip 更不容易产生爆音。
    if target_peak > 0 and audio.size:
        soft_limit = min(0.98, max(0.5, target_peak * 1.08))
        over = np.abs(audio) > soft_limit
        if np.any(over):
            signed = np.sign(audio[over])
            excess = (np.abs(audio[over]) - soft_limit) / max(1e-6, 1.0 - soft_limit)
            audio[over] = signed * (soft_limit + (1.0 - soft_limit) * np.tanh(excess))

    clipped = np.clip(audio, -1.0, 1.0).astype(np.float32, copy=False)
    clip_ratio = float(np.mean(np.abs(clipped) >= 0.999)) if clipped.size else 0.0
    quality = MossAudioQuality(
        max_abs_before=max_abs_before,
        scale=scale,
        max_abs_after=float(np.max(np.abs(clipped))) if clipped.size else 0.0,
        clip_ratio=clip_ratio,
        repaired_impulses=int(repaired_impulses),
        dc_offset_before=dc_offset_before,
    )
    return clipped, quality


def _repair_impulses(audio: np.ndarray) -> tuple[np.ndarray, int]:
    """修复孤立瞬态尖峰，避免把正常辅音/爆破音抹掉。"""

    if audio.shape[0] < 3:
        return audio, 0
    repaired = np.array(audio, copy=True)
    total = 0
    for ch in range(repaired.shape[1]):
        y = repaired[:, ch]
        neighbor_avg = 0.5 * (y[:-2] + y[2:])
        residual = y[1:-1] - neighbor_avg
        # 同时要求残差大、绝对振幅大、相邻点没有同向大振幅，尽量只抓“针刺”。
        mask = (np.abs(residual) > 0.42) & (np.abs(y[1:-1]) > 0.55)
        if not np.any(mask):
            continue
        idx = np.nonzero(mask)[0] + 1
        y[idx] = neighbor_avg[mask]
        total += int(idx.size)
    return repaired, total


def _apply_edge_fade(audio: np.ndarray, fade_samples: int) -> np.ndarray:
    if audio.shape[0] <= 2 or fade_samples <= 0:
        return audio
    n = min(int(fade_samples), max(1, audio.shape[0] // 8))
    if n <= 1:
        return audio
    faded = np.array(audio, copy=True)
    fade_in = np.linspace(0.0, 1.0, n, dtype=np.float32).reshape(-1, 1)
    fade_out = np.linspace(1.0, 0.0, n, dtype=np.float32).reshape(-1, 1)
    faded[:n] *= fade_in
    faded[-n:] *= fade_out
    return faded


def split_waveform_for_stream(waveform, *, sample_rate: int, chunk_seconds: float, min_floor: float) -> Iterator[np.ndarray]:
    """按流式输出块大小切分波形。"""

    audio = np.asarray(waveform, dtype=np.float32)
    if audio.size == 0:
        return
    max_seconds = max(float(min_floor), float(chunk_seconds))
    max_samples = max(1, int(int(sample_rate) * max_seconds))
    total_samples = int(audio.shape[0])
    for start in range(0, total_samples, max_samples):
        yield np.ascontiguousarray(audio[start : start + max_samples])


def concat_waveforms(waveforms: Iterable[np.ndarray]) -> np.ndarray:
    """合并非空波形。"""

    parts = [item for item in waveforms if getattr(item, "size", 0)]
    if not parts:
        raise RuntimeError("MOSS: all segments produced empty audio")
    return np.concatenate(parts)


def silence_array(seconds: float, *, sample_rate: int, channels: int) -> np.ndarray:
    """生成指定时长的静音波形。"""

    samples = max(0, int(int(sample_rate) * max(0.0, float(seconds))))
    expected_channels = max(1, int(channels))
    if samples <= 0:
        return np.zeros((0, expected_channels), dtype=np.float32)
    return np.zeros((samples, expected_channels), dtype=np.float32)
