# SpokenPages - Local EPUB to Audiobook Converter

A Windows desktop experiment in turning local speech synthesis into a resumable audiobook workflow, with content-derived job identities, passage caching, streamed chapter WAV assembly, and an isolated background worker.

**Why it exists:** long-running local narration needs more than a model call: interrupted work should resume, saved narrators should survive restarts, and chapter assembly should not require keeping a whole audiobook in memory.

**My contribution:** application/workflow engineering around OpenBMB's VoxCPM2: orchestration, persistence and resume behavior, the Tk UI, audio assembly, offline tests, benchmarking, and operational scripts/docs. Development is AI-assisted. The project integrates VoxCPM; it does not implement or train the model.

**Status:** a small Windows 11/Python 3.12 prototype, not a production product. Windows-only support is intentional. Offline tests exercise workflow correctness; they do not establish speech quality, GPU compatibility, or production readiness.

## Engineering highlights

- **Resumable generation:** content/settings-derived job identities include a cache compatibility version and pinned model revision. Validated passage WAVs survive stop/failure and are reused.
- **Bounded processing:** narration text is split into passages of at most 400 characters; chapter assembly streams from disk into uncompressed PCM16 WAVs.
- **Model lifecycle:** lazy, cached loading on one generation worker avoids repeated preparation. Tk updates return through an event queue.
- **Persistence:** reference audio uses content-hash filenames; reference copies and voice-library JSON use flushed temporary files and atomic replacement. Published examples are separate from ignored user voices.
- **Measured behavior:** the included compilation experiment found no meaningful throughput improvement on the tested RTX 3060. Preparation cost and steady-state timing are reported separately, without a speedup claim.

## Synthetic voice example

The included [synthetic demo narrator](examples/voices/README.md) was generated through SpokenPages/VoxCPM from my own voice-design instructions. It is not a recording of me or another real speaker, and was not copied from third-party audio. Its provenance, saved prompt/settings, and MIT asset terms are documented separately from upstream model licensing.

The example is a voice reference, not a speech-quality benchmark. A new user library copies it from `examples/voices/` into ignored `voices/`; existing libraries are preserved.

Detailed references: [architecture and data](docs/architecture.md), [environment record](docs/environment.md), [troubleshooting](docs/troubleshooting.md), and [third-party notices](THIRD_PARTY_NOTICES.md).

## System requirements

- 64-bit Windows 11 is the tested target. The application requires a desktop session for Tk.
- Python 3.12 with Tk and the Python launcher (`py`). Other Python versions are not supported by the setup and launch scripts.
- A CUDA-capable NVIDIA GPU. VoxCPM2 reports approximately 8 GB VRAM; an RTX 3060 12 GB is the tested development GPU. Performance and peak memory vary with the input and dependency versions.
- A current NVIDIA driver. CUDA 12.x minor-version compatibility starts at Windows driver 528.33; NVIDIA paired CUDA 12.6 GA with driver 560.76. A current production driver is recommended because compilation may need newer driver features. The PyTorch wheel supplies the CUDA runtime, so the full CUDA Toolkit is not required.
- Internet access for setup and the first model download. Generation is local after the model is cached.
- At least 15 GiB free for setup/model data, plus generated audio and download/installation headroom. The development machine used a 5.25 GiB virtual environment and 4.62 GiB Hugging Face cache; sizes can change.

## Run

