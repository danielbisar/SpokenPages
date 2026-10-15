# SpokenPages agent instructions

## Start here

SpokenPages is a native Windows 11 Tk application that converts EPUB spine documents into resumable chapter WAVs with VoxCPM2. Python 3.12 and an NVIDIA CUDA GPU are the supported development target.

- Read [README.md](README.md) for setup, behavior, and supported scope.
- Read [docs/architecture.md](docs/architecture.md) before changing EPUB parsing, generation, resume identity, manifests, audio assembly, or voice persistence.
- Use [docs/troubleshooting.md](docs/troubleshooting.md) for environment and CUDA diagnosis.
- Preserve the licensing and responsible-use guidance in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Commands

- Set up only when needed: `.\setup.ps1` or `setup.cmd`. The environment is large and setup performs network installs.
- Run tests after Python changes: `.\run-tests.ps1`.
- Equivalent focused command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
- Do not run `benchmark.py --model`, download model weights, or perform real speech inference unless the task requires GPU validation. Unit tests mock synthesis and remain offline.

The CUDA 12.6 environment intentionally pins PyTorch 2.14 and Torchaudio 2.11 because Torchaudio 2.14 is not published on that index. Do not normalize these versions without checking package availability and validating imports, `pip check`, tests, and inference.

## Ownership and invariants

- `app.py` owns Tk widgets, UI validation, and the single background generation worker. Keep Tk updates on the UI thread through the event queue.
- `core.py` owns EPUB parsing, bounded text splitting, model reuse, job identity, segment resume, and WAV assembly. Preserve spine order and text content; each synthesis passage must remain at most 400 characters.
- Bump `CACHE_VERSION` for incompatible splitter, prompt, synthesis-dependency, or audio/cache changes. Keep `MODEL_REVISION` in both the actual snapshot loader and manifest identity; do not pass an unsupported revision argument through VoxCPM's constructor.
- Book generation requires a saved reference WAV; voice previews may use description-only voice design.
- Resume identity includes selected indices and full chapter text, voice style, reference-content hash, language, inference steps, seed, model, CFG, and preview mode. Any semantic setting change must produce a different job identity.
- Stop is cooperative between passages. Valid completed segments must remain reusable after stop or failure.
- `voices.py` validates entries, copies references under content-hash filenames, and atomically replaces `voices.json`. Preserve those durability properties.
- Keep edits small and consistent with the script-style modules; there is no stable public Python API.

## Platform and data safety

- The current UI is Windows-specific (`os.startfile`, `.cmd`/PowerShell entry points, and Windows Triton). Treat Linux support as a portability feature requiring code, dependency, documentation, and GPU validation changes.
- `audiobooks/` is ignored runtime output. Its manifests contain full selected book text. Do not inspect, delete, stage, or rewrite user output unless explicitly requested.
- `voices/` is ignored user data, not disposable cache. Never inspect or mutate an existing user library unless requested. Published synthetic examples live under `examples/voices/` and use Git LFS; keep their provenance and asset terms with them. Runtime saves must not modify published examples.
- `.venv/`, Python caches, and the Hugging Face model cache are local generated data.
- If SpokenPages is actively generating, source edits affect the next launch. Do not mutate the active job folder or voice library during that run.

## Validation and documentation

- Run the narrowest relevant test first, then the full `.\run-tests.ps1` suite for shared generation, voice, or UI behavior.
- Offline-only tests need just Python 3.12 with Tk: `py -3.12 -m unittest discover -s tests -v`. Windows CI requires Tk and must not silently skip desktop tests or install synthesis dependencies.
- UI tests skip when Tcl/Tk cannot initialize; that skip does not validate desktop behavior.
- Tests do not validate CUDA kernels, pronunciation, perceived quality, model downloads, or VRAM usage. State clearly when those checks were not run.
- Update README workflow text and the linked architecture or troubleshooting guide when behavior, persisted data, dependency pins, or platform support changes.
