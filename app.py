"""Audiobook native Windows desktop interface."""
import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from core import Chapter, generate, read_epub
from voices import VoiceLibrary

LANGUAGES = ['Auto (from text)', 'English', 'German', 'French', 'Spanish', 'Italian', 'Portuguese', 'Chinese', 'Japanese', 'Korean']


class App:
    def __init__(self, root):
        self.root = root
        self.chapters = []
        self.events = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.stop = threading.Event()
        self.busy = False
        self.last_preview = None
        root.title('Audiobook — EPUB to Audiobook')
        root.geometry('980x820')
        root.minsize(760, 600)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', font=('Segoe UI', 11))
        style.configure('TButton', padding=7, font=('Segoe UI', 10))
        base = Path(__file__).resolve().parent
        self.library = VoiceLibrary(base / 'voices')
        self.inputs = []
        self.reference = tk.StringVar()
        self.voice_style = tk.StringVar(value='Calm, clear audiobook narrator, measured pace')
        self.destination = tk.StringVar(value=str(base / 'audiobooks'))
        self.language = tk.StringVar(value='Auto (from text)')
        self.test_language = tk.StringVar(value='Auto (from text)')
        self.steps = tk.StringVar(value='20')
        self.seed = tk.StringVar(value='42')
        self.voice_name = tk.StringVar()
        self.selected_voice = tk.StringVar()
        self.edit_voice = tk.StringVar()
        shell = ttk.Frame(root, padding=16)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='Audiobook', font=('Georgia', 26)).pack(anchor='w')
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill='both', expand=True, pady=8)
        book = self.make_tab('Book generation')
        voice = self.make_tab('Voice setup')
        self.voice_tab = 1
        self.button(book, 'Open EPUB', self.open_book)
        self.title = ttk.Label(book, text='Choose a book to see its chapters.', wraplength=700)
        self.title.pack(anchor='w', pady=8)
        self.listbox = tk.Listbox(book, selectmode='extended', exportselection=False, height=9,
                                 font=('Segoe UI', 11))
        self.listbox.pack(fill='x')
        self.inputs.append(self.listbox)
        self.listbox.bind('<<ListboxSelect>>', lambda event: self.update_selection())
        selection = ttk.Frame(book)
        selection.pack(fill='x')
        self.button(selection, 'Select all sections', self.select_all, side='left')
        self.button(selection, 'Clear selection', self.clear_selection, side='left')
        self.selection_summary = ttk.Label(book, text='No sections selected.', wraplength=700)
        self.selection_summary.pack(anchor='w', pady=4)
        ttk.Label(book, text='Ctrl-click to choose chapters. All chapters are selected initially.').pack(anchor='w', pady=5)
        ttk.Label(book, text='Narrator voice').pack(anchor='w', pady=(10, 3))
        self.voice_selector = self.combo(book, self.selected_voice, [], readonly=True)
        self.voice_summary = ttk.Label(book, text='', wraplength=700)
        self.voice_summary.pack(anchor='w', pady=4)
        self.voice_selector.bind('<<ComboboxSelected>>', lambda event: self.show_voice_summary())
        self.button(book, 'Set up voices', lambda: self.tabs.select(self.voice_tab))
        ttk.Label(book, text='Book language (from EPUB metadata; you can override it)').pack(anchor='w', pady=(10, 3))
        self.combo(book, self.language, LANGUAGES)
        self.path_row(book, 'Save audiobook to', self.destination, self.pick_destination)
        self.button(book, 'Generate audiobook', lambda: self.start(False))

        ttk.Label(voice, text='Create a narrator, test it, then save it with your own name.', wraplength=700).pack(anchor='w')
        self.edit_selector = self.combo(voice, self.edit_voice, [], readonly=True)
        self.edit_selector.bind('<<ComboboxSelected>>', lambda event: self.load_voice())
        self.button(voice, 'New voice', self.new_voice)
        ttk.Label(voice, text='Voice name').pack(anchor='w', pady=(8, 3))
        self.entry(voice, self.voice_name)
        self.path_row(voice, 'Voice reference (optional WAV)', self.reference, self.pick_voice)
        ttk.Label(voice, text='Narrator direction').pack(anchor='w', pady=(8, 3))
        self.entry(voice, self.voice_style)
        presets = ttk.Frame(voice)
        presets.pack(fill='x', pady=6)
        for label, direction in [
            ('Warm storyteller', 'Warm mature voice, natural storytelling, clear diction, relaxed pace'),
            ('Clear nonfiction', 'Clear neutral adult voice, conversational nonfiction narration, steady pace'),
            ('Gentle narrator', 'Soft low adult voice, gentle expressive narration, unhurried pace'),
        ]:
            self.button(presets, label, lambda d=direction: self.voice_style.set(d), side='left')
        settings = ttk.Frame(voice)
        settings.pack(fill='x')
        for label, variable, values in [('Test language', self.test_language, LANGUAGES),
                                         ('Inference steps', self.steps, ['10', '20', '30']),
                                         ('Voice seed', self.seed, ['42', '123', '456', '789'])]:
            group = ttk.Frame(settings)
            group.pack(side='left', padx=(0, 10))
            ttk.Label(group, text=label).pack(anchor='w')
            self.combo(group, variable, values)
        ttk.Label(voice, text='More steps are slower. Change seed to audition another voice. Language is a hint, not translation.', wraplength=700).pack(anchor='w', pady=6)
        ttk.Label(voice, text='Voice test text (1–400 characters)').pack(anchor='w')
        self.test_text = tk.Text(voice, height=3, font=('Segoe UI', 11), wrap='word')
        self.test_text.insert('1.0', 'The morning light fell across the open book. A new story was about to begin.')
        self.test_text.pack(fill='x', pady=4)
        self.inputs.append(self.test_text)
        self.button(voice, 'Use selected book passage', self.use_book_text)
        playback = ttk.Frame(voice)
        playback.pack(fill='x')
        self.button(playback, 'Generate voice test', lambda: self.start(True), side='left')
        self.button(playback, 'Play last test', self.play_preview, side='left')
        self.button(voice, 'Use last test as voice reference', self.use_preview)
        ttk.Label(voice, text='Use a clean speech reference for a stable narrator. Saving copies the reference into your voice library.', wraplength=700).pack(anchor='w', pady=6)
        self.button(voice, 'Save voice / update matching name', self.save_voice)
        self.saved_status = ttk.Label(voice, text='', wraplength=700)
        self.saved_status.pack(anchor='w')
        footer = ttk.Frame(shell)
        footer.pack(fill='x')
        ttk.Button(footer, text='Stop after passage', command=self.stop.set).pack(side='left')
        ttk.Button(footer, text='Open output', command=self.open_output).pack(side='right')
        self.progress = ttk.Progressbar(shell, maximum=1)
        self.progress.pack(fill='x', pady=5)
        self.status = ttk.Label(shell, text='Ready • VoxCPM2 • local generation', wraplength=700)
        self.status.pack(anchor='w')
        self.refresh_voices()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.poll)

    def make_tab(self, title):
        page = ttk.Frame(self.tabs)
        self.tabs.add(page, text=title)
        canvas = tk.Canvas(page, highlightthickness=0)
        scrollbar = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        content = ttk.Frame(canvas, padding=12)
        window = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
        return content

    def button(self, parent, text, command, side='top'):
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side=side, anchor='w', pady=4, padx=(0, 6))
        self.inputs.append(button)
        return button

    def entry(self, parent, variable):
        entry = ttk.Entry(parent, textvariable=variable)
        entry.pack(fill='x')
        self.inputs.append(entry)

    def combo(self, parent, variable, values, readonly=False):
        control = ttk.Combobox(parent, textvariable=variable, values=values,
                               state='readonly' if readonly else 'normal', width=20)
        control.pack(fill='x', pady=3)
        self.inputs.append(control)
        return control

    def path_row(self, parent, label, variable, command):
        ttk.Label(parent, text=label).pack(anchor='w', pady=(8, 3))
        row = ttk.Frame(parent)
        row.pack(fill='x')
        self.button(row, 'Browse', command, side='right')
        self.entry(row, variable)

    def refresh_voices(self, selected=None):
        names = sorted(self.library.voices, key=str.casefold)
        self.voice_selector.configure(values=names)
        self.edit_selector.configure(values=names)
        self.selected_voice.set(selected or (names[0] if names else ''))
        self.show_voice_summary()

    def show_voice_summary(self):
        name = self.selected_voice.get()
        if name in self.library.voices:
            voice = self.library.get(name)
            readiness = 'Reference saved' if voice['reference'] else 'Needs a reference: test this voice, use the test as reference, then save it'
            self.voice_summary.configure(text=f"{voice['style']} • {voice['steps']} steps • {readiness}")
        else:
            self.voice_summary.configure(text='No saved voices yet. Create one in Voice setup to get started.')

    def new_voice(self):
        self.edit_voice.set('')
        self.voice_name.set('')
        self.reference.set('')
        self.voice_style.set('Calm, clear audiobook narrator, measured pace')
        self.seed.set('42')
        self.steps.set('20')
        self.test_language.set('Auto (from text)')
        self.last_preview = None
        self.saved_status.configure(text='New voice. Enter a name and save when ready.')

    def load_voice(self):
        name = self.edit_voice.get()
        if name not in self.library.voices:
            return
        voice = self.library.get(name)
        self.voice_name.set(name)
        self.reference.set(voice['reference'])
        self.voice_style.set(voice['style'])
        self.seed.set(str(voice['seed']))
        self.steps.set(str(voice['steps']))
        self.test_language.set(voice['language'] or 'Auto (from text)')
        self.last_preview = None
        self.saved_status.configure(text='Editing saved voice. Save to apply changes; a different name creates a copy.')

    def draft_voice(self):
        try:
            voice = dict(style=self.voice_style.get().strip(), reference=self.reference.get().strip(),
                         seed=int(self.seed.get()), steps=int(self.steps.get()),
                         language=self.test_language.get().strip())
        except ValueError:
            raise ValueError('Steps and seed must be whole numbers.') from None
        if voice['language'] == 'Auto (from text)':
            voice['language'] = ''
        VoiceLibrary.validate('Draft', voice)
        return voice

    def save_voice(self):
        try:
            name = self.library.save(self.voice_name.get(), self.draft_voice())
            self.refresh_voices(name)
            self.edit_voice.set(name)
            self.reference.set(self.library.get(name)['reference'])
            self.saved_status.configure(text=f'Saved “{name}”. Selected on the Book generation tab.')
        except (OSError, ValueError) as error:
            messagebox.showerror('Cannot save voice', str(error))

    def use_book_text(self):
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showinfo('Book passage', 'Open a book and select a chapter first.')
            return
        self.test_text.delete('1.0', 'end')
        self.test_text.insert('1.0', self.chapters[selected[0]].text[:400])
        self.test_language.set(self.language.get())

    def select_all(self):
        self.listbox.selection_set(0, 'end')
        self.update_selection()

    def clear_selection(self):
        self.listbox.selection_clear(0, 'end')
        self.update_selection()

    def update_selection(self):
        selected = self.listbox.curselection()
        words = sum(len(self.chapters[i].text.split()) for i in selected)
        self.selection_summary.configure(text=f'{len(selected)} of {len(self.chapters)} sections selected • {words:,} words. Only selected sections will be generated.')

    def open_book(self):
        path = filedialog.askopenfilename(filetypes=[('EPUB books', '*.epub')])
        if not path:
            return
        try:
            title, chapters, language = read_epub(path, include_language=True)
            self.language.set(language or 'Auto (from text)')
            self.chapters = chapters
            self.title.configure(text=f'{title} — {len(chapters)} sections')
            self.listbox.delete(0, 'end')
            for i, chapter in enumerate(chapters):
                self.listbox.insert('end', f'{i + 1:02d}   {chapter.title}   ({len(chapter.text.split()):,} words)')
            self.listbox.selection_set(0, 'end')
            self.update_selection()
        except Exception as error:
            messagebox.showerror('Cannot read EPUB', str(error))

    def play_preview(self):
        if self.last_preview and self.last_preview.is_file():
            os.startfile(str(self.last_preview))
        else:
            messagebox.showinfo('Voice test', 'Generate a voice test first.')

    def use_preview(self):
        if self.last_preview and self.last_preview.is_file():
            self.reference.set(str(self.last_preview))
        else:
            messagebox.showinfo('Voice test', 'Generate a voice test first.')

    def pick_voice(self):
        path = filedialog.askopenfilename(filetypes=[('WAV audio', '*.wav')])
        if path:
            self.reference.set(path)

    def pick_destination(self):
        path = filedialog.askdirectory()
        if path:
            self.destination.set(path)

    def open_output(self):
        path = Path(self.destination.get())
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def start(self, preview):
        if self.busy:
            return
        selected = [(i, self.chapters[i]) for i in self.listbox.curselection()]
        if preview:
            text = self.test_text.get('1.0', 'end').strip()
            if not text or len(text) > 400:
                messagebox.showerror('Voice test text', 'Enter between 1 and 400 characters.')
                return
            selected = [(0, Chapter('Voice test', text))]
        try:
            if preview:
                voice = self.draft_voice()
            else:
                if self.selected_voice.get() not in self.library.voices:
                    messagebox.showinfo('Choose a voice', 'Save a voice in Voice setup, then select it for the book.')
                    self.tabs.select(self.voice_tab)
                    return
                voice = self.library.get(self.selected_voice.get())
        except ValueError as error:
            messagebox.showerror('Voice settings', str(error))
            return
        steps, seed = voice['steps'], voice['seed']
        language = voice['language'] if preview else self.language.get().strip()
        if language == 'Auto (from text)':
            language = ''
        if not selected:
            messagebox.showinfo('Select chapters', 'Open an EPUB and select at least one chapter.')
            return
        reference = voice['reference']
        if not preview and not reference:
            self.edit_voice.set(self.selected_voice.get())
            self.load_voice()
            self.tabs.select(self.voice_tab)
            messagebox.showinfo('Set a narrator reference',
                                'This voice only has a description, so its sound can change between passages.\n\nGenerate a voice test, choose Use last test as voice reference, then save the voice. You can also browse to a clean speech WAV.')
            return
        if reference and not Path(reference).is_file():
            messagebox.showerror('Missing reference', 'Choose an existing WAV voice reference.')
            return
        destination = self.destination.get().strip()
        if not destination:
            messagebox.showerror('Missing destination', 'Choose an output folder.')
            return
        direction = voice['style']
        self.busy = True
        self.stop.clear()
        self.input_states = [(control, str(control.cget('state'))) for control in self.inputs]
        for control in self.inputs:
            control.configure(state='disabled')
        self.status.configure(text='Starting…')
        self.progress['value'] = 0
        def worker():
            try:
                folder = generate(selected, destination, reference, direction, self.stop,
                         lambda text, value: self.events.put(('progress', text, value)), preview,
                         language=language, steps=steps, seed=seed)
                if preview and not self.stop.is_set():
                    files = sorted(folder.glob('*.wav'))
                    if files:
                        self.events.put(('preview', str(files[0]), 0))
            except Exception as error:
                self.events.put(('error', str(error), 0))
            finally:
                self.events.put(('done', '', 0))
        self.executor.submit(worker)

    def poll(self):
        while not self.events.empty():
            kind, text, value = self.events.get_nowait()
            if kind == 'done':
                self.busy = False
                for control, state in self.input_states:
                    control.configure(state=state)
            elif kind == 'preview':
                self.last_preview = Path(text)
                self.play_preview()
            elif kind == 'error':
                self.status.configure(text='Generation failed. Completed passages are retained.')
                messagebox.showerror('Generation failed', text + '\n\nSee README.md for setup requirements.')
            else:
                self.status.configure(text=text)
                self.progress['value'] = value
        self.root.after(150, self.poll)

    def close(self):
        if self.busy:
            self.stop.set()
            messagebox.showinfo('Stopping', 'Waiting for the current passage. Close again after generation stops.')
        else:
            self.executor.shutdown(wait=False)
            self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    try:
        App(root)
    except (OSError, ValueError) as error:
        messagebox.showerror('Cannot load voice library', str(error))
        root.destroy()
    else:
        root.mainloop()
