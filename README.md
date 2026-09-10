# Audiobook

Native Windows EPUB-to-audiobook prototype powered by OpenBMB VoxCPM2.

## Run

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/ with Tk and the Python launcher enabled.
2. Run `Setup.cmd`. This creates a private environment and downloads CUDA PyTorch and VoxCPM dependencies. An internet connection and several GB of free disk space are required.
3. Run `Start.cmd`, open an unencrypted EPUB, and select chapters.
4. Optionally select a clean WAV reference voice. Leave the field blank to use voice design. For consistent narration, a reference clip is preferable; a fixed seed alone does not guarantee identical delivery across passages.
5. Generate a preview first, then generate the selected chapters. Use Open output to locate and play the WAV files.

The first generation downloads `openbmb/VoxCPM2` into the usual Hugging Face cache. Subsequent cached-model generation is local. The model is reloaded per job to keep this prototype simple. The RTX 3060 12 GB detected on the development machine exceeds the project's approximate 8 GB inference figure; actual memory use and speed still require testing.

## Output and resume

Each job has a folder containing numbered chapter WAVs, cached passage WAVs, and a manifest. Stop takes effect between passages, including after model loading. Select the same chapters and keep voice settings unchanged to resume; changes create a separate job folder. Keep the segments folder until you no longer need resume. Output uses PCM16 at the model's sample rate with 250 ms between passages. Chapter assembly streams from disk. Very long individual chapters can exceed standard WAV's 4 GB limit; select smaller sections in that case.

## Scope and limitations

- Reads EPUB spine order, skips non-linear items and navigation documents. Each spine document becomes one selectable section; its first text line supplies the label.
- Splits text into bounded passages. Paragraph boundaries are retained; abbreviations and unusual punctuation may split imperfectly.
- Supports UTF-8 EPUB content; encrypted books and unusual encodings are not supported.
- Exports chapter WAVs. M4B/MP3 packaging, a packaged EXE, text editing, pronunciation dictionaries, and automatic speech-quality checks are not included yet.
- PyTorch/VoxCPM installation and actual speech inference must be validated on the target machine. If CUDA is unavailable, check the NVIDIA driver and your PyTorch installation. This prototype does not promise CPU audiobook throughput.
- The UI and EPUB/audio assembly logic can run without VoxCPM installed; generation displays dependency errors when setup is incomplete.

## Development checks

Run `python -m unittest discover -s tests -v` from this folder. Tests exercise spine order, text splitting, and WAV assembly without downloading a model.

Validation in this workspace: all three core tests passed. UI startup could not be verified because the bundled Python runtime failed to initialize Tcl/Tk. No model weights were downloaded and no real speech generation was run. Use a standard Python installation with Tk to run the app.

Official model documentation: https://github.com/OpenBMB/VoxCPM
