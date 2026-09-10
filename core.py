"""EPUB reading and restartable audiobook generation."""
import hashlib
import json
import posixpath
import re
import wave
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET


@dataclass
class Chapter:
    title: str
    text: str


class TextReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('head', 'script', 'style'):
            self.hidden += 1
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'section'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('head', 'script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'section'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def read_epub(path, include_language=False):
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 200_000_000:
            raise ValueError('EPUB is too large (200 MB expanded limit).')
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        rootfile = container.find('.//{*}rootfile')
        if rootfile is None:
            raise ValueError('EPUB has no package document.')
        package = rootfile.attrib['full-path']
        root = ET.fromstring(archive.read(package))
        title = root.find('.//{*}metadata/{*}title')
        book_title = title.text if title is not None and title.text else Path(path).stem
        manifest = {item.attrib['id']: item.attrib for item in root.findall('.//{*}manifest/{*}item')}
        chapters = []
        for ref in root.findall('.//{*}spine/{*}itemref'):
            item = manifest.get(ref.attrib['idref'], {})
            if ref.attrib.get('linear') == 'no' or 'nav' in item.get('properties', '').split():
                continue
            if item.get('media-type') not in ('application/xhtml+xml', 'text/html'):
                continue
            name = posixpath.normpath(posixpath.join(posixpath.dirname(package), unquote(item['href'].split('#')[0])))
            reader = TextReader()
            reader.feed(archive.read(name).decode('utf-8-sig'))
            lines = [re.sub(r'\s+', ' ', line).strip() for line in ''.join(reader.parts).splitlines()]
            lines = [line for line in lines if line]
            if lines:
                heading = ' — '.join(lines[:2]) if re.fullmatch(r'\d+|[IVXLCDM]+', lines[0]) and len(lines) > 1 else lines[0]
                chapters.append(Chapter(heading[:100], '\n\n'.join(lines)))
        if not chapters:
            raise ValueError('No readable chapters found. Use an unencrypted EPUB.')
        language = root.find('.//{*}metadata/{*}language')
        language = language.text.strip() if language is not None and language.text else ''
        return (book_title, chapters, language) if include_language else (book_title, chapters)


def split_text(text, limit=400):
    """Bound inference input without dropping text, including unspaced scripts."""
    chunks = []
    for paragraph in text.split('\n\n'):
        remaining = paragraph.strip()
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            window = remaining[:limit + 1]
            stops = list(re.finditer(r'[.!?。！？](?:\s|$)', window))
            cut = stops[-1].end() if stops else window.rfind(' ')
            if cut < limit // 3:
                cut = limit
            chunks.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
    return chunks


def join_wavs(inputs, output, gap_seconds=0.25):
    temporary = output.with_suffix('.partial.wav')
    try:
        with wave.open(str(temporary), 'wb') as target:
            expected = None
            for index, source in enumerate(inputs):
                with wave.open(str(source), 'rb') as audio:
                    signature = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
                    if expected is None:
                        expected = signature
                        target.setnchannels(signature[0])
                        target.setsampwidth(signature[1])
                        target.setframerate(signature[2])
                    elif signature != expected:
                        raise ValueError('Audio segments have incompatible formats.')
                    if index:
                        target.writeframes(b'\0' * int(signature[2] * gap_seconds) * signature[0] * signature[1])
                    while frames := audio.readframes(65536):
                        target.writeframes(frames)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def narration_prompt(text, style, language=''):
    direction = ', '.join(part for part in (style.strip(), f'Speak in {language}' if language else '') if part)
    return f'({direction}){text}' if direction else text


@lru_cache(maxsize=1)
def load_model():
    """Keep weights and compiled kernels alive between sequential UI jobs."""
    from voxcpm import VoxCPM
    return VoxCPM.from_pretrained('openbmb/VoxCPM2', load_denoiser=False)


def generate(chapters, destination, reference, style, stop, report, preview=False,
             language='', steps=20, seed=42):
    if not preview and not reference:
        raise ValueError('Book generation needs a voice reference. Generate a voice test, use it as the reference, and save the voice first.')
    import soundfile as sf
    import torch
    config = {'model': 'openbmb/VoxCPM2', 'style': style, 'seed': seed, 'steps': steps, 'language': language, 'cfg': 2.0,
              'reference': hashlib.sha256(Path(reference).read_bytes()).hexdigest() if reference else None,
              'chapters': [(i, c.title, c.text) for i, c in chapters], 'preview': preview}
    key = hashlib.sha256(json.dumps(config, ensure_ascii=False).encode()).hexdigest()[:16]
    folder = Path(destination) / ('preview-' + key if preview else 'book-' + key)
    cache = folder / 'segments'
    cache.mkdir(parents=True, exist_ok=True)
    (folder / 'manifest.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    report('Preparing passages…', 0)
    model = None
    tasks = [(i, c, split_text(c.text)) for i, c in chapters]
    if preview:
        tasks = [(tasks[0][0], tasks[0][1], tasks[0][2][:1])]
    total = sum(len(parts) for _, _, parts in tasks)
    done = 0
    for chapter_index, chapter, parts in tasks:
        paths = []
        for segment_index, text in enumerate(parts):
            if stop.is_set():
                report('Stopped. Completed passages are saved; Generate resumes them.', done / total)
                return folder
            output = cache / f'{chapter_index:04d}-{segment_index:05d}.wav'
            valid = False
            if output.exists():
                try:
                    with wave.open(str(output), 'rb') as audio:
                        valid = audio.getnframes() > 0
                except (wave.Error, EOFError):
                    pass
            if not valid:
                if model is None:
                    report('Loading / preparing VoxCPM2. First compilation can take several minutes…', done / total)
                    model = load_model()
                    if stop.is_set():
                        report('Stopped after model preparation.', done / total)
                        return folder
                report(f'{chapter.title} • passage {segment_index + 1}/{len(parts)}', done / total)
                kwargs = {'text': narration_prompt(text, style, language),
                          'cfg_value': 2.0, 'inference_timesteps': steps}
                if reference:
                    kwargs['reference_wav_path'] = reference
                torch.manual_seed(seed)
                wav = model.generate(**kwargs)
                if len(wav) == 0:
                    raise ValueError('VoxCPM returned empty audio. Try a shorter passage.')
                temporary = output.with_suffix('.partial.wav')
                sf.write(str(temporary), wav, model.tts_model.sample_rate, subtype='PCM_16')
                temporary.replace(output)
            paths.append(output)
            done += 1
            report(f'Completed {done}/{total} passages', done / total)
        safe_title = re.sub(r'[^\w .-]', '_', chapter.title)[:65].rstrip('. ')
        join_wavs(paths, folder / f'{chapter_index + 1:03d} - {safe_title}.wav')
    report(f'Finished. Chapter WAV files saved in {folder}', 1)
    return folder
