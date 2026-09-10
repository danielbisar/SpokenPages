import tempfile
import unittest
import wave
import zipfile
import json
import threading
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from pathlib import Path
from core import Chapter, generate, load_model, join_wavs, narration_prompt, read_epub, split_text


class CoreTests(unittest.TestCase):
    def setUp(self):
        load_model.cache_clear()
        self.addCleanup(load_model.cache_clear)

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
        model = MagicMock()
        model.generate.return_value = [0.1] * 100
        model.tts_model.sample_rate = 48000
        factory = MagicMock(return_value=model)
        torch = MagicMock()
        def write(path, samples, rate, subtype):
            with wave.open(path, 'wb') as audio:
                audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
                audio.writeframes(b'\x01\x00' * len(samples))
        modules = {'torch': torch, 'soundfile': SimpleNamespace(write=write),
                   'voxcpm': SimpleNamespace(VoxCPM=SimpleNamespace(from_pretrained=factory))}
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', modules):
            args = ([(0, Chapter('Test', 'Hallo Welt.'))], directory, '', 'Warm voice',
                    threading.Event(), lambda *args: None)
            folder = generate(*args, preview=True, language='German', steps=30, seed=123)
            model.generate.assert_called_once_with(text='(Warm voice, Speak in German)Hallo Welt.',
                                                   cfg_value=2.0, inference_timesteps=30)
            torch.manual_seed.assert_called_with(123)
            config = json.loads((folder / 'manifest.json').read_text())
            self.assertEqual((config['language'], config['steps'], config['seed']), ('German', 30, 123))
            self.assertEqual(generate(*args, preview=True, language='German', steps=30, seed=123), folder)
            self.assertEqual(model.generate.call_count, 1)
            other = generate(*args, preview=True, language='German', steps=30, seed=124)
            self.assertNotEqual(folder, other)
            factory.assert_called_once()

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
