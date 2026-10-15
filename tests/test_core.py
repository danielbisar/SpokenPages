import tempfile
import unittest
import wave
import zipfile
import json
import threading
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from pathlib import Path
from core import (
    CACHE_VERSION, MODEL_ID, MODEL_REVISION, Chapter, generate, join_wavs,
    load_model, model_snapshot, narration_prompt, read_epub, split_text, validate_wav,
)


class CoreTests(unittest.TestCase):
    def setUp(self):
        load_model.cache_clear()
        self.addCleanup(load_model.cache_clear)
        self.model = MagicMock()
        self.model.generate.return_value = [0.1] * 100
        self.model.tts_model.sample_rate = 48000
        self.factory = MagicMock(return_value=self.model)
        self.snapshot = MagicMock(return_value='cached-model')
        self.torch = MagicMock()

        def write(path, samples, rate, subtype):
            with wave.open(path, 'wb') as audio:
                audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
                audio.writeframes(b'\x01\x00' * len(samples))

        modules = {'torch': self.torch, 'soundfile': SimpleNamespace(write=write),
                   'huggingface_hub': SimpleNamespace(snapshot_download=self.snapshot),
                   'voxcpm': SimpleNamespace(VoxCPM=SimpleNamespace(from_pretrained=self.factory))}
        self.enterContext(patch.dict('sys.modules', modules))

    def test_spine_order_and_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'book.epub'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
                z.writestr('OPS/book.opf', '<package><metadata><title>Example</title><language>de-DE</language></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/><item id="n" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/></manifest><spine><itemref idref="b"/><itemref idref="n"/><itemref idref="a"/></spine></package>')
                z.writestr('OPS/a.xhtml', '<html><head><title>Repeated book title</title><style>hidden</style></head><body><h1>First</h1><p>A &amp; B</p></body></html>')
                z.writestr('OPS/b.xhtml', '<h1>Second</h1><script>hidden</script><p>Visible.</p>')
            title, chapters = read_epub(path)
            self.assertEqual(title, 'Example')
            self.assertEqual(read_epub(path, include_language=True)[2], 'de-DE')
            self.assertEqual([c.title for c in chapters], ['Second', 'First'])
            self.assertNotIn('hidden', chapters[0].text)
            self.assertIn('A & B', chapters[1].text)

    def test_split_preserves_content_and_bounds(self):
        for text in ['A long sentence. ' * 100, '很长的文字。' * 300, 'x' * 1001]:
            parts = split_text(text)
            self.assertTrue(all(0 < len(p) <= 400 for p in parts))
            self.assertEqual(''.join(''.join(parts).split()), ''.join(text.split()))

    def test_split_sentence_edges_and_small_limits(self):
        for limit in (1, 2, 10, 400):
            for punctuation in '.!?。！？':
                for position in (limit - 1, limit, limit + 1):
                    for separator in ('', ' ', '\n', '\t'):
                        text = 'x' * position + punctuation + separator + 'More text.'
                        with self.subTest(limit=limit, text=text):
                            parts = split_text(text, limit)
                            self.assertTrue(all(0 < len(p) <= limit for p in parts))
                            self.assertEqual(''.join(''.join(parts).split()), ''.join(text.split()))

    def test_split_rejects_invalid_limits(self):
        for limit in (0, -1, 1.5, True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                split_text('Text', limit)

    def test_book_requires_reference_before_loading_model(self):
        with patch('core.load_model') as load:
            with self.assertRaisesRegex(ValueError, 'voice reference'):
                generate([(0, Chapter('Test', 'Hello.'))], 'unused', '', '',
                         threading.Event(), lambda *args: None)
            load.assert_not_called()

    def test_language_prompt(self):
        self.assertEqual(narration_prompt('Hallo.', '', ''), 'Hallo.')
        self.assertEqual(narration_prompt('Hallo.', 'Warm voice', 'German'),
                         '(Warm voice, Speak in German)Hallo.')

    def test_generation_settings_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ([(0, Chapter('Test', 'Hallo Welt.'))], directory, '', 'Warm voice',
                    threading.Event(), lambda *args: None)
            folder = generate(*args, preview=True, language='German', steps=30, seed=123)
            self.model.generate.assert_called_once_with(text='(Warm voice, Speak in German)Hallo Welt.',
                                                        cfg_value=2.0, inference_timesteps=30)
            self.torch.manual_seed.assert_called_with(123)
            config = json.loads((folder / 'manifest.json').read_text())
            self.assertEqual((config['language'], config['steps'], config['seed']), ('German', 30, 123))
            self.assertEqual(generate(*args, preview=True, language='German', steps=30, seed=123), folder)
            self.assertEqual(self.model.generate.call_count, 1)
            other = generate(*args, preview=True, language='German', steps=30, seed=124)
            self.assertNotEqual(folder, other)
            self.factory.assert_called_once_with('cached-model', load_denoiser=False)
            self.snapshot.assert_called_once_with(repo_id=MODEL_ID, revision=MODEL_REVISION,
                                                   local_files_only=False)
            self.assertEqual(config['cache_version'], CACHE_VERSION)
            self.assertEqual(config['model_revision'], MODEL_REVISION)

    def test_compatibility_changes_create_separate_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ([(0, Chapter('Test', 'Hello.'))], directory, '', '',
                    threading.Event(), lambda *args: None)
            folder = generate(*args, preview=True)
            for setting, value in [('CACHE_VERSION', CACHE_VERSION + 1),
                                   ('MODEL_REVISION', 'another-revision'),
                                   ('MODEL_ID', 'another-model')]:
                with self.subTest(setting=setting), patch('core.' + setting, value):
                    self.assertNotEqual(generate(*args, preview=True), folder)

    def test_content_and_settings_changes_create_separate_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.write_bytes(b'first reference')
            chapters = [(0, Chapter('Test', 'Hello.'))]
            base = dict(chapters=chapters, destination=directory, reference=str(reference),
                        style='', stop=threading.Event(), report=lambda *args: None)
            folder = generate(**base)
            changes = [
                {'chapters': [(1, Chapter('Test', 'Hello.'))]},
                {'chapters': [(0, Chapter('New title', 'Hello.'))]},
                {'chapters': [(0, Chapter('Test', 'Different text.'))]},
                {'style': 'Warm'}, {'language': 'German'}, {'steps': 30},
                {'seed': 123}, {'preview': True},
            ]
            for change in changes:
                with self.subTest(change=change):
                    self.assertNotEqual(generate(**(base | change)), folder)
            reference.write_bytes(b'different reference')
            self.assertNotEqual(generate(**base), folder)

    def test_cached_only_snapshot_uses_the_pinned_revision(self):
        self.assertEqual(model_snapshot(local_files_only=True), 'cached-model')
        self.snapshot.assert_called_once_with(repo_id=MODEL_ID, revision=MODEL_REVISION,
                                               local_files_only=True)

    def test_preview_keeps_all_paragraphs(self):
        with tempfile.TemporaryDirectory() as directory:
            text = 'First paragraph.\n\nSecond paragraph.'
            generate([(0, Chapter('Voice test', text))], directory, '', '',
                     threading.Event(), lambda *args: None, preview=True)
            self.assertEqual(self.model.generate.call_args.kwargs['text'], text)

    def test_preview_rejects_invalid_text_before_loading_model(self):
        for chapters in ([], [(0, Chapter('Empty', ' '))], [(0, Chapter('Long', 'x' * 401))]):
            with self.subTest(chapters=chapters), self.assertRaises(ValueError):
                generate(chapters, 'unused', '', '', threading.Event(), lambda *args: None, preview=True)
        self.factory.assert_not_called()

    def test_truncated_cached_passage_is_regenerated(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ([(0, Chapter('Test', 'Hello.'))], directory, '', '',
                    threading.Event(), lambda *args: None)
            folder = generate(*args, preview=True)
            segment = next((folder / 'segments').glob('*.wav'))
            original = segment.read_bytes()
            for removed in (1, 200):
                with self.subTest(removed=removed):
                    segment.write_bytes(original[:-removed])
                    with self.assertRaisesRegex(ValueError, 'truncated'):
                        validate_wav(segment)
                    generate(*args, preview=True)
                    self.assertEqual(segment.read_bytes(), original)
            self.assertEqual(self.model.generate.call_count, 3)

    def test_invalid_wav_headers_and_empty_audio_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'audio.wav'
            for data in (b'', b'not a WAV'):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    validate_wav(path)
            with wave.open(str(path), 'wb') as audio:
                audio.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            with self.assertRaisesRegex(ValueError, 'no audio'):
                validate_wav(path)

    def test_stop_retains_passages_for_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            stop = threading.Event()
            def report(text, value):
                if text == 'Completed 1/2 passages':
                    stop.set()
            reference = Path(directory) / 'reference.wav'
            reference.write_bytes(b'reference')
            args = ([(0, Chapter('Test', 'First.\n\nSecond.'))], directory, str(reference), '', stop, report)
            folder = generate(*args)
            self.assertEqual(len(list((folder / 'segments').glob('*.wav'))), 1)
            self.assertFalse(list(folder.glob('*.wav')))
            stop.clear()
            generate(args[0], directory, str(reference), '', stop, lambda *args: None)
            self.assertEqual(self.model.generate.call_count, 2)
            validate_wav(next(folder.glob('*.wav')))

    def test_synthesis_failure_preserves_completed_passages(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.write_bytes(b'reference')
            args = ([(0, Chapter('Test', 'First.\n\nSecond.'))], directory, str(reference), '',
                    threading.Event(), lambda *args: None)
            self.model.generate.side_effect = [[0.1] * 100, RuntimeError('Synthesis failed')]
            with self.assertRaisesRegex(RuntimeError, 'Synthesis failed'):
                generate(*args)
            folder = next(Path(directory).glob('book-*'))
            segment = next((folder / 'segments').glob('*.wav'))
            original = segment.read_bytes()
            self.model.generate.side_effect = None
            generate(*args)
            self.assertEqual(self.model.generate.call_count, 3)
            self.assertEqual(segment.read_bytes(), original)
            validate_wav(next(folder.glob('*.wav')))

    def test_audio_order_and_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / f'{i}.wav' for i in range(2)]
            for i, path in enumerate(paths):
                with wave.open(str(path), 'wb') as w:
                    w.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                    w.writeframes(bytes([i + 1, 0]) * 800)
            output = Path(directory) / 'joined.wav'
            join_wavs(paths, output)
            with wave.open(str(output), 'rb') as w:
                self.assertEqual(w.getnframes(), 3600)
                self.assertEqual(w.readframes(800), b'\x01\x00' * 800)
                self.assertEqual(w.readframes(2000), b'\0' * 4000)
                self.assertEqual(w.readframes(800), b'\x02\x00' * 800)


if __name__ == '__main__':
    unittest.main()
