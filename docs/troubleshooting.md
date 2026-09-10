# Troubleshooting

Run commands from the repository root. Prefer `setup.cmd` and `start.cmd` if local PowerShell policy blocks scripts.

## Setup fails

Confirm that the Python launcher can find 64-bit Python 3.12 and that Tk works:

```powershell
py -0p
py -3.12 -c "import struct, sys, tkinter; print(sys.version); print(struct.calcsize('P') * 8, 'bit'); print(tkinter.TkVersion)"
```

If PowerShell reports that script execution is disabled, either use the `.cmd` entry points or allow scripts only for the current process:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

Setup is safe to rerun. To rebuild from scratch, close the app, delete `.venv`, and rerun setup. This does not remove voices, model weights, or generated books.

The setup intentionally installs `torch==2.14.0` with `torchaudio==2.11.0` from the CUDA 12.6 PyTorch index. Torchaudio 2.14 is not published there; the selected pair passes `pip check` and imports on the tested machine. Inspect an installation with:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip show torch torchaudio voxcpm triton-windows
```

## CUDA is unavailable

Check the driver and the Python runtime separately:

```powershell
nvidia-smi
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No CUDA GPU')"
.\.venv\Scripts\python.exe benchmark.py
```

The setup uses CUDA 12.6 wheels. NVIDIA documents Windows driver 528.33 as the minimum for CUDA 12.x minor-version compatibility and 560.76 as the driver paired with CUDA 12.6 GA. Install a current production driver if CUDA or Triton compilation fails. The full CUDA Toolkit is not required because the PyTorch wheel includes the runtime libraries.

CPU-only generation is not a supported performance target. The interface and unit tests can run without CUDA, but speech generation and `benchmark.py` report an error.

## Model download or offline use fails

The first generation downloads `openbmb/VoxCPM2` from Hugging Face. The default cache is `%USERPROFILE%\.cache\huggingface\hub`. A partial download can be retried by starting generation again.

Set `HF_HOME` before the first download to place Hugging Face data on another drive:

```powershell
$env:HF_HOME = 'D:\huggingface'
.\start.ps1
```

This setting applies only to that PowerShell process unless added to the user's environment. `benchmark.py --model` deliberately uses cached files only, so run one successful generation before using that benchmark.

## Generation fails or stops

- **Out of memory:** close other GPU applications, close and reopen SpokenPages to release cached model memory, and try a shorter selection. Selecting fewer chapters reduces output work but may not reduce model VRAM substantially.
- **Empty audio:** retry with a shorter or simpler passage, a different reference, or fewer expressive instructions.
- **Missing reference:** reopen Voice setup, select an existing WAV or generate a test, choose **Use last test as voice reference**, and save the voice again.
- **Stop appears delayed:** Stop is checked between passages and after model preparation; it cannot interrupt an active model call.
- **Unexpected resume:** resume identity includes chapter titles and full text, selected indices, voice settings, reference contents, language, steps, and seed. Matching jobs reuse valid passage WAVs.

Completed segments remain in the job's `segments/` directory after an error or stop. Do not remove that directory if you intend to resume.

## EPUB cannot be read

The reader supports unencrypted UTF-8 EPUB content in spine order. It rejects archives larger than 200 MB after expansion, encrypted books, unsupported text encodings, malformed package metadata, and books with no readable linear HTML/XHTML spine items.

If labels or text look stale after updating the application, reopen the EPUB. Navigation documents and spine items marked non-linear are intentionally skipped.

## Voice library cannot load

`voices/voices.json` must be valid UTF-8 JSON containing named voice objects. The app refuses to overwrite a malformed library. Before repairing it:

1. Close the app.
2. Back up the entire `voices/` directory.
3. Validate the JSON and ensure every referenced WAV filename still exists in that directory.

Saved reference WAVs use a content-hash filename. Updating or deleting a voice does not automatically remove old unreferenced WAVs; remove one manually only after confirming no entry in `voices.json` names it.

## Storage and cleanup

- `.venv/`: installed Python environment; safe to delete and recreate with setup.
- `%USERPROFILE%\.cache\huggingface\hub`: downloaded model data; safe to delete when the app is closed, but the next generation downloads it again.
- `audiobooks/`: default output, previews, manifests, and resumable passage caches; delete completed job folders when neither their output nor resume data is needed.
- `voices/`: saved voice metadata and copied references; back it up and do not bulk-delete it as cache.

On the tested machine, `.venv` uses 5.25 GiB and the Hugging Face cache uses 4.62 GiB before generated audio. These values are examples, not fixed limits.

## Information to collect for a report

Include the exact error, Windows version, GPU and driver from `nvidia-smi`, output from the CUDA Python check above, and package versions from `pip show`. Do not attach copyrighted EPUB text, `manifest.json`, or private voice references without permission.
