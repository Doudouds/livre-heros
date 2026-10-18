import copy
import itertools
import tempfile
import unittest
from pathlib import Path

from engine import Content, StoryEngine
from engine.probability import probabilities
from engine.simulator import complete
from tools.export_tts_manifest import all_segments, session_segments


class FixedRandom:
    def __init__(self, roll=0):
        self.roll = roll

    def random(self):
        return self.roll


class CagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content()

    def engine(self, seed=42):
        return StoryEngine(self.content, "explorer", "forest", "compass", seed, "cages")

    def successful_until(self, rank):
        e = self.engine()
        e.advance()
        e.rng = FixedRandom()
        while e.current["rank"] < rank:
            e.choose(0)
            e.advance()
        return e

    def test_new_games_have_three_distinct_middle_plots(self):
        paths = {}
        for seed in range(30):
            e = self.engine(seed)
            e.rng = FixedRandom()
            complete(e, lambda _: 0)
            paths[e.revelation["id"]] = tuple(s["id"] for s in e.journal["scenes"][6:9])
        self.assertEqual(set(paths), {"quiet", "visitor", "departure"})
        self.assertEqual(len(set(paths.values())), 3)

    def test_all_configurations_and_extreme_outcomes_keep_a_complete_story(self):
        for triple in itertools.product(self.content.heroes, self.content.locations, self.content.items):
            for roll, route in ((0, 0), (.99999, 1)):
                e = StoryEngine(self.content, *triple, 0, "cages")
                e.rng = FixedRandom(roll)
                complete(e, lambda _: route)
                with self.subTest(triple=triple, roll=roll):
                    self.assertTrue(e.finished)
                    self.assertEqual(e.state.story_progress, 12)
                    self.assertEqual(len(e.journal["scenes"]), 14)
                    self.assertTrue(18 <= e.state.estimated_seconds / 60 <= 22)
                    self.assertFalse(any("{" in s["spoken_text"] for s in e.journal["scenes"]))
                    self.assertEqual(e.state.conclusion, "full" if roll == 0 else "pending")

    def test_transformation_is_witnessed_before_the_mouse_explains_the_spell(self):
        e = self.successful_until(5)
        self.assertIn("transformation_seen", e.state.flags)
        self.assertIn("Le tablier de Lison tombe", e.current["text"])
        self.assertIn("À la place de ta sœur", e.current["text"])
        e.choose(0)
        e.advance()
        self.assertIn("pour l'ouvrir défait le sort", e.current["text"])

    def test_choices_change_rescues_and_the_following_choices(self):
        for first, second, expected in ((0, 0, "full"), (0, 1, "lison"), (1, 1, "others")):
            e = self.successful_until(10)
            e.choose(first)
            result = e.pending["text"]
            e.advance()
            self.assertTrue(e.current["text"].startswith(result + "\n\n"))
            self.assertIn("Lison" if first == 0 else "enfants", e.current["choices"][second]["text"])
            e.choose(second)
            e.advance()
            e.choose(0)
            e.advance()
            self.assertEqual(e.state.conclusion, expected)

    def test_failed_unlock_keeps_the_key_and_lison_remains_a_bird(self):
        e = self.successful_until(10)
        e.rng = FixedRandom(.99999)
        e.choose(0)
        e.advance()
        self.assertIn("has_key", e.state.flags)
        self.assertIn("lison_bird", e.state.flags)
        self.assertIn("Achever d'ouvrir", e.current["choices"][0]["text"])
        e.rng = FixedRandom()
        e.choose(1)
        e.advance()
        e.choose(1)
        e.advance()
        self.assertEqual(e.state.conclusion, "bird")
        self.assertIn("forme d'un oiseau", e.current["text"])

    def test_mouse_promise_requires_actually_collecting_the_family(self):
        for selected in (0, 1):
            e = self.successful_until(12)
            self.assertIn("mouse_promised", e.state.flags)
            e.choose(selected)
            e.advance()
            self.assertEqual("mouse_home" in e.state.flags, selected == 0)
            self.assertIn("tenu parole" if selected == 0 else "attendent encore", e.current["text"])

    def test_remembered_key_and_alert_change_later_odds(self):
        e = self.successful_until(8)
        choice = e.current["choices"][1]
        e.state.flags.discard("key_seen")
        before = probabilities(choice, e.state, self.content.config)["objective"]
        e.state.flags.add("key_seen")
        informed = probabilities(choice, e.state, self.content.config)["objective"]
        e.state.flags.add("alert")
        alerted = probabilities(choice, e.state, self.content.config)["objective"]
        self.assertGreater(informed, before)
        self.assertLess(alerted, informed)

    def test_replay_and_audio_use_the_actual_joined_passages(self):
        c = copy.deepcopy(self.content)
        c.arcs = {"cages": c.arcs["cages"]}
        c.scenes = {k: v for k, v in c.scenes.items() if v["arc"] == "cages"}
        c.heroes = {"explorer": c.heroes["explorer"]}
        c.locations = {"forest": c.locations["forest"]}
        c.items = {"compass": c.items["compass"]}
        c.catalog["encounters"] = c.catalog["encounters"][:1]
        prepared_ids = {record["segment_id"] for record in all_segments(c)}
        for seed in (0, 1, 42):
            e = self.engine(seed)
            complete(e, lambda e: e.state.story_progress % 2)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "session.json"
                e.export_session(path)
                replay = StoryEngine.replay(self.content, path)
                self.assertEqual(e.debug_snapshot(), replay.debug_snapshot())
                records = list(session_segments(self.content, path))
                self.assertEqual(len(records), 14)
                self.assertEqual([r["segment_id"] for r in records], [s["segment_id"] for s in e.journal["scenes"]])
                self.assertTrue(all(r["segment_id"] in prepared_ids for r in records))
                seconds = sum(s["estimated_duration"] for s in e.journal["scenes"]) + 12 * self.content.config["choice_seconds"]
                self.assertAlmostEqual(e.state.estimated_seconds, seconds)

    def test_explicit_plot_replays_without_changing_older_journals(self):
        for plot in ("quiet", "visitor", "departure"):
            e = StoryEngine(self.content, "rogue", "city", "book", 42, "cages", revelation_id=plot)
            complete(e, lambda _: 0)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "session.json"
                e.export_session(path)
                self.assertEqual(StoryEngine.replay(self.content, path).journal, e.journal)

    def test_pilot_ui_advances_directly_and_restarts_with_the_same_tale(self):
        import tkinter as tk
        from ui.pc_ui import PcUI
        root = tk.Tk()
        root.withdraw()
        try:
            app = PcUI(root, self.content, arc="cages")
            self.assertFalse(app.debug.get())
            for variable, value in ((app.hero, "explorer"), (app.location, "forest"), (app.item, "compass")):
                variable.set(value)
            app.start()
            first_seed = app.engine.state.seed
            first_plot = app.engine.revelation["id"]
            app.advance()
            app.keyboard_choice(0, "1")
            self.assertEqual(len(app.engine.journal["choices"]), 1)
            app.keyboard_choice(0, "1")
            app.submit_choice(1)
            self.assertEqual(len(app.engine.journal["choices"]), 1)
            for _ in range(11):
                app.choose(0)
                self.assertIsNone(app.engine.pending)
                self.assertNotIn("Poursuivre", [str(w["text"]) for w in app.actions.winfo_children()])
            self.assertTrue(app.engine.finished)
            app.setup()
            self.assertIsNone(app.engine)
            for variable, value in ((app.hero, "explorer"), (app.location, "forest"), (app.item, "compass")):
                variable.set(value)
            app.start()
            self.assertEqual(app.engine.arc["id"], "cages")
            self.assertNotEqual(app.engine.state.seed, first_seed)
            self.assertNotEqual(app.engine.revelation["id"], first_plot)
            second_plot = app.engine.revelation["id"]
            app.setup()
            for variable, value in ((app.hero, "explorer"), (app.location, "forest"), (app.item, "compass")):
                variable.set(value)
            app.start()
            self.assertEqual({first_plot, second_plot, app.engine.revelation["id"]}, {"quiet", "visitor", "departure"})
        finally:
            if "app" in locals():
                app.audio.stop()
            root.destroy()