Install [Git LFS](https://git-lfs.com/) before cloning, then run `git lfs install` and `git lfs pull` in the clone to obtain the example WAV. A source ZIP or a clone without LFS may contain only a text pointer; the app reports this explicitly rather than treating it as audio.

1. Install Python 3.12 from https://www.python.org/downloads/windows/ with Tk and the Python launcher enabled.
2. Run `setup.cmd` or `./setup.ps1`. This creates a private environment and installs CUDA PyTorch 2.14, Torchaudio 2.11, and the constrained VoxCPM/Triton combination. Torchaudio 2.11 is intentional: it is the version recorded as working with this project's PyTorch 2.14 environment. Setup checks dependency integrity/imports and records installed packages; see the [environment record](docs/environment.md).
3. Run `start.cmd` or `./start.ps1`, open an unencrypted EPUB, and select chapters.
4. Open the **Voice setup** tab. Enter a custom voice name and optionally select a clean WAV reference voice. Leave the field blank to use voice design. For consistent narration, a reference clip is preferable; a fixed seed alone does not guarantee identical delivery across passages.
5. Choose a narrator preset or edit its description. Generate voice tests without opening a book, using editable text in the intended language. Tests open in your default WAV player; Play last test replays them. Change the seed to try another voice. Use last test as voice reference to reuse a voice you like (or browse to an earlier test WAV).
6. Compare 10, 20 (default), or 30 inference steps. Higher values take longer and may improve synthesis; they do not guarantee better narration. Output is uncompressed PCM16 WAV at the model's native sample rate; increasing bit depth will not fix an unsuitable voice or synthesis artifacts.
7. Book language is filled from EPUB metadata when present. You can override it with a language name/code or choose Auto (from text). VoxCPM has no dedicated language argument: this selection adds a natural-language pronunciation hint, not translation or a guaranteed language lock. Use test text and reference speech in the intended language to check pronunciation.
8. Click **Save voice / update matching name**, then choose your saved narrator on the **Book generation** tab and generate the selected chapters. Use Open output to locate the WAV files. Voice settings, language, inference steps, and seed are recorded in the job manifest and affect resume identity.

The first generation downloads the pinned `openbmb/VoxCPM2` revision into `%USERPROFILE%\.cache\huggingface\hub` unless Hugging Face environment variables select another cache. Subsequent cached-model generation is local. The model stays loaded on a single generation worker between jobs, including its compiled kernels. Close the app to release its GPU memory. The RTX 3060 12 GB detected on the development machine exceeds the project's approximate 8 GB inference figure; actual memory use and speed still require testing.

## Output and resume

The default destination is `audiobooks/`. Each job has a folder containing numbered chapter WAVs, cached passage WAVs, and a manifest. Stop takes effect between passages, including after model loading. Select the same chapters and keep voice settings unchanged to resume; changes create a separate job folder. Keep the segments folder until you no longer need resume. Output uses PCM16 at the model's sample rate with 250 ms between passages. Chapter assembly streams from disk. Very long individual chapters can exceed standard WAV's 4 GB limit; select smaller sections in that case.

The manifest contains the full selected chapter text as well as voice settings and the reference-audio hash. Treat the whole output folder as potentially sensitive. See [architecture and data](docs/architecture.md) for its schema, resume identity, storage locations, and cleanup rules.

Cache compatibility changes intentionally create new job folders; older output is retained, not migrated. Cached segments are checked for a complete readable PCM payload, not just a positive frame count in their header.

## Scope and limitations

- Reads EPUB spine order, skips non-linear items and navigation documents. Each spine document becomes one selectable section; its first text line supplies the label.
- Rejects EPUB archives whose total expanded file size exceeds 200 MB.
- Splits narration text into passages of at most 400 characters, before adding voice/language direction. Paragraph boundaries are retained; abbreviations and unusual punctuation may split imperfectly. Voice tests synthesize the entire supplied text (1-400 characters), including multiple paragraphs.
- Supports UTF-8 EPUB content; encrypted books and unusual encodings are not supported.
- Exports chapter WAVs. M4B/MP3 packaging, a packaged EXE, text editing, pronunciation dictionaries, and automatic speech-quality checks are not included yet.
- PyTorch/VoxCPM installation and actual speech inference must be validated on the target machine. If CUDA is unavailable, check the NVIDIA driver and your PyTorch installation. This prototype does not promise CPU audiobook throughput.
- The UI and EPUB/audio assembly logic can run without VoxCPM installed; generation displays dependency errors when setup is incomplete.

## Development checks

After full setup, run `./run-tests.ps1` or `.venv/Scripts/python.exe -m unittest discover -s tests -v` from this folder. For **offline-only development**, a standard Python 3.12 installation with Tk is sufficient: run `py -3.12 -m unittest discover -s tests -v`. No pip dependencies, GPU, or model weights are needed for the tests.

The [Windows offline CI](.github/workflows/offline-tests.yml) checks application imports and a working Tk window before running core/voice/UI tests with mocked synthesis. Local UI tests skip if Tk cannot create a window; CI sets `SPOKENPAGES_REQUIRE_TK=1` so a missing desktop fails instead. Import failures always fail.

The unit tests do not download model weights or evaluate perceived speech quality. Listen to voice tests on your target machine before generating a full book.

Official model documentation: https://huggingface.co/openbmb/VoxCPM2

## Generation speed

Setup installs CUDA PyTorch 2.14, Torchaudio 2.11, and Windows Triton 3.8. Restart the app after installing dependencies. VoxCPM enables compilation automatically; the first model preparation may take several minutes, while later jobs reuse the loaded model. GPU memory stays allocated until you close the app. Inference steps remain at your chosen value; the speed changes do not reduce this setting.

Verify the compiler with `.venv/Scripts/python.exe benchmark.py`. With model weights already cached, compare `.venv/Scripts/python.exe benchmark.py --model` and `.venv/Scripts/python.exe benchmark.py --model --compile`. Each reports preparation time and three speech runs at 20 steps. Compare later runs separately from preparation; RTF below 1 means generation is faster than playback. Short-passage results do not predict every book or reference voice.

Windows version compatibility: https://github.com/triton-lang/triton-windows/blob/readme/README.md

Measured on the development RTX 3060 (Python 3.12, PyTorch 2.14.0+cu126, Triton Windows 3.8.0.post28): model preparation took 11.54 seconds uncompiled and 72.35 seconds on the initial compiled load. The third uncompiled run took 6.63 seconds for 5.12 seconds of audio (RTF 1.294); the third compiled run took 6.77 seconds for 5.28 seconds of audio (RTF 1.282). This short sample shows no meaningful throughput improvement from compilation. Compiled output duration differs slightly despite the same seed. Retaining the model removes repeated preparation between UI jobs; it does not make initial startup faster. The benchmark does not assess voice quality.

## Saved voices

The Voice setup tab creates and edits voices; Book generation selects from saved voices. Saving an existing name updates it (case-insensitive). Saving with a different name creates a copy. Unsaved editor changes never affect book generation. A voice stores narrator direction, seed, inference steps, reference audio, and test language; book language remains a separate setting populated from EPUB metadata. Use selected book passage explicitly copies the selected chapter's opening into the voice test editor.

User voices persist in ignored `voices/voices.json` beside the app. Reference WAVs are copied atomically into that folder when saved, so deleting a preview or moving the original recording does not break the voice. Back up the whole `voices` directory to preserve your library. On first launch only, the app seeds a missing library from the published synthetic example under `examples/voices/`. Existing libraries are not overwritten. User-library edits do not modify the published example.

Both `voices/` and generated `audiobooks/` output are ignored by Git. This does not protect files deliberately force-added or saved to other tracked paths. Both tabs have vertical scrollbars for smaller windows; progress and Stop remain outside the tabs.

## Selecting content and keeping one narrator

The chapter list shows body headings and word counts, with a selected-section count below it. Select all sections includes the entire readable EPUB; a normal click selects only one section, while Ctrl-click adds or removes sections. HTML head metadata is excluded from narration. Reopen an already loaded EPUB after updating the app to refresh its labels.

Book generation requires reference audio for the saved voice. A description and fixed seed alone design a new voice for each passage. In Voice setup, generate a test containing a few natural sentences, listen, choose **Use last test as voice reference**, and save the voice. Alternatively browse to a clean speech WAV. This conditions all passages on the same reference, although delivery can still vary. Existing outputs are retained; corrected text or reference settings create a new job folder. Output currently consists of one WAV per selected section, not a single combined book file.

## License and responsible use

The application source and documentation are licensed under the [MIT License](LICENSE). The author also offers the synthetic demo WAV under MIT to the extent applicable rights exist; this is not a claim of exclusive ownership or copyrightability of AI-generated audio. VoxCPM and the VoxCPM2 model are separately licensed under Apache-2.0; other direct and transitive dependencies retain their own licenses. No ownership of upstream software, models, or training data is claimed. See [third-party notices](THIRD_PARTY_NOTICES.md).

Only process books and voice recordings you have permission to use. Obtain the speaker's consent before cloning a voice. The VoxCPM2 model card forbids impersonation, fraud, and disinformation and says AI-generated content should be clearly labeled. Laws and distribution-platform rules may impose additional requirements; this repository does not determine ownership or grant rights in source books, recordings, or generated audio.
