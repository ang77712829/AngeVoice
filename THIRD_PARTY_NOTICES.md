# Third-Party Notices

AngeVoice project code is licensed under the MIT License. See `LICENSE`.

AngeVoice integrates third-party models, runtimes and dependencies. Those components keep their own upstream licenses and are not relicensed by AngeVoice.

## Kokoro

AngeVoice uses Kokoro / Kokoro-82M v1.1 Chinese model support.

- Upstream model family: Kokoro / Kokoro-82M
- Default model: `hexgrad/Kokoro-82M-v1.1-zh`
- Upstream license: Apache License 2.0, as declared by the upstream model card or repository
- Role: default Chinese TTS engine/model integration

AngeVoice does not claim ownership of Kokoro model weights, voices, training data, upstream runtime components or upstream model assets.

## MOSS-TTS-Nano / OpenMOSS

AngeVoice integrates MOSS-TTS-Nano through the official OpenMOSS runtime code.

- Upstream project: `OpenMOSS/MOSS-TTS-Nano`
- Upstream license: Apache License 2.0
- Upstream copyright: OpenMOSS Team, Fudan University, SII and MOSI, as stated by the upstream license file
- Role: optional MOSS-TTS-Nano CPU/CUDA engine, preset voice synthesis and reference-audio cloning support

AngeVoice does not claim ownership of MOSS-TTS-Nano model weights, tokenizer weights, ONNX model assets, training data, official runtime code or other upstream OpenMOSS assets.

## Docker images

Some AngeVoice Docker images may download or include third-party runtime code and model assets during build or runtime, including OpenMOSS/MOSS-TTS-Nano runtime code and Hugging Face model files.

Redistributors of prebuilt images should preserve upstream license files and attribution notices inside the image and in accompanying documentation.

## No relicensing of upstream assets

The MIT license in this repository applies to AngeVoice project code only. It does not relicense Kokoro, MOSS-TTS-Nano, their model weights, voices, tokenizer weights, training data, upstream runtime code or any other third-party assets.
