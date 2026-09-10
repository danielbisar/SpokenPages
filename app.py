"""Audiobook native Windows desktop interface."""
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from core import generate, read_epub


class App:
    def __init__(self, root):
        self.root = root
        self.chapters = []
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        root.title('Audiobook — EPUB to Audiobook')
        root.geometry('900x760')
        root.minsize(720, 620)
        root.configure(bg='#f4f1ea')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#f4f1ea')
        style.configure('TLabel', background='#f4f1ea', foreground='#223d36', font=('Segoe UI', 11))
        style.configure('TButton', padding=9, font=('Segoe UI', 10))
        frame = ttk.Frame(root, padding=26)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Audiobook', font=('Georgia', 30)).pack(anchor='w')
        ttk.Label(frame, text='Turn your reading shelf into a listening library.').pack(anchor='w', pady=(0, 18))
        self.open_button = ttk.Button(frame, text='1. Open EPUB', command=self.open_book)
        self.open_button.pack(anchor='w')
        self.title = ttk.Label(frame, text='Choose a book to see its chapters.')
        self.title.pack(anchor='w', pady=10)
        self.listbox = tk.Listbox(frame, selectmode='extended', exportselection=False, height=9,
                                 font=('Segoe UI', 11), bg='white', relief='flat', selectbackground='#356b59')
        self.listbox.pack(fill='both', expand=True)
        ttk.Label(frame, text='Ctrl-click to choose chapters. All chapters are selected initially.').pack(anchor='w', pady=5)
        self.reference = tk.StringVar()
        self.voice_style = tk.StringVar(value='Calm, clear audiobook narrator, measured pace')
        self.destination = tk.StringVar(value=str(Path(__file__).resolve().parent / 'audiobooks'))
        self.inputs = [self.open_button]
        for label, variable, command in [
            ('2. Voice reference (optional WAV)', self.reference, self.pick_voice),
            ('3. Save audiobook to', self.destination, self.pick_destination),
        ]:
            ttk.Label(frame, text=label).pack(anchor='w', pady=(9, 3))
            row = ttk.Frame(frame)
            row.pack(fill='x')
            entry = ttk.Entry(row, textvariable=variable)
            entry.pack(side='left', fill='x', expand=True)
            button = ttk.Button(row, text='Browse', command=command)
            button.pack(side='right', padx=(8, 0))
            self.inputs.extend([entry, button])
        ttk.Label(frame, text='Narrator direction').pack(anchor='w', pady=(9, 3))
        entry = ttk.Entry(frame, textvariable=self.voice_style)
        entry.pack(fill='x')
        self.inputs.append(entry)
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=14)
        for label, command in [('Preview first passage', lambda: self.start(True)),
                               ('Generate audiobook', lambda: self.start(False))]:
            button = ttk.Button(row, text=label, command=command)
            button.pack(side='left', padx=(0, 8))
            self.inputs.append(button)
        ttk.Button(row, text='Stop after passage', command=self.stop.set).pack(side='left')
        ttk.Button(row, text='Open output', command=self.open_output).pack(side='right')
        self.progress = ttk.Progressbar(frame, maximum=1)
        self.progress.pack(fill='x')
        self.status = ttk.Label(frame, text='Ready • VoxCPM2 • local generation', wraplength=810)
        self.status.pack(anchor='w', pady=8)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.poll)

    def open_book(self):
        path = filedialog.askopenfilename(filetypes=[('EPUB books', '*.epub')])
        if not path:
            return
        try:
            title, chapters = read_epub(path)
            self.chapters = chapters
            self.title.configure(text=f'{title} — {len(chapters)} sections')
            self.listbox.delete(0, 'end')
            for i, chapter in enumerate(chapters):
                self.listbox.insert('end', f'{i + 1:02d}   {chapter.title}')
            self.listbox.selection_set(0, 'end')
        except Exception as error:
            messagebox.showerror('Cannot read EPUB', str(error))

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
        if not selected:
            messagebox.showinfo('Select chapters', 'Open an EPUB and select at least one chapter.')
            return
        reference = self.reference.get().strip()
        if reference and not Path(reference).is_file():
            messagebox.showerror('Missing reference', 'Choose an existing WAV voice reference.')
            return
        destination = self.destination.get().strip()
        if not destination:
            messagebox.showerror('Missing destination', 'Choose an output folder.')
            return
        direction = self.voice_style.get().strip()
        self.busy = True
        self.stop.clear()
        for control in self.inputs:
            control.configure(state='disabled')
        self.status.configure(text='Starting…')
        self.progress['value'] = 0
        def worker():
            try:
                generate(selected, destination, reference, direction, self.stop,
                         lambda text, value: self.events.put(('progress', text, value)), preview)
            except Exception as error:
                self.events.put(('error', str(error), 0))
            finally:
                self.events.put(('done', '', 0))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind, text, value = self.events.get_nowait()
            if kind == 'done':
                self.busy = False
                for control in self.inputs:
                    control.configure(state='normal')
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
            self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
