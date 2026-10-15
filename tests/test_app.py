"""UI integration checks; skipped if Tcl/Tk cannot initialize."""
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from app import App
from core import Chapter
from voices import VoiceLibrary


class AppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            if os.environ.get('SPOKENPAGES_REQUIRE_TK') == '1':
                raise
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        with patch('app.VoiceLibrary', return_value=VoiceLibrary(Path(self.directory.name) / 'voices')):
            self.app = App(self.root)
        self.addCleanup(self.app.executor.shutdown, wait=True)
        self.app.destination.set(self.directory.name)

    def test_book_uses_saved_voice_not_unsaved_draft(self):
        a = self.app
        a.voice_name.set('My narrator')
        reference = Path(self.directory.name) / 'reference.wav'
        reference.write_bytes(b'reference audio')
        a.reference.set(str(reference))
        a.voice_style.set('Saved direction')
        a.seed.set('123')
        a.save_voice()
        a.voice_style.set('Unsaved direction')
        a.seed.set('456')
        a.language.set('German')
        a.chapters = [Chapter('Chapter', 'Hallo Welt.')]
        a.listbox.insert('end', 'Chapter')
        a.listbox.selection_set(0)
        with patch('app.generate', return_value=Path(self.directory.name)) as generate, patch.object(a.executor, 'submit', side_effect=lambda work: work()):
            a.start(False)
            a.poll()
        self.assertEqual(generate.call_args.args[3], 'Saved direction')
        self.assertEqual(generate.call_args.kwargs['seed'], 123)
        self.assertEqual(generate.call_args.kwargs['language'], 'German')
        self.assertEqual(str(a.voice_selector.cget('state')), 'readonly')
        self.assertFalse(a.busy)

    def test_reload_named_voice_and_test_without_book(self):
        a = self.app
        a.voice_name.set('Test narrator')
        a.test_language.set('French')
        a.save_voice()
        a.new_voice()
        a.edit_voice.set('Test narrator')
        a.load_voice()
        self.assertEqual(a.test_language.get(), 'French')
        with patch('app.generate', return_value=Path(self.directory.name)) as generate, patch.object(a.executor, 'submit', side_effect=lambda work: work()):
            a.start(True)
            a.poll()
        self.assertTrue(generate.call_args.args[6])
        self.assertEqual(generate.call_args.kwargs['language'], 'French')

    def test_book_without_reference_opens_voice_setup(self):
        a = self.app
        a.voice_name.set('Unanchored narrator')
        a.save_voice()
        a.chapters = [Chapter('Copyright', 'Copyright text.')]
        a.listbox.insert('end', 'Copyright')
        a.select_all()
        self.assertIn('1 of 1 sections', a.selection_summary.cget('text'))
        with patch('app.messagebox.showinfo'), patch('app.generate') as generate:
            a.start(False)
        generate.assert_not_called()
        self.assertEqual(a.tabs.index(a.tabs.select()), 1)
        self.assertFalse(a.busy)
        a.clear_selection()
        self.assertIn('0 of 1 sections', a.selection_summary.cget('text'))

    def test_worker_failure_retains_traceback_and_restores_inputs(self):
        a = self.app
        with patch('app.generate', side_effect=RuntimeError('Synthesis failed')), \
                patch.object(a.executor, 'submit', side_effect=lambda work: work()), \
                patch('app.traceback.print_exc') as traceback, \
                patch('app.messagebox.showerror') as showerror:
            a.start(True)
            a.poll()
        traceback.assert_called_once()
        self.assertIn('Synthesis failed', showerror.call_args.args[1])
        self.assertFalse(a.busy)
        self.assertEqual(str(a.voice_selector.cget('state')), 'readonly')
