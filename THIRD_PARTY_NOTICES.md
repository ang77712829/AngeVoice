# Third-Party Notices

AngeVoice framework code is released under the Apache License 2.0. See `LICENSE`.

AngeVoice integrates upstream models, runtime source and dependencies. Matching the core upstream license simplifies distribution, but upstream copyrights, notices and asset licenses remain with their respective authors.

## Core Apache-2.0 integrations

### Kokoro

- Upstream model family: Kokoro / Kokoro-82M
- Default model: `hexgrad/Kokoro-82M-v1.1-zh`
- Upstream license: Apache License 2.0, as declared by the upstream model card
- Role: default Chinese TTS engine/model integration

### MOSS-TTS-Nano / OpenMOSS

- Upstream project: `OpenMOSS/MOSS-TTS-Nano`
- Upstream license: Apache License 2.0
- Upstream copyright: OpenMOSS Team, Fudan University, SII and MOSI, as stated by the upstream license file
- Role: MOSS-TTS-Nano CPU/CUDA synthesis, preset voices and reference-audio cloning

### ZipVoice / ZipVoice-Distill

- Upstream project and model: `k2-fsa/ZipVoice`
- Upstream license: Apache License 2.0
- Role: zero-shot voice cloning on CPU through ONNX INT8 assets and on supported GPU deployments
- Vendored component: upstream Python inference source under `vendor/ZipVoice/` with its upstream `LICENSE` preserved
- Runtime assets: ZipVoice model assets are downloaded into the operator's persistent model directory when selected or first used

## Other third-party runtime assets

### Vocos mel-24khz vocoder

ZipVoice synthesis uses a Vocos vocoder asset retrieved at runtime.

- Upstream model: `charactr/vocos-mel-24khz`
- Upstream license: MIT, as declared by the upstream model repository
- Runtime assets: `config.yaml` and `pytorch_model.bin`
- Persistent location: `/app/models/zipvoice/vocos-mel-24khz/`

## Distribution notes

Docker images may download or contain upstream runtime code or model assets. When redistributing source archives, Docker images or derived packages, preserve `LICENSE`, this notice, bundled upstream license files, and any license notices required by runtime assets. AngeVoice does not claim ownership of third-party model weights, voices, tokenizer assets, training data or upstream runtime code.
