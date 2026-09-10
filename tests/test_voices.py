import tempfile
import unittest
from pathlib import Path
from voices import VoiceLibrary


class VoiceTests(unittest.TestCase):
    def test_saved_voice_survives_restart_and_source_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'preview.wav'
            source.write_bytes(b'example audio')
            voice = dict(style='Warm', reference=str(source), language='German', steps=20, seed=42)
            library = VoiceLibrary(root / 'voices')
            library.save('My narrator', voice)
            source.unlink()
            restored = VoiceLibrary(root / 'voices').get('My narrator')
            self.assertEqual(Path(restored.pop('reference')).read_bytes(), b'example audio')
            self.assertEqual(restored, {k: v for k, v in voice.items() if k != 'reference'})

    def test_update_and_named_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            library = VoiceLibrary(directory)
            voice = dict(style='Warm', reference='', language='', steps=20, seed=42)
            library.save('Narrator', voice)
            voice['seed'] = 123
            library.save('narrator', voice)
            library.save('Another voice', voice)
            self.assertEqual(set(VoiceLibrary(directory).voices), {'narrator', 'Another voice'})
            self.assertEqual(library.get('narrator')['seed'], 123)

    def test_failed_save_preserves_library(self):
        with tempfile.TemporaryDirectory() as directory:
            library = VoiceLibrary(directory)
            voice = dict(style='Warm', reference='', language='', steps=20, seed=42)
            library.save('Saved', voice)
            for name, changes in [('', {}), ('Invalid', {'steps': 0}), ('Missing', {'reference': str(Path(directory) / 'missing.wav')})]:
                with self.assertRaises((ValueError, OSError)):
                    library.save(name, {**voice, **changes})
            self.assertEqual(list(VoiceLibrary(directory).voices), ['Saved'])

    def test_corrupt_library_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'voices.json'
            path.write_text('{invalid')
            with self.assertRaises(ValueError):
                VoiceLibrary(directory)
            self.assertEqual(path.read_text(), '{invalid')
