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

    def __init__(self, root, content, debug=False, seed=None, arc=None):
        self.root, self.content = root, content
        self.engine = None
        self.initial_seed, self.initial_arc = seed, arc
        self.active_tale_arc = arc
        self.setup_kind = "library"
        self.illustration = None
        self.pilot_plots_seen = set()
        self.pressed_choice_keys = set()
        self.last_choice_time = 0
        self.debug = tk.BooleanVar(value=debug)
        self.audio = LocalAudioPlayer(content.root, content.config["audio_root"])
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
        self.setup() if arc is not None else self.home()

    def clear(self):
        for widget in self.page.winfo_children():
            widget.destroy()
        self.illustration = None
        self.original_illustration = None
        self.illustration_factor = None
        self.reading_scene = None

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
        ttk.Label(self.page, text="Deux histoires. Deux univers. À toi d'ouvrir la première page.",
                  style="Sub.TLabel", wraplength=720).pack(anchor="w", pady=(10, 30))
        for title, subtitle, description, command in (
            ("Le conte", "La Maison aux Sept Cages",
             "Retrouve Lison et délivre les enfants changés en oiseaux.\n"
             "Choisis ton héros, ton lieu et ton objet, puis trace ton chemin.", self.select_tale),
            ("Le livre", "La petite passeuse d'étoile",
             "Accompagne Alex dans une ville où chaque pas est imposé.\n"
             "Premier chapitre complet, illustré en noir et blanc. Deux choix à chaque étape.", self.book_setup),
        ):
            frame = ttk.Frame(self.page, padding=(22, 18), relief="solid", borderwidth=1)
            frame.pack(fill="x", pady=(0, 18))
            ttk.Label(frame, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ttk.Label(frame, text=subtitle, font=("Georgia", 20), wraplength=700).pack(anchor="w", pady=(5, 8))
            ttk.Label(frame, text=description, style="Sub.TLabel", wraplength=700).pack(anchor="w")
            ttk.Button(frame, text="Ouvrir " + ("le conte" if title == "Le conte" else "le livre"),
                       style="Primary.TButton", command=command).pack(anchor="w", pady=(14, 0))

    def select_tale(self):
        self.active_tale_arc = self.initial_arc or "cages"
        self.setup()

    def restart(self):
        if self.setup_kind == "book":
            self.book_setup()
        elif self.setup_kind == "tale":
            self.setup()
        else:
            self.home()

    def book_setup(self):
        self.reset_reading()
        self.setup_kind = "book"
        book = self.content.books["passeuse_ch1"]
        self.story_layout(book["title"], f"{book['author']} · Chapitre 1", book["scenes"][0])
        self.set_text("Alex connaissait chaque marche entre sa chambre et l'usine.\n"
                      "Un soir, ce chemin ne lui suffit plus.\n\n"
                      f"{book['decision_count']} décisions · Deux possibilités à chaque fois.\n"
                      "Les choix font varier ses gestes, ses difficultés et les passages suivants.\n\n"
                      "Le premier chapitre est disponible. La suite du roman viendra après cet essai.")
        ttk.Button(self.actions, text="Commencer le chapitre", style="Primary.TButton", command=self.start_book).pack(fill="x")
        ttk.Button(self.actions, text="Choisir une autre histoire", command=self.home).pack(fill="x", pady=(8, 0))

    def start_book(self):
        self.engine = BookEngine(self.content)
        self.show_scene()

    def resize_reading_image(self, event):
        if event.widget != self.body or self.original_illustration is None:
            return
        available = max(200, event.width - 64)
        factor = max(1, ceil(self.original_illustration.width() / available))
        if factor != self.illustration_factor:
            self.illustration = self.original_illustration.subsample(factor)
            self.illustration_factor = factor
            self.body.image_configure("chapter-illustration", image=self.illustration)


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
            try:
                asset = (self.content.root / self.reading_scene["image"]).resolve()
                if not asset.is_relative_to(self.content.root.resolve()):
                    raise ValueError("Illustration hors projet")
                self.original_illustration = tk.PhotoImage(file=str(asset), master=self.root)
                available = max(200, self.root.winfo_width() - 148)
                self.illustration_factor = max(1, ceil(self.original_illustration.width() / available))
                self.illustration = self.original_illustration.subsample(self.illustration_factor)
                self.body.image_create("end", image=self.illustration, name="chapter-illustration")
                self.body.insert("end", "\n\n")
                self.body.tag_configure("illustration", justify="center")
                self.body.tag_add("illustration", "1.0", "2.0")
            except (tk.TclError, OSError, ValueError):
                self.body.insert("end", self.reading_scene["image_alt"] + "\n\n")
        self.body.insert("end", text)
        self.body.yview_moveto(0)
        self.body.config(state="disabled")

    def show_scene(self):
        scene = self.engine.current
        is_book = isinstance(self.engine, BookEngine)
        subtitle = (f"La petite passeuse d'étoile · Chapitre 1 · Passage {scene['rank']}/{len(self.engine.scenes)}"
                    if is_book else "Les Portes de l'Imaginaire")
        self.story_layout(scene["title"], subtitle, scene)
        self.set_text(scene["text"])
        self.audio.play(scene["segment_id"], scene.get("audio_file"))
        if scene["kind"] == "intro":
            ttk.Button(self.actions, text="Entrer dans l'aventure", style="Primary.TButton",
                       command=self.advance).pack(fill="x")
        elif scene["kind"] == "ending":
            if is_book:
                ttk.Label(self.actions, text="Fin du chapitre 1 · Le chapitre 2 n'est pas encore disponible.",
                          style="Sub.TLabel", wraplength=700).pack(anchor="w", pady=(0, 8))
                ttk.Button(self.actions, text="Rejouer le chapitre", style="Primary.TButton",
                           command=self.book_setup).pack(fill="x")
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
        self.audio.play(result["segment_id"], result.get("audio_file"))
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
                    self.audio.play(result["segment_id"], result.get("audio_file"))
                    ttk.Button(self.actions, text="Poursuivre", command=self.advance).pack(fill="x")
                    self.update_debug()
                else:
                    self.show_scene()
            except (OSError, ValueError, KeyError, TypeError) as exc:
                messagebox.showerror("Journal incompatible", str(exc), parent=self.root)

    def close(self):
        self.audio.stop()
        self.root.destroy()
