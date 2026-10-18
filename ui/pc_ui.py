import json
import secrets
import time
import tkinter as tk
from math import ceil
from tkinter import filedialog, messagebox, ttk

from audio.audio_player import LocalAudioPlayer
from engine import StoryEngine
from engine.book_engine import BookEngine


class PcUI:
    BG = "#f4f1e9"
    INK = "#242735"
    ACCENT = "#30485c"

    def __init__(self, root, content, debug=False, seed=None, arc=None, book=None):
        self.root, self.content = root, content
        self.engine = None
        self.initial_seed, self.initial_arc = seed, arc
        self.active_tale_arc = arc
        self.setup_kind = "library"
        self.active_book_id = "passeuse_ch1"
        self.illustration = None
        self.pilot_plots_seen = set()
        self.pressed_choice_keys = set()
        self.last_choice_time = 0
        self.audio_poll = None
        self.audio_controls = None
        self.debug = tk.BooleanVar(value=debug)
        self.audio = LocalAudioPlayer(content.root, content.config["audio_root"],
                                      lead_in_ms=content.config.get("audio_lead_in_ms", 800))
        self.root.title("Les Portes de l'Imaginaire — Histoires interactives")
        self.root.geometry("1100x800")
        self.root.minsize(800, 620)
        self.root.configure(bg=self.BG)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.INK, font=("Segoe UI", 11))
        style.configure("Title.TLabel", font=("Georgia", 25), foreground=self.ACCENT)
        style.configure("Sub.TLabel", font=("Segoe UI", 11), foreground="#57636c")
        style.configure("TButton", font=("Segoe UI", 12), padding=(16, 12))
        style.configure("Audio.TButton", font=("Segoe UI", 11), padding=(10, 8))
        style.configure("Reader.TFrame", background="#fffdf7")
        style.configure("Reader.TLabel", background="#fffdf7", font=("Segoe UI", 10),
                        foreground="#57636c")
        style.configure("Primary.TButton", background=self.ACCENT, foreground="white")
        style.map("Primary.TButton", background=[("active", "#45657e"), ("disabled", "#84959f")])
        style.configure("TRadiobutton", background=self.BG, font=("Segoe UI", 11), padding=(8, 9))
        menu = tk.Menu(root)
        adventure = tk.Menu(menu, tearoff=False)
        adventure.add_command(label="Choisir une histoire", command=self.home)
        adventure.add_command(label="Recommencer cette histoire", command=self.restart)
        adventure.add_separator()
        adventure.add_command(label="Quitter", command=self.close)
        menu.add_cascade(label="Aventure", menu=adventure)
        tools = tk.Menu(menu, tearoff=False)
        tools.add_checkbutton(label="Mode debug", variable=self.debug, command=self.toggle_debug)
        tools.add_command(label="Enregistrer le journal…", command=self.save_session)
        tools.add_command(label="Rejouer un journal…", command=self.open_session)
        menu.add_cascade(label="Outils", menu=tools)
        root.config(menu=menu)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.page = ttk.Frame(root, padding=(32, 24))
        self.page.pack(fill="both", expand=True)
        self.root.bind("<KeyPress-a>", lambda e: self.keyboard_choice(0, e.keysym))
        self.root.bind("<KeyPress-b>", lambda e: self.keyboard_choice(1, e.keysym))
        self.root.bind("<KeyPress-1>", lambda e: self.keyboard_choice(0, e.keysym))
        self.root.bind("<KeyPress-2>", lambda e: self.keyboard_choice(1, e.keysym))
        self.root.bind("<Left>", lambda e: self.keyboard_choice(0, e.keysym))
        self.root.bind("<Right>", lambda e: self.keyboard_choice(1, e.keysym))
        self.root.bind("<KeyRelease>", lambda e: self.pressed_choice_keys.discard(e.keysym))
        if book is not None:
            self.start_book(book)
        else:
            self.setup() if arc is not None else self.home()

    def clear(self):
        if self.audio_poll is not None:
            self.root.after_cancel(self.audio_poll)
            self.audio_poll = None
        self.audio_controls = None
        for widget in self.page.winfo_children():
            widget.destroy()
        self.illustration = None
        self.original_illustration = None
        self.illustration_factor = None
        self.reading_scene = None
        self.illustration_row = None

    def reset_reading(self):
        self.audio.stop()
        self.engine = None
        self.pressed_choice_keys.clear()
        self.last_choice_time = 0
        self.clear()

    def home(self):
        self.reset_reading()
        self.setup_kind = "library"
        ttk.Label(self.page, text="Les Portes de l'Imaginaire", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.page, text="Choisis une histoire et ouvre sa première page.",
                  style="Sub.TLabel", wraplength=720).pack(anchor="w", pady=(10, 20))
        cards = [
            ("Le conte", "La Maison aux Sept Cages",
             "Retrouve Lison et délivre les enfants changés en oiseaux.\n"
             "Choisis ton héros, ton lieu et ton objet.", self.select_tale, "Ouvrir le conte"),
            ("Le livre", "La petite passeuse d'étoile",
             "Accompagne Alex dans une ville où chaque pas est imposé.\n"
             "Premier chapitre complet, illustré en noir et blanc.", self.start_book, "Ouvrir le livre"),
        ]
        for book_id, book in self.content.books.items():
            if book_id != "passeuse_ch1":
                cards.append((book.get("library_label", "Le conte"), book["title"],
                              book.get("library_description", "Deux choix à chaque étape."),
                              lambda selected=book_id: self.start_book(selected),
                              book.get("open_label", "Ouvrir cette histoire")))
        for title, subtitle, description, command, button_label in cards:
            frame = ttk.Frame(self.page, padding=(18, 12), relief="solid", borderwidth=1)
            frame.pack(fill="x", pady=(0, 12))
            ttk.Button(frame, text=button_label, style="Primary.TButton", command=command).pack(
                side="right", anchor="center", padx=(16, 0))
            ttk.Label(frame, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ttk.Label(frame, text=subtitle, font=("Georgia", 18), wraplength=430).pack(anchor="w", pady=(4, 5))
            ttk.Label(frame, text=description, style="Sub.TLabel", wraplength=430).pack(anchor="w")

    def select_tale(self):
        self.active_tale_arc = self.initial_arc or "cages"
        self.setup()

    def restart(self):
        if self.setup_kind == "book":
            self.start_book(self.engine.book["id"] if self.engine else self.active_book_id)
        elif self.setup_kind == "tale":
            self.setup()
        else:
            self.home()

    def start_book(self, book_id="passeuse_ch1"):
        self.reset_reading()
        self.setup_kind = "book"
        self.active_book_id = book_id
        self.engine = BookEngine(self.content, book_id)
        self.show_scene()

    def resize_reading_image(self, event):
        if event.widget != self.body or self.original_illustration is None:
            return
        available = self.reading_image_width(event.width)
        factor = max(1, ceil(self.original_illustration.width() / available))
        if factor != self.illustration_factor:
            self.illustration = self.original_illustration.subsample(factor)
            self.illustration_factor = factor
            self.image_label.configure(image=self.illustration)

    def reading_image_width(self, body_width):
        controls_width = self.audio_controls.winfo_reqwidth() if self.audio_controls else 150
        return max(200, min(600, body_width - 64 - controls_width - 24))

    def create_audio_controls(self, parent, horizontal=False):
        self.audio_controls = ttk.Frame(parent, style="Reader.TFrame", padding=(16, 8, 0, 8))
        self.audio_buttons = {}
        for key, label, command in (
            ("play", "▶ Lecture", self.resume_audio),
            ("pause", "⏸ Pause", self.pause_audio),
            ("replay", "↺ Rejouer", self.replay_audio),
        ):
            button = ttk.Button(self.audio_controls, text=label, width=11,
                                style="Audio.TButton", command=command, state="disabled")
            if horizontal:
                button.pack(side="left", padx=(0, 8))
            else:
                button.pack(fill="x", pady=(0, 8))
            self.audio_buttons[key] = button
        self.audio_status = ttk.Label(self.audio_controls, text="Audio indisponible",
                                      style="Reader.TLabel", wraplength=135)
        self.audio_status.pack(side="left" if horizontal else "top", anchor="w")
        return self.audio_controls

    def update_audio_controls(self):
        if self.audio_poll is not None:
            self.root.after_cancel(self.audio_poll)
            self.audio_poll = None
        if self.audio_controls is None:
            return
        state = self.audio.state
        available = state != "unavailable"
        self.audio_buttons["play"].configure(state="normal" if available and state != "playing" else "disabled")
        self.audio_buttons["pause"].configure(state="normal" if state == "playing" else "disabled")
        self.audio_buttons["replay"].configure(state="normal" if available else "disabled")
        self.audio_status.configure(text={"playing": "Lecture en cours", "paused": "En pause",
                                          "ready": "Prêt à écouter", "unavailable": "Audio indisponible"}[state])
        if available:
            self.audio_poll = self.root.after(250, self.update_audio_controls)

    def resume_audio(self):
        self.audio.resume()
        self.update_audio_controls()

    def pause_audio(self):
        self.audio.pause()
        self.update_audio_controls()

    def replay_audio(self):
        self.audio.replay()
        self.update_audio_controls()

    def play_audio(self, segment_id, audio_file=None):
        lead_in = self.content.config.get("audio_lead_in_ms", 800)
        if isinstance(self.engine, BookEngine):
            lead_in = self.engine.book.get("audio_lead_in_ms", lead_in)
        self.audio.lead_in_ms = lead_in
        self.audio.play(segment_id, audio_file)
        self.update_audio_controls()


    def setup(self):
        self.reset_reading()
        self.setup_kind = "tale"
        ttk.Label(self.page, text="Les Portes de l'Imaginaire", style="Title.TLabel").pack(anchor="w")
        subtitle = "La Maison aux Sept Cages · Un nouveau parcours à chaque aventure." if self.active_tale_arc == "cages" else "Trois envies. Une aventure. À toi d'en choisir le chemin."
        ttk.Label(self.page, text=subtitle,
                  style="Sub.TLabel").pack(anchor="w", pady=(8, 26))
        options = ttk.Frame(self.page)
        options.pack(fill="x", pady=4)
        self.hero, self.location, self.item = tk.StringVar(), tk.StringVar(), tk.StringVar()
        columns = [("1 · Quel type de héros veux-tu être ?", self.content.heroes, self.hero),
                   ("2 · Quel lieu veux-tu rencontrer ?", self.content.locations, self.location),
                   ("3 · Quel objet veux-tu posséder ?", self.content.items, self.item)]
        for i, (question, entries, variable) in enumerate(columns):
            options.columnconfigure(i, weight=1, uniform="questions")
            frame = ttk.Frame(options, padding=(0, 0, 14, 0))
            frame.grid(row=0, column=i, sticky="nsew")
            ttk.Label(frame, text=question, wraplength=280, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 15))
            for entry in entries.values():
                label = entry["label"].replace(" / ", " /\n") if len(entry["label"]) > 27 else entry["label"]
                ttk.Radiobutton(frame, text=label, value=entry["id"], variable=variable,
                                command=self.check_ready).pack(anchor="w", fill="x")
        ttk.Label(self.page, text="Une aventure complète dure environ 20 minutes.\n"
                  "Lis à ton rythme : chaque choix ouvre une nouvelle possibilité.",
                  style="Sub.TLabel").pack(anchor="w", pady=(25, 16))
        self.start_button = ttk.Button(self.page, text="Commencer l'aventure", style="Primary.TButton",
                                        command=self.start, state="disabled")
        self.start_button.pack(anchor="w")
        self.debug_setup = ttk.Frame(self.page, padding=(0, 18))
        self.seed_var = tk.StringVar(value="" if self.initial_seed is None else str(self.initial_seed))
        self.arc_var = tk.StringVar(value=self.active_tale_arc or "Aléatoire")
        ttk.Label(self.debug_setup, text="DEBUG · Graine (vide = aléatoire)").grid(row=0, column=0, padx=(0, 12))
        ttk.Entry(self.debug_setup, textvariable=self.seed_var, width=22).grid(row=0, column=1)
        ttk.Label(self.debug_setup, text="Arc").grid(row=0, column=2, padx=12)
        ttk.Combobox(self.debug_setup, textvariable=self.arc_var,
                     values=["Aléatoire", *self.content.arcs], state="readonly", width=23).grid(row=0, column=3)
        if self.debug.get():
            self.debug_setup.pack(anchor="w")

    def check_ready(self):
        self.start_button.config(state="normal" if all(v.get() for v in (self.hero, self.location, self.item)) else "disabled")

    def start(self):
        try:
            seed_text = self.seed_var.get().strip() if self.debug.get() else ""
            seed = int(seed_text) if seed_text else None
            arc = self.arc_var.get() if self.debug.get() else (self.active_tale_arc or "Aléatoire")
            plot = None
            if arc == "cages" and not self.debug.get():
                available = {r["id"] for r in self.content.arcs[arc]["revelations"]}
                if self.pilot_plots_seen == available:
                    last = self.last_pilot_plot
                    self.pilot_plots_seen.clear()
                    available.discard(last)
                plot = secrets.choice(sorted(available - self.pilot_plots_seen))
            self.engine = StoryEngine(self.content, self.hero.get(), self.location.get(), self.item.get(),
                                      seed=seed, arc_id=None if arc == "Aléatoire" else arc, revelation_id=plot)
            if plot is not None:
                self.pilot_plots_seen.add(plot)
                self.last_pilot_plot = plot
            self.show_scene()
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Impossible de commencer", str(exc), parent=self.root)

    def story_layout(self, title, subtitle="", scene=None):
        self.clear()
        ttk.Label(self.page, text=title, style="Title.TLabel", wraplength=950).pack(anchor="w")
        if subtitle:
            ttk.Label(self.page, text=subtitle, style="Sub.TLabel").pack(anchor="w", pady=(6, 10))
        # Réserver la place des choix avant que le texte extensible ne la prenne.
        self.actions = ttk.Frame(self.page)
        self.actions.pack(side="bottom", fill="x", pady=(8, 0))
        self.body_frame = ttk.Frame(self.page)
        self.body_frame.pack(fill="both", expand=True, pady=(18, 10))
        self.reading_scene = scene
        self.body = tk.Text(self.body_frame, wrap="word", font=("Georgia", 14), bg="#fffdf7",
                            fg=self.INK, relief="flat", padx=24, pady=22, spacing1=4, spacing3=12,
                            height=12, takefocus=False, cursor="arrow")
        scrollbar = ttk.Scrollbar(self.body_frame, command=self.body.yview)
        self.body.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.body.pack(side="left", fill="both", expand=True)
        self.body.bind("<Configure>", self.resize_reading_image)
        self.debug_panel = tk.Text(self.page, height=8, font=("Consolas", 9), wrap="word", bg="#e7edf0", relief="flat")

    def set_text(self, text):
        self.body.config(state="normal")
        self.body.delete("1.0", "end")
        if self.reading_scene and self.reading_scene.get("image"):
            self.illustration_row = ttk.Frame(self.body, style="Reader.TFrame", name="chapter-illustration")
            controls = self.create_audio_controls(self.illustration_row)
            controls.pack(side="right", anchor="n")
            try:
                asset = (self.content.root / self.reading_scene["image"]).resolve()
                if not asset.is_relative_to(self.content.root.resolve()):
                    raise ValueError("Illustration hors projet")
                self.original_illustration = tk.PhotoImage(file=str(asset), master=self.root)
                available = self.reading_image_width(self.root.winfo_width() - 148)
                self.illustration_factor = max(1, ceil(self.original_illustration.width() / available))
                self.illustration = self.original_illustration.subsample(self.illustration_factor)
                self.image_label = tk.Label(self.illustration_row, image=self.illustration,
                                            bg="#fffdf7", borderwidth=0)
                self.image_label.pack(side="left", anchor="n")
            except (tk.TclError, OSError, ValueError):
                self.original_illustration = None
                ttk.Label(self.illustration_row, text=self.reading_scene["image_alt"],
                          style="Reader.TLabel", wraplength=350).pack(side="left", anchor="n")
            self.body.window_create("end", window=self.illustration_row)
            self.body.insert("end", "\n\n")
            self.body.tag_configure("illustration", justify="center")
            self.body.tag_add("illustration", "1.0", "2.0")
        elif self.reading_scene:
            self.illustration_row = ttk.Frame(self.body, style="Reader.TFrame")
            self.create_audio_controls(self.illustration_row, horizontal=True).pack(anchor="w")
            self.body.window_create("end", window=self.illustration_row)
            self.body.insert("end", "\n\n")
        self.body.insert("end", text)
        self.body.yview_moveto(0)
        self.body.config(state="disabled")

    def show_scene(self):
        scene = self.engine.current
        is_book = isinstance(self.engine, BookEngine)
        if is_book:
            chapter = f" · Chapitre {self.engine.book['chapter']}" if self.engine.book.get("chapter") else ""
            subtitle = f"{self.engine.book['title']}{chapter} · Passage {scene['rank']}/{len(self.engine.scenes)}"
        else:
            subtitle = "Les Portes de l'Imaginaire"
        self.story_layout(scene["title"], subtitle, scene)
        self.set_text(scene["text"])
        audio_file = scene.get("audio_file")
        if is_book and not audio_file:
            audio_root = self.content.config.get("book_audio_roots", {}).get(self.engine.book["id"])
            if audio_root:
                audio_file = f"{audio_root}/{scene['segment_id']}.wav"
        self.play_audio(scene["segment_id"], audio_file)
        if scene["kind"] == "intro":
            ttk.Button(self.actions, text="Entrer dans l'aventure", style="Primary.TButton",
                       command=self.advance).pack(fill="x")
        elif scene["kind"] == "ending":
            if is_book:
                ttk.Label(self.actions, text=self.engine.book.get("ending_notice", "Fin du chapitre 1 · Le chapitre 2 n'est pas encore disponible."),
                          style="Sub.TLabel", wraplength=700).pack(anchor="w", pady=(0, 8))
                ttk.Button(self.actions, text=self.engine.book.get("restart_label", "Rejouer le chapitre"), style="Primary.TButton",
                           command=self.restart).pack(fill="x")
                ttk.Button(self.actions, text="Choisir une autre histoire", command=self.home).pack(fill="x", pady=(6, 0))
            else:
                ttk.Button(self.actions, text="Une nouvelle aventure", style="Primary.TButton",
                           command=self.setup).pack(fill="x")
        else:
            ttk.Label(self.actions, text=scene.get("choice_question", "Que fais-tu ?"),
                      font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
            for i, choice in enumerate(scene["choices"]):
                ttk.Button(self.actions, text=f"Choix {i+1} · {choice['text']}",
                           command=lambda index=i: self.submit_choice(index)).pack(fill="x", pady=(0, 6))
        self.update_debug()

    def choose(self, index):
        if not self.engine or self.engine.finished or self.engine.pending or self.engine.current["kind"] != "decision":
            return
        result = self.engine.choose(index)
        if self.engine.arc.get("inline_consequences"):
            self.engine.advance()
            self.show_scene()
            return
        self.story_layout("Ton chemin se dessine…")
        self.set_text(result["text"])
        self.play_audio(result["segment_id"], result.get("audio_file"))
        ttk.Button(self.actions, text="Poursuivre", style="Primary.TButton", command=self.advance).pack(fill="x")
        self.update_debug()

    def submit_choice(self, index):
        now = time.monotonic()
        if now - self.last_choice_time < .3:
            return
        self.last_choice_time = now
        self.choose(index)

    def keyboard_choice(self, index, key=None):
        if self.root.focus_get() and isinstance(self.root.focus_get(), (ttk.Entry, ttk.Combobox)):
            return
        if key is not None:
            if key in self.pressed_choice_keys:
                return
            self.pressed_choice_keys.add(key)
        self.submit_choice(index)

    def advance(self):
        if not self.engine or self.engine.finished:
            return
        self.engine.advance()
        self.show_scene()

    def toggle_debug(self):
        if self.engine:
            self.update_debug()
        elif self.setup_kind != "tale":
            return
        elif self.debug.get():
            self.debug_setup.pack(anchor="w")
        else:
            self.debug_setup.pack_forget()

    def update_debug(self):
        if not self.debug.get():
            self.debug_panel.pack_forget()
            return
        self.debug_panel.pack(side="bottom", before=self.body_frame, fill="x", pady=(14, 0))
        self.debug_panel.config(state="normal")
        self.debug_panel.delete("1.0", "end")
        self.debug_panel.insert("1.0", json.dumps(self.engine.debug_snapshot(), ensure_ascii=False, indent=2))
        self.debug_panel.config(state="disabled")

    def save_session(self):
        if not self.debug.get() or not self.engine:
            messagebox.showinfo("Journal", "Active le mode debug et commence une aventure pour enregistrer son journal.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Enregistrer le journal",
                                           defaultextension=".json", filetypes=[("Journal JSON", "*.json")])
        if path:
            try:
                self.engine.export_session(path)
            except OSError as exc:
                messagebox.showerror("Journal", str(exc), parent=self.root)

    def open_session(self):
        if not self.debug.get():
            messagebox.showinfo("Journal", "Active le mode debug pour rejouer un journal.", parent=self.root)
            return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Journal JSON", "*.json")])
        if path:
            try:
                log = self.content.read(path)
                if log.get("format") == BookEngine.JOURNAL_FORMAT:
                    self.engine = BookEngine.replay(self.content, path)
                    self.setup_kind = "book"
                    self.active_book_id = self.engine.book["id"]
                else:
                    self.engine = StoryEngine.replay(self.content, path)
                    self.setup_kind = "tale"
                if self.engine.pending:
                    if self.engine.arc.get("inline_consequences"):
                        self.engine.advance()
                        self.show_scene()
                        return
                    result = self.engine.pending
                    self.story_layout("Ton chemin se dessine…")
                    self.set_text(result["text"])
                    self.play_audio(result["segment_id"], result.get("audio_file"))
                    ttk.Button(self.actions, text="Poursuivre", command=self.advance).pack(fill="x")
                    self.update_debug()
                else:
                    self.show_scene()
            except (OSError, ValueError, KeyError, TypeError) as exc:
                messagebox.showerror("Journal incompatible", str(exc), parent=self.root)

    def close(self):
        if self.audio_poll is not None:
            self.root.after_cancel(self.audio_poll)
            self.audio_poll = None
        self.audio.stop()
        self.root.destroy()
