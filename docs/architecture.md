# Architecture and data

## Components

- `app.py` owns the Tk desktop interface, validates UI state, serializes generation through one worker thread, and relays progress back to the UI thread.
- `core.py` reads EPUBs, extracts and splits text, loads and retains VoxCPM2, generates resumable passage audio, and assembles chapter WAVs.
- `voices.py` validates named voice settings and atomically persists the voice library and content-addressed reference WAVs.
- `benchmark.py` checks CUDA/Triton compilation or benchmarks an already-cached model.
- `setup.cmd` and `setup.ps1` create `.venv` and install the pinned GPU stack. `start.cmd`, `start.ps1`, and `run-tests.ps1` enforce Python 3.12 before launching work.

The modules are scripts rather than a stable Python package. Their functions and JSON formats should be treated as internal implementation details unless a release explicitly promises compatibility.

## Generation flow

1. `read_epub` opens the EPUB ZIP, enforces a 200 MB expanded-size limit, locates the OPF package, and walks readable linear HTML/XHTML spine items.
2. `TextReader` excludes `head`, `script`, and `style` content and preserves common block boundaries. Each readable spine item becomes one selectable `Chapter`.
3. `split_text` divides each selected chapter into passages of at most 400 characters, preferring paragraph and sentence boundaries without dropping text.
4. `generate` computes a job identity, writes its manifest, and reuses valid cached passage WAVs. VoxCPM2 is loaded lazily only when a missing passage must be synthesized.
5. `join_wavs` streams passage WAVs into one PCM16 chapter WAV with 250 ms of silence between passages. It writes a temporary file and replaces the destination only after successful assembly.

The UI uses a single generation worker because the loaded model and GPU are shared. Stop requests are cooperative and take effect between passages or immediately after model preparation.

## Job layout

The default destination is `audiobooks/`, but users can select another folder. Book jobs use `book-<identity>` and voice tests use `preview-<identity>`:

```text
audiobooks/
  book-0123456789abcdef/
    manifest.json
    segments/
      0000-00000.wav
      0000-00001.wav
    001 - Chapter title.wav
```

`audiobooks/` is ignored by Git. A custom destination outside that directory has its own version-control and backup policy.

## Manifest and resume identity

`manifest.json` records:

| Field | Meaning |
| --- | --- |
| `model` | Hugging Face model identifier |
| `style` | Narrator direction prepended to synthesis text |
| `seed` | Torch random seed reset for each generated passage |
| `steps` | VoxCPM inference timesteps |
| `language` | Optional natural-language pronunciation hint |
| `cfg` | Classifier-free guidance value, currently `2.0` |
| `reference` | SHA-256 digest of reference WAV contents, or `null` |
| `chapters` | Selected spine index, title, and full text for every section |
| `preview` | Whether the job is a voice test |

The job identity is the first 16 hexadecimal characters of the SHA-256 digest of the serialized JSON configuration above. Changing any recorded value creates a different folder. Repeating the same configuration reuses a passage when its expected WAV exists and contains at least one frame; chapter WAVs are then assembled again from the segment set.

The manifest intentionally makes jobs inspectable, but it also stores the complete selected book text. Output folders must be protected and shared under the same rules as the source book. The reference recording itself is not copied into a job, but its digest can identify identical content across jobs.

## Voice library

`voices/voices.json` maps display names to narrator direction, relative reference filename, seed, inference steps, and test language. Saving a reference copies it into `voices/` under the SHA-256 hash of its bytes. This makes saved voices independent of previews and original recording locations.

Saving a case-insensitive matching name replaces that entry; a different name creates a copy. Writes use `voices.tmp` followed by replacement so a failed write does not partially overwrite the library. Previously copied reference files are retained even when no saved voice uses them.

The repository contains an example `voices.json` and reference WAV. Unlike `audiobooks/`, changes under `voices/` are visible to Git. Review voice metadata and recording rights before committing additions.

## Other local data

- `.venv/` contains installed executable code and native libraries and is ignored by Git.
- `%USERPROFILE%\.cache\huggingface\hub` contains model files by default. Set `HF_HOME` before launch to relocate it.
- Python `__pycache__/` directories are ignored by Git.
- EPUB source files are read in place and are not copied by the application.

The application does not intentionally upload EPUB text or reference audio. Network access is used by dependencies to retrieve packages during setup and model files on the first generation. Review dependency behavior before using sensitive material in a controlled environment.

## Tests

`tests/test_core.py` covers EPUB order and filtering, language prompts, bounded text splitting, reference enforcement, resume identity, model reuse, and WAV assembly. `tests/test_voices.py` covers persistence, copied references, updates, validation failures, and corrupt-library protection. `tests/test_app.py` covers the saved-versus-unsaved voice boundary and key UI workflows; those tests skip when Tcl/Tk cannot create a window.

Tests mock speech generation. They do not download weights, exercise GPU kernels, assess pronunciation, or evaluate audio quality. Use `benchmark.py` and listening tests on the target machine for those checks.
