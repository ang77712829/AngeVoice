# License and Attribution Compliance

AngeVoice framework code is released under the Apache License 2.0. See `../LICENSE`.

The three core model/runtime integrations used by AngeVoice — Kokoro, MOSS-TTS-Nano and ZipVoice — are also supplied upstream under Apache License 2.0 terms. This alignment simplifies public distribution, while upstream attribution and any bundled license notices must still be preserved. Other dependencies and runtime-downloaded assets remain subject to their own licenses.

## Core upstream integrations

| Component | Upstream source | License | Use in AngeVoice |
| --- | --- | --- | --- |
| Kokoro / Kokoro-82M v1.1 Chinese | `hexgrad/Kokoro-82M-v1.1-zh` | Apache License 2.0 | Default Chinese TTS model integration |
| MOSS-TTS-Nano | `OpenMOSS/MOSS-TTS-Nano` | Apache License 2.0 | CPU/CUDA synthesis and reference-audio cloning runtime |
| ZipVoice / ZipVoice-Distill | `k2-fsa/ZipVoice` | Apache License 2.0 | Zero-shot voice cloning and vendored inference source |

The repository preserves the vendored ZipVoice upstream license at `../vendor/ZipVoice/LICENSE`. AngeVoice does not claim ownership of third-party model weights, voices, tokenizer assets, training data or upstream runtime code.

## Other runtime assets

ZipVoice may retrieve the Vocos `charactr/vocos-mel-24khz` vocoder assets at runtime. These assets are recorded in `../THIRD_PARTY_NOTICES.md` and remain under their upstream MIT terms.

## Docker image redistribution

Dockerfiles copy AngeVoice legal material into the image and preserve bundled/downloaded upstream license material where supplied. Redistributors of prebuilt images or derived packages should retain:

```text
/app/LICENSE
/app/THIRD_PARTY_NOTICES.md
/app/ACKNOWLEDGEMENTS.md
/app/licenses/
```

## Release checklist

Before publishing a source release, wheel, Docker image or fnOS/FPK package:

1. Keep the AngeVoice Apache License 2.0 `LICENSE` file.
2. Keep `THIRD_PARTY_NOTICES.md` and `ACKNOWLEDGEMENTS.md`.
3. Preserve upstream license files included by bundled or downloaded third-party projects.
4. Keep Kokoro, MOSS-TTS-Nano and ZipVoice attribution visible in public documentation.
5. Do not claim ownership of third-party model assets or remove license terms for non-Apache dependencies such as Vocos.

## Related files

- `../LICENSE`
- `../THIRD_PARTY_NOTICES.md`
- `../ACKNOWLEDGEMENTS.md`
- `../licenses/README.md`
- `../vendor/ZipVoice/LICENSE`
