import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import validate_wav
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

    def test_interrupted_reference_copy_preserves_library_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.wav'
            source.write_bytes(b'example audio')
            library = VoiceLibrary(root / 'voices')
            voice = dict(style='Warm', reference='', language='', steps=20, seed=42)
            library.save('Saved', voice)
            original = library.path.read_bytes()
            with patch('voices.os.fsync', side_effect=OSError('Interrupted write')):
                with self.assertRaisesRegex(OSError, 'Interrupted'):
                    library.save('New', {**voice, 'reference': str(source)})
            self.assertEqual(library.path.read_bytes(), original)
            self.assertEqual(list(library.voices), ['Saved'])
            self.assertFalse(list(library.folder.glob('*.wav')))
            self.assertFalse(list(library.folder.glob('*.tmp')))
            library.save('New', {**voice, 'reference': str(source)})
            reference = Path(library.get('New')['reference'])
            reference.write_bytes(b'partial')
            library.save('New', {**voice, 'reference': str(source)})
            self.assertEqual(reference.read_bytes(), source.read_bytes())

    def test_reference_replace_failure_leaves_no_partial_final_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.wav'
            source.write_bytes(b'example audio')
            library = VoiceLibrary(root / 'voices')
            voice = dict(style='Warm', reference=str(source), language='', steps=20, seed=42)
            with patch.object(Path, 'replace', side_effect=OSError('Cannot replace')):
                with self.assertRaisesRegex(OSError, 'Cannot replace'):
                    library.save('New', voice)
            self.assertEqual(list(library.folder.iterdir()), [])
            self.assertEqual(library.voices, {})

    def test_lfs_pointer_is_rejected_with_recovery_instructions(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'pointer.wav'
            source.write_bytes(b'version https://git-lfs.github.com/spec/v1\n')
            library = VoiceLibrary(Path(directory) / 'voices')
            voice = dict(style='Warm', reference=str(source), language='', steps=20, seed=42)
            with self.assertRaisesRegex(ValueError, 'git lfs pull'):
                library.save('Example', voice)
            self.assertFalse(library.path.exists())

    def test_examples_are_copied_only_into_a_new_runtime_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'sample.wav'
            source.write_bytes(b'synthetic example audio')
            examples = VoiceLibrary(root / 'examples')
            voice = dict(style='Warm', reference=str(source), language='', steps=20, seed=42)
            examples.save('Synthetic example', voice)
            original = examples.path.read_bytes()
            runtime = VoiceLibrary(root / 'voices', examples=examples.folder)
            self.assertEqual(Path(runtime.get('Synthetic example')['reference']).parent, runtime.folder)
            runtime.save('Synthetic example', {**voice, 'seed': 123})
            reopened = VoiceLibrary(runtime.folder, examples=examples.folder)
            self.assertEqual(reopened.get('Synthetic example')['seed'], 123)
            self.assertEqual(examples.path.read_bytes(), original)

    def test_bundled_synthetic_example_is_a_complete_content_addressed_wav(self):
        examples = Path(__file__).resolve().parents[1] / 'examples' / 'voices'
        with tempfile.TemporaryDirectory() as directory:
            library = VoiceLibrary(directory, examples=examples)
            reference = Path(library.get('Synthetic demo narrator')['reference'])
            validate_wav(reference)
            self.assertEqual(reference.stem, hashlib.sha256(reference.read_bytes()).hexdigest())
