# AngeVoice Demo

在线演示文件夹，部署到 [ModelScope 魔搭创空间](https://modelscope.cn/studios/ange111/AngeVoice)。

## 功能

- 🧠 双引擎切换：Kokoro v1.1 Chinese / MOSS-TTS-Nano CPU
- 🎵 20+ 中文预置音色 + MOSS 音色克隆
- ⚡ 语速调节（Kokoro）
- 💡 示例文本一键试听

## 在线体验

🔗 https://modelscope.cn/studios/ange111/AngeVoice

## 本地运行

```bash
# 在仓库根目录
python hf-demo/app.py
```

访问 http://localhost:7860

## 部署到 ModelScope 魔搭

1. Fork 或推送代码到你的 GitHub 仓库
2. 在魔搭创空间创建 Docker 类型空间
3. 连接到你的仓库
4. 平台会自动检测根目录的 `Dockerfile` 并构建

详见 [DEPLOY_MODELSCOPE.md](DEPLOY_MODELSCOPE.md)。

## 文件说明

```
hf-demo/
├── app.py              # Gradio 演示界面
├── Dockerfile          # HF Spaces / ModelScope 构建文件（内容与根目录一致）
├── README.md           # 本文件
└── DEPLOY_MODELSCOPE.md # 魔搭部署详细指南
```

根目录的 `Dockerfile` 是平台构建入口，引用 `hf-demo/app.py`。
