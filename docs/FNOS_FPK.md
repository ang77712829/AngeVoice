# fnOS / FPK 部署

AngeVoice 的 fnOS 包使用一个固定的 `app/docker/docker-compose.yaml`。安装、设置或升级向导直接提供 `COMPOSE_PROFILES=cpu | gpu | legacy-gpu`；fnOS `docker-project` 在创建容器前依据该值选择对应服务和镜像，不依赖回调在容器创建后再改写镜像。

## 运行模式

| 运行模式 | 默认镜像 | 适用设备 | ZipVoice 路线 |
| --- | --- | --- | --- |
| `cpu` | `ghcr.io/ang77712829/angevoice-cpu:latest` | x86_64 / ARM64 无 GPU NAS | CPU ONNX INT8 |
| `gpu` | `ghcr.io/ang77712829/angevoice-gpu:latest` | NVIDIA x86_64，包含 Tesla P4 | CUDA，不可用时回退 CPU |
| `legacy-gpu` | `ghcr.io/ang77712829/angevoice-legacy-gpu:latest` | 标准 GPU 镜像无法运行的兼容环境 | 保守 provider 配置 |

FPK 内只包含一个 Compose 文件；其中三个 profile 服务共用相同的端口、管理后台、模型目录、Voice Profile、输出、凭据与运行配置持久化契约。用户只需在安装向导选择一种运行模式。

## 安装向导选项

安装或配置页面可设置：

- 运行模式：CPU / 标准 GPU / Legacy GPU；
- 服务端口；
- 管理员用户名与首次进入密码；
- 模型下载源。

首次进入默认可使用 `admin / admin123`。公网暴露服务前，请在管理后台修改管理员凭据；修改后的密码仅以哈希形式保存。

## 持久化数据

安装、重启、模式切换或升级时，应保留以下目录：

```text
models/       模型资产
prompts/      Voice Profiles 与参考音频
outputs/      输出音频
credentials/  管理员哈希凭据与 API Key
config/       运行配置
logs/         日志与诊断资料
```

三个运行模式挂载相同的数据目录，因此保存的音色、API Key 与后台设置可以继续使用。

## 使用说明

- 有 NVIDIA GPU 时优先选择标准 GPU 模式；只有标准镜像无法启动或运行不兼容时再使用 Legacy GPU。
- CPU 镜像提供 amd64 与 arm64 架构；GPU 与 Legacy GPU 面向 NVIDIA x86_64 环境。
- 模型文件不包含在 FPK 中，首次使用模型时会下载到持久化目录。
- 实际 Provider、自动回退原因、资源占用与最近合成性能可在状态和诊断页面查看。
