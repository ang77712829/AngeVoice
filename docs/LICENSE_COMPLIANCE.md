# 许可证与署名合规

AngeVoice 框架代码按 Apache License 2.0 发布，许可证见 `../LICENSE`，项目版权与署名信息记录在 `../NOTICE`。

AngeVoice 使用的三个核心模型/运行时集成 Kokoro、MOSS-TTS-Nano 与 ZipVoice，上游同样按 Apache License 2.0 提供。许可证兼容降低了公开分发复杂度，但仍必须保留上游署名和随包许可证声明。其他依赖以及运行时下载的资产仍以各自上游许可证为准。

## 核心上游集成

| 组件 | 上游来源 | 许可证 | 在 AngeVoice 中的用途 |
| --- | --- | --- | --- |
| Kokoro / Kokoro-82M v1.1 Chinese | `hexgrad/Kokoro-82M-v1.1-zh` | Apache License 2.0 | 默认中文 TTS 模型集成 |
| MOSS-TTS-Nano | `OpenMOSS/MOSS-TTS-Nano` | Apache License 2.0 | CPU/CUDA 合成与参考音频克隆运行时 |
| ZipVoice / ZipVoice-Distill | `k2-fsa/ZipVoice` | Apache License 2.0 | 零样本音色克隆与随包推理源码 |

仓库在 `../vendor/ZipVoice/LICENSE` 保留了随包 ZipVoice 的上游许可证。AngeVoice 不声明拥有第三方模型权重、音色、分词资产、训练数据或上游运行时代码的所有权。

## 其他运行时资产

ZipVoice 可能在运行时获取 Vocos `charactr/vocos-mel-24khz` 声码器资产。这些资产记录在 `../THIRD_PARTY_NOTICES.md`，仍遵循其上游 MIT 条款。

## Docker 镜像再分发

Dockerfile 会将 AngeVoice 法务材料复制到镜像中，并在可用时保留随包或下载得到的上游许可证材料。分发预构建镜像或派生包时应保留：

```text
/app/LICENSE
/app/NOTICE
/app/THIRD_PARTY_NOTICES.md
/app/ACKNOWLEDGEMENTS.md
/app/licenses/
```

## 发布检查清单

发布源码包、wheel、Docker 镜像或 fnOS/FPK 包前，请确认：

1. 保留 AngeVoice 的 Apache License 2.0 `LICENSE` 文件。
2. 保留 AngeVoice 版权与署名 `NOTICE` 文件。
3. 保留 `THIRD_PARTY_NOTICES.md` 与 `ACKNOWLEDGEMENTS.md`。
4. 保留随包或运行时下载第三方项目附带的上游许可证文件。
5. 在公开文档中保留 Kokoro、MOSS-TTS-Nano 与 ZipVoice 署名。
6. 不声明拥有第三方模型资产，也不移除 Vocos 等非 Apache 依赖的许可证条款。

## 相关文件

- `../LICENSE`
- `../NOTICE`
- `../THIRD_PARTY_NOTICES.md`
- `../ACKNOWLEDGEMENTS.md`
- `../licenses/README.md`
- `../vendor/ZipVoice/LICENSE`
