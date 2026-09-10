# Third-party notices

The source code in this repository is licensed under the MIT License in `LICENSE`. The project installs and uses separately licensed software and model data; those works are not relicensed by this repository.

## Direct dependencies

| Component | Use | Declared license | Source |
| --- | --- | --- | --- |
| VoxCPM 2.0.3 and VoxCPM2 model | Speech synthesis and model weights | Apache License 2.0 | https://github.com/OpenBMB/VoxCPM and https://huggingface.co/openbmb/VoxCPM2 |
| PyTorch 2.14 | Tensor and CUDA runtime | Multiple permissive licenses; see its license and bundled notices | https://github.com/pytorch/pytorch/blob/main/LICENSE |
| Torchaudio 2.11 | VoxCPM audio dependency | BSD 2-Clause | https://github.com/pytorch/audio/blob/main/LICENSE |
| python-soundfile | WAV writing | BSD 3-Clause | https://github.com/bastibe/python-soundfile/blob/master/LICENSE |
| libsndfile, bundled by python-soundfile wheels | Native audio I/O | GNU LGPL 2.1 | https://github.com/libsndfile/libsndfile/blob/master/COPYING |
| Triton for Windows | GPU kernel compiler | MIT | https://github.com/triton-lang/triton-windows |

VoxCPM installs additional transitive Python dependencies. PyTorch and its binary wheels also include third-party components. The table is a convenience summary, not a complete redistribution notice. Anyone distributing the application, its environment, an installer, or an executable must inspect the exact resolved packages and preserve all required copyright, license, source-offer, and notice files. Installed distributions commonly place those files in `.venv/Lib/site-packages/*-info/licenses/` or beside bundled native libraries.

## Model use

The VoxCPM2 model card describes the model as Apache-2.0 and commercially usable. It also states these use conditions:

- Do not use the model for impersonation, fraud, or disinformation.
- Clearly label AI-generated content.
- Perform safety evaluation appropriate to a production use case.

Use only EPUBs and voice recordings for which you have permission. Obtain informed consent from a speaker before cloning their voice. The model license does not grant copyright, publicity, privacy, trademark, or contractual rights in input material or a person's voice, and this notice is not legal advice.
