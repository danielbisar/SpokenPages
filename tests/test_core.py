import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from core import join_wavs, read_epub, split_text


class CoreTests(unittest.TestCase):
    def test_spine_order_and_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'book.epub'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
                z.writestr('OPS/book.opf', '<package><metadata><title>Example</title></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/><item id="n" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/></manifest><spine><itemref idref="b"/><itemref idref="n"/><itemref idref="a"/></spine></package>')
                z.writestr('OPS/a.xhtml', '<h1>First</h1><p>A &amp; B</p>')
                z.writestr('OPS/b.xhtml', '<h1>Second</h1><script>hidden</script><p>Visible.</p>')
            title, chapters = read_epub(path)
            self.assertEqual(title, 'Example')
            self.assertEqual([c.title for c in chapters], ['Second', 'First'])
            self.assertNotIn('hidden', chapters[0].text)
            self.assertIn('A & B', chapters[1].text)

    def test_split_preserves_content_and_bounds(self):
        for text in ['A long sentence. ' * 100, '很长的文字。' * 300, 'x' * 1001]:
            parts = split_text(text)
            self.assertTrue(all(0 < len(p) <= 400 for p in parts))
            self.assertEqual(''.join(''.join(parts).split()), ''.join(text.split()))

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
