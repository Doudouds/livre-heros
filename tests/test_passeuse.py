import copy
import json
import random
import re
import hashlib
import tempfile
import unittest
from pathlib import Path

from engine import Content
from engine.book_engine import BookEngine, validate_book


class BookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content()

    def test_every_choice_preserves_order_and_has_its_own_consequence(self):
        book = self.content.books["passeuse_ch1"]
        validate_book(book, self.content.root)
        for index in (0, 1):
            engine = BookEngine(self.content)
            while not engine.finished:
                current = engine.current
                self.assertEqual(len(current["choices"]), 2)
                self.assertNotEqual(current["choices"][0]["consequence"], current["choices"][1]["consequence"])
                result = engine.choose(index)
                engine.advance()
                self.assertTrue(engine.current["text"].startswith(result["text"] + "\n\n"))
            self.assertEqual(engine.state.story_progress, 27)
            self.assertEqual([s["id"] for s in engine.journal["scenes"]], [s["id"] for s in book["scenes"]])
            self.assertIn("racine", engine.current["text"])

    def test_varied_paths_terminate_with_third_person_text(self):
        for seed in range(200):
            rng = random.Random(seed)
            engine = BookEngine(self.content)
            while not engine.finished:
                engine.choose(rng.randrange(2))
                engine.advance()
            self.assertEqual(len(engine.journal["scenes"]), 28)
            self.assertEqual(engine.state.conclusion, "chapter_complete")
            for scene in engine.journal["scenes"]:
                self.assertFalse(re.search(r"\b(tu|toi|tes|ton|ta|vous|votre|vos)\b", scene["text"], re.I))
                self.assertNotIn("{", scene["text"])

    def reach(self, rank, decisions=None):
        engine = BookEngine(self.content)
        decisions = decisions or {}
        while engine.current["rank"] < rank:
            engine.choose(decisions.get(engine.current["rank"], 0))
            engine.advance()
        return engine

    def test_knee_injury_changes_later_climbing_descent_and_exit(self):
        careful = self.reach(23)
        injured = self.reach(23, {16: 1})
        self.assertNotIn("genou heurté", careful.current["text"])
        self.assertIn("genou heurté", injured.current["text"])
        while injured.current["rank"] < 25:
            injured.choose(0)
            injured.advance()
        result = injured.choose(1)
        self.assertIn("réveilla brutalement la douleur de son genou", result["text"])
        self.assertIn("genou_aggrave", injured.state.flags)
        injured.advance()
        self.assertIn("La douleur du genou obligea Alex à s'arrêter", injured.current["text"])
        while not injured.finished:
            injured.choose(0)
            injured.advance()
        self.assertIn("genou heurté dans l'escalier", injured.current["text"])

    def test_observed_patrol_changes_the_same_later_choice(self):
        uninformed = self.reach(22)
        informed = self.reach(22, {3: 1})
        first = uninformed.choose(1)["text"]
        second = informed.choose(1)["text"]
        self.assertIn("contraignit à se retirer", first)
        self.assertIn("sans devoir se cacher", second)
        self.assertNotEqual(first, second)
        self.assertIn("traversee_calculee", informed.state.flags)
        uninformed.advance()
        informed.advance()
        self.assertEqual(uninformed.current["id"], informed.current["id"])

    def test_hasty_work_and_crane_effort_have_visible_later_costs(self):
        work = self.reach(6, {5: 1})
        self.assertIn("Une remontrance lui fut adressée", work.current["text"])
        work.choose(0)
        work.advance()
        self.assertIn("La remontrance revenait", work.current["text"])
        tired = self.reach(27, {23: 1})
        self.assertIn("bras qui avaient tremblé sur la grue", tired.current["text"])
        self.assertIn("depuis la grue", tired.choose(0)["text"])

    def test_rebuilt_book_records_the_pdf_in_the_project_and_only_chapter_one(self):
        book = self.content.books["passeuse_ch1"]
        source = self.content.root / book["source"]["file"]
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), book["source"]["sha256"])
        self.assertEqual(book["chapter"], 1)
        self.assertEqual(book["narrative_person"], 3)
        self.assertEqual({p for s in book["scenes"] for p in s["source_pages"]}, set(range(5, 20)))
        self.assertEqual(book["choice_question"], "Que doit choisir Alex ?")
        self.assertNotIn("Que fais-tu", BookEngine(self.content).current["spoken_text"])

    def test_journals_replay_before_after_and_between_choices(self):
        engine = BookEngine(self.content)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "book.json"
            for step in range(55):
                engine.export_session(path)
                replay = BookEngine.replay(self.content, path)
                self.assertEqual(replay.debug_snapshot(), engine.debug_snapshot())
                self.assertEqual(replay.journal, engine.journal)
                if engine.finished:
                    break
                if engine.pending:
                    engine.advance()
                else:
                    engine.choose(step % 2)
            self.assertTrue(engine.finished)

    def test_changed_content_and_falsified_journal_are_rejected(self):
        engine = BookEngine(self.content)
        engine.choose(1)
        engine.advance()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "book.json"
            engine.export_session(path)
            changed = copy.deepcopy(self.content)
            changed.books["passeuse_ch1"]["scenes"][0]["text"] += " Autre texte."
            with self.assertRaises(ValueError):
                BookEngine.replay(changed, path)
            log = json.loads(path.read_text(encoding="utf-8"))
            log["choices"][0]["choice_index"] = 0
            path.write_text(json.dumps(log), encoding="utf-8")
            with self.assertRaises(ValueError):
                BookEngine.replay(self.content, path)

    def test_rejects_invalid_choices_and_duplicate_submissions(self):
        engine = BookEngine(self.content)
        for bad in (True, -1, 2, "1"):
            with self.assertRaises(ValueError):
                engine.choose(bad)
        engine.choose(0)
        with self.assertRaises(ValueError):
            engine.choose(1)
        with self.assertRaises(ValueError):
            bad_book = copy.deepcopy(engine.book)
            bad_book["scenes"][0]["choices"][0]["next"] = bad_book["start"]
            validate_book(bad_book)

    def test_home_book_tale_and_image_display_in_the_same_ui(self):
        import tkinter as tk
        from ui.pc_ui import PcUI
        root = tk.Tk()
        root.withdraw()
        app = None
        try:
            app = PcUI(root, self.content)
            self.assertEqual(app.setup_kind, "library")
            root.geometry("800x620")
            root.deiconify()
            root.update()
            app.debug.set(True)
            app.toggle_debug()
            open_book = next(w for frame in app.page.winfo_children()
                             for w in frame.winfo_children()
                             if w.winfo_class() == "TButton" and w["text"] == "Ouvrir le livre")
            open_book.invoke()
            self.assertEqual(app.setup_kind, "book")
            self.assertEqual(app.engine.current["rank"], 1)
            root.update()
            labels = [str(w["text"]) for w in app.actions.winfo_children() if w.winfo_class() == "TLabel"]
            self.assertIn("Que doit choisir Alex ?", labels)
            buttons = [w for w in app.actions.winfo_children() if w.winfo_class() == "TButton"]
            self.assertEqual(len(buttons), 2)
            self.assertTrue(all("Commencer le chapitre" not in str(w["text"]) for w in buttons))
            self.assertTrue(all(w.winfo_ismapped() and
                                w.winfo_rooty() + w.winfo_height() <= app.page.winfo_rooty() + app.page.winfo_height()
                                for w in buttons))
            self.assertIsNotNone(app.illustration)
            self.assertGreaterEqual(app.illustration.width(), 360)
            self.assertLessEqual(app.illustration.width(), 600)
            self.assertLessEqual(app.illustration.width(), app.body.winfo_width() - 48)
            self.assertEqual(app.body.dump("1.0", "1.1", window=True)[0],
                             ("window", str(app.illustration_row), "1.0"))
            self.assertTrue(all(b.winfo_rootx() >= app.image_label.winfo_rootx() + app.image_label.winfo_width()
                                for b in app.audio_buttons.values()))
            root.geometry("1100x800")
            root.update()
            self.assertGreaterEqual(app.illustration.width(), 480)
            self.assertLessEqual(app.illustration.width(), 600)
            app.body.yview_moveto(1)
            root.update()
            self.assertGreater(app.body.yview()[0], 0)
            first_image = str(app.illustration)
            app.keyboard_choice(0, "1")
            app.keyboard_choice(0, "1")
            # Le troisième clic est le même geste doublé dans le délai anti-rebond.
            # Le chargement de l'illustration peut durer plus de 300 ms sur ce PC.
            from unittest.mock import patch
            with patch("ui.pc_ui.time.monotonic", return_value=app.last_choice_time + .1):
                app.submit_choice(1)
            self.assertEqual(app.engine.state.story_progress, 1)
            self.assertNotEqual(first_image, str(app.illustration))
            for _ in range(26):
                self.assertEqual(len([w for w in app.actions.winfo_children() if w.winfo_class() == "TButton"]), 2)
                app.choose(1)
            self.assertTrue(app.engine.finished)
            self.assertIsNotNone(app.illustration)
            app.restart()
            self.assertEqual(app.setup_kind, "book")
            self.assertEqual(app.engine.current["rank"], 1)
            self.assertEqual(app.engine.state.story_progress, 0)
            app.home()
            app.select_tale()
            app.hero.set("explorer")
            app.location.set("forest")
            app.item.set("compass")
            app.start()
            self.assertEqual(app.engine.arc["id"], "cages")
            self.assertIsNone(app.illustration)
            app.home()
            self.assertIsNone(app.engine)
        finally:
            if app:
                app.audio.stop()
            root.destroy()
