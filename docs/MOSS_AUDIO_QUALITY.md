# MOSS 音频听感与小智播放排障

本页记录 AngeVoice v2.6.4.6 之后对 MOSS 听感的默认策略。

## 默认策略：低延迟保守流式

MOSS 的 WebSocket 默认启用官方逐帧实时解码，以降低 Web/小智首包等待：

```bash
MOSS_REALTIME_STREAMING_DECODE=true
```

逐帧实时解码可以降低首包延迟，但在部分 CUDA/ONNX 组合、参考音频和小喇叭播放链路上，可能放大 chunk 边界不连续，表现为：

- 电流音；
- “噗”“刺”的爆音；
- 片段之间卡顿或断裂；
- 小智播放时比 Web 端更明显的失真。

如遇上述问题，可把 `MOSS_REALTIME_STREAMING_DECODE=false`，让 AngeVoice 先生成更完整的高质量 chunk，再按固定时长切成小包推送。这样延迟更高，但听感可能更稳。

## 推荐参数

```bash
MOSS_REALTIME_STREAMING_DECODE=true
MOSS_OUTPUT_PEAK_NORMALIZE_ENABLED=true
MOSS_OUTPUT_TARGET_PEAK=0.78
MOSS_OUTPUT_GAIN=0.90
MOSS_OUTPUT_DECLICK_ENABLED=true
MOSS_OUTPUT_EDGE_FADE_MS=2
```

这些参数会做温和后处理：

- 去除极小 DC offset；
- 降低峰值，避免小喇叭/Opus 链路爆音；
- 修复孤立瞬态尖峰；
- 在片段头尾做短淡入淡出，减少拼接噪声。

## 如果仍有卡顿或爆音

优先使用更保守的分段和分包：

```bash
MOSS_SEGMENT_LENGTH=140
MOSS_STREAM_CHUNK_SECONDS=0.42
MOSS_STREAM_QUEUE_MAX_ITEMS=8
MOSS_OUTPUT_TARGET_PEAK=0.78
```

`MOSS_SEGMENT_LENGTH` 只影响 MOSS，不影响 Kokoro。长文本段数过多时，段间拼接会增加卡顿、爆音和语气断裂概率，可在 140~180 之间尝试。

## MOSS 文本规则路由和日期上下文

MOSS 文本清洗现在显式以 `model=moss-*` 调用 AngeVoice 中文规则，避免误套 Kokoro 专用的替换字典。也就是说，Kokoro 仍可用较激进的同音字提示修正多音字，而 MOSS 只应用确认有效的保底规则和通用文本规范化，减少把“重庆、银行、调整”等词误改成 Kokoro 提示字的风险。

短日期会按上下文判断：`4.20号`、`活动在4.20开始`、`4.20更新` 会读作“四月二十日”；裸小数、版本号和金额不会无脑改日期，例如 `版本4.20` 保持版本/小数语义，`4.20元` 仍按金额读。

不建议把 `MOSS-Audio-Tokenizer` 直接替换进 MOSS-TTS-Nano。本项目当前只接入与 MOSS-TTS-Nano ONNX runtime 配套的 tokenizer/codec，避免 token 空间或 codec codebook 不匹配导致音质下降或不可用。

## 低延迟实时模式修正

`MOSS_REALTIME_STREAMING_DECODE=true` 是推荐默认值，适合小智、WebSocket 和 NAS 低延迟播放；如果出现边界噪声或卡顿，可回退为 `false`。

需要注意的是，实时模式会产生很多很小的音频块。如果对每个小块都做 1~3ms 的 edge fade，会在播放端形成连续的微小音量缺口，听起来像卡顿、抖动或爆音。因此当前实现只在整段/整块输出上使用边缘淡入淡出，实时逐帧小块只保留去 DC、去孤立脉冲和峰值保护，不再逐小块 fade。

如需最大听感稳定性、可以接受更慢首包，可手动设置：

```env
MOSS_REALTIME_STREAMING_DECODE=false
```
