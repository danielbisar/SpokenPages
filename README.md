# Audiobook

Native Windows EPUB-to-audiobook prototype powered by OpenBMB VoxCPM2.

## Run

1. Install Python 3.12 from https://www.python.org/downloads/windows/ with Tk and the Python launcher enabled.
2. Run `setup.cmd` or `./setup.ps1`. This creates a private environment and downloads CUDA PyTorch and VoxCPM dependencies. An internet connection and several GB of free disk space are required.
3. Run `start.cmd` or `./start.ps1`, open an unencrypted EPUB, and select chapters.
4. Open the **Voice setup** tab. Enter a custom voice name and optionally select a clean WAV reference voice. Leave the field blank to use voice design. For consistent narration, a reference clip is preferable; a fixed seed alone does not guarantee identical delivery across passages.
5. Choose a narrator preset or edit its description. Generate voice tests without opening a book, using editable text in the intended language. Tests open in your default WAV player; Play last test replays them. Change the seed to try another voice. Use last test as voice reference to reuse a voice you like (or browse to an earlier test WAV).
6. Compare 10, 20 (default), or 30 inference steps. Higher values take longer and may improve synthesis; they do not guarantee better narration. Output remains lossless PCM16 at the model's native sample rate; increasing bit depth will not fix an unsuitable voice or synthesis artifacts.
7. Book language is filled from EPUB metadata when present. You can override it with a language name/code or choose Auto (from text). VoxCPM has no dedicated language argument: this selection adds a natural-language pronunciation hint, not translation or a guaranteed language lock. Use test text and reference speech in the intended language to check pronunciation.
8. Click **Save voice / update matching name**, then choose your saved narrator on the **Book generation** tab and generate the selected chapters. Use Open output to locate the WAV files. Voice settings, language, inference steps, and seed are recorded in the job manifest and affect resume identity.

The first generation downloads `openbmb/VoxCPM2` into the usual Hugging Face cache. Subsequent cached-model generation is local. The model stays loaded on a single generation worker between jobs, including its compiled kernels. Close the app to release its GPU memory. The RTX 3060 12 GB detected on the development machine exceeds the project's approximate 8 GB inference figure; actual memory use and speed still require testing.

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

Run `./run-tests.ps1` (uses the Python 3.12 private environment) or `.venv/Scripts/python.exe -m unittest discover -s tests -v` from this folder. Tests exercise spine order, text splitting, and WAV assembly without downloading a model.

The unit tests do not download model weights or evaluate perceived speech quality. Listen to voice tests on your target machine before generating a full book.

Official model documentation: https://huggingface.co/openbmb/VoxCPM2

## Generation speed

Setup installs CUDA PyTorch 2.14 and matching Windows Triton 3.8. Restart the app after installing dependencies. VoxCPM enables compilation automatically; the first model preparation may take several minutes, while later jobs reuse the loaded model. GPU memory stays allocated until you close the app. Inference steps remain at your chosen value; the speed changes do not reduce this setting.

Verify the compiler with `.venv/Scripts/python.exe benchmark.py`. With model weights already cached, compare `.venv/Scripts/python.exe benchmark.py --model` and `.venv/Scripts/python.exe benchmark.py --model --compile`. Each reports preparation time and three speech runs at 20 steps. Compare later runs separately from preparation; RTF below 1 means generation is faster than playback. Short-passage results do not predict every book or reference voice.

Windows version compatibility: https://github.com/triton-lang/triton-windows/blob/readme/README.md

Measured on the development RTX 3060 (Python 3.12, PyTorch 2.14.0+cu126, Triton Windows 3.8.0.post28): model preparation took 11.54 seconds uncompiled and 72.35 seconds on the initial compiled load. The third uncompiled run took 6.63 seconds for 5.12 seconds of audio (RTF 1.294); the third compiled run took 6.77 seconds for 5.28 seconds of audio (RTF 1.282). This short sample shows no meaningful throughput improvement from compilation. Compiled output duration differs slightly despite the same seed. Retaining the model removes repeated preparation between UI jobs; it does not make initial startup faster. The benchmark does not assess voice quality.

## Saved voices

The Voice setup tab creates and edits voices; Book generation selects from saved voices. Saving an existing name updates it (case-insensitive). Saving with a different name creates a copy. Unsaved editor changes never affect book generation. A voice stores narrator direction, seed, inference steps, reference audio, and test language; book language remains a separate setting populated from EPUB metadata. Use selected book passage explicitly copies the selected chapter's opening into the voice test editor.

Voices persist in `voices/voices.json` beside the app. Reference WAVs are copied into that folder when saved, so deleting a preview or moving the original recording does not break the voice. Back up the whole `voices` directory to preserve your library. Both tabs have vertical scrollbars for smaller windows; progress and Stop remain outside the tabs.

## Selecting content and keeping one narrator

The chapter list shows body headings and word counts, with a selected-section count below it. Select all sections includes the entire readable EPUB; a normal click selects only one section, while Ctrl-click adds or removes sections. HTML head metadata is excluded from narration. Reopen an already loaded EPUB after updating the app to refresh its labels.

Book generation requires reference audio for the saved voice. A description and fixed seed alone design a new voice for each passage. In Voice setup, generate a test containing a few natural sentences, listen, choose **Use last test as voice reference**, and save the voice. Alternatively browse to a clean speech WAV. This conditions all passages on the same reference, although delivery can still vary. Existing outputs are retained; corrected text or reference settings create a new job folder. Output currently consists of one WAV per selected section, not a single combined book file.
