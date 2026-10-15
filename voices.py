"""Named voice settings and durable copies of reference audio."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def atomic_write(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.',
                                         suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class VoiceLibrary:
    def __init__(self, folder, examples=None):
        self.folder = Path(folder)
        self.path = self.folder / 'voices.json'
        self.voices = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Voice library must contain named voices.')
            for name, voice in data.items():
                self.validate(name, voice)
            self.voices = data
        elif examples is not None:
            sample = VoiceLibrary(examples)
            for name in sample.voices:
                self.save(name, sample.get(name))

    @staticmethod
    def validate(name, voice):
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError('Enter a voice name between 1 and 80 characters.')
        if not isinstance(voice, dict) or any(not isinstance(voice.get(k), str) for k in ('style', 'reference', 'language')):
            raise ValueError('Invalid voice settings.')
        if type(voice.get('steps')) is not int or not 1 <= voice['steps'] <= 100:
            raise ValueError('Use 1–100 inference steps.')
        if type(voice.get('seed')) is not int or not 0 <= voice['seed'] <= 4294967295:
            raise ValueError('Use a seed between 0 and 4294967295.')

    def save(self, name, voice):
        name = name.strip()
        self.validate(name, voice)
        # Matching names update the existing preset, including case-only edits.
        previous = next((n for n in self.voices if n.casefold() == name.casefold()), None)
        saved = dict(voice)
        self.folder.mkdir(parents=True, exist_ok=True)
        if saved['reference']:
            audio = Path(saved['reference']).read_bytes()
            if audio.startswith(b'version https://git-lfs.github.com/spec/v1'):
                raise ValueError('Reference audio is a Git LFS pointer. Run git lfs install and git lfs pull first.')
            filename = hashlib.sha256(audio).hexdigest() + '.wav'
            reference = self.folder / filename
            if not reference.exists() or hashlib.sha256(reference.read_bytes()).hexdigest() != filename[:-4]:
                atomic_write(reference, audio)
            saved['reference'] = filename
        updated = dict(self.voices)
        if previous:
            del updated[previous]
        updated[name] = saved
        atomic_write(self.path, json.dumps(updated, ensure_ascii=False, indent=2).encode('utf-8'))
        self.voices = updated
        return name

    def get(self, name):
        voice = dict(self.voices[name])
        if voice['reference']:
            voice['reference'] = str(self.folder / voice['reference'])
        return voice
