"""Named voice settings and durable copies of reference audio."""
import hashlib
import json
from pathlib import Path


class VoiceLibrary:
    def __init__(self, folder):
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
            filename = hashlib.sha256(audio).hexdigest() + '.wav'
            reference = self.folder / filename
            if not reference.exists():
                reference.write_bytes(audio)
            saved['reference'] = filename
        updated = dict(self.voices)
        if previous:
            del updated[previous]
        updated[name] = saved
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)
        self.voices = updated
        return name

    def get(self, name):
        voice = dict(self.voices[name])
        if voice['reference']:
            voice['reference'] = str(self.folder / voice['reference'])
        return voice
