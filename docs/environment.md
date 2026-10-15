# Environment and validation record

## Known-good direct combination

The existing development/benchmark record reports Windows 11, Python 3.12 and
an NVIDIA RTX 3060 12 GB with this direct dependency combination:

| Component | Recorded version |
| --- | --- |
| PyTorch | `2.14.0+cu126` |
| Torchaudio | `2.11.0` from the CUDA 12.6 index |
| VoxCPM | `2.0.3` |
| Triton Windows | `3.8.0.post28` |

`constraints-windows.txt` preserves this combination during installation of
`requirements.txt`. Torch and Torchaudio intentionally have different version
numbers. Do not replace them with matching numbers without checking package
availability and validating the resulting environment on Windows.

This is **not a complete resolved/transitive lockfile**. The prior environment's
full package freeze, exact Python patch version and NVIDIA driver version were
not retained in the repository; unknown versions are not invented here.
SoundFile and transitive dependencies still resolve within their declared
requirements. Setup now runs `pip check`, imports the synthesis dependencies
without loading a model, and writes the actual resolved package versions to
ignored `.venv/installed-packages.txt`. Retain that local record with benchmark
results when comparing environments; review it before publishing.

## Model compatibility

New jobs use `openbmb/VoxCPM2` at Hugging Face revision
`32279effe8c19989596f05d353d1447f51d9e915`, the upstream revision inspected during
this readiness update. `core.py` resolves that immutable snapshot before loading
VoxCPM; `benchmark.py --model` requires that same snapshot to be cached.

This pins model inputs for future jobs; it does not establish which revision
created the existing demo WAV or retroactively validate GPU inference with the
updated loader. Both the model revision and `CACHE_VERSION` enter job identity.
Bump `CACHE_VERSION` for incompatible splitter, prompt, synthesis-dependency,
or audio/cache changes. Existing output is left untouched, without migration.

## What each check establishes

- **Windows offline CI:** Python 3.12 application imports, a real Tk window,
  core/voice/UI tests with mocked synthesis, example WAV availability and
  whitespace checks. It installs no synthesis packages or model weights.
- **Setup:** dependency metadata consistency and imports. Neither proves that
  CUDA kernels, compilation or inference work.
- **Manual target-machine checks:** CUDA/compiler checks, actual inference,
  stop/resume during a real job, reference conditioning, pronunciation, audio
  quality, VRAM, and performance. The README's historical timings are not new
  measurements from CI.
