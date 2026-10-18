import copy
import itertools
import json
import random
import tempfile
import unittest
from pathlib import Path

from engine import Content, StoryEngine
from engine.content import segment_id
from engine.probability import probabilities, resolve
from engine.rules import apply_effects, matches
from engine.simulator import complete, simulate
from engine.story_state import StoryState


class FixedRandom:
    def __init__(self, roll):
        self.roll = roll

    def random(self):
        return self.roll


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content()

    def engine(self, seed=42, arc=None):
        return StoryEngine(self.content, "rogue", "city", "book", seed, arc)

    def test_all_125_configurations_across_all_arcs_and_two_routes(self):
        c = self.content
        checked = 0
        for i, triple in enumerate(itertools.product(c.heroes, c.locations, c.items)):
            for arc in c.arcs:
                for choice in (0, 1):
                    with self.subTest(triple=triple, arc=arc, choice=choice):
                        e = StoryEngine(c, *triple, i, arc)
                        complete(e, lambda _: choice)
                        self.assertTrue(e.finished)
                        self.assertEqual(e.state.story_progress, 12)
                        self.assertIn(triple[1], e.state.visited_locations)
                        self.assertIn(triple[2], e.state.inventory)
                        self.assertTrue(c.config["minimum_seconds"] <= e.state.estimated_seconds <= c.config["maximum_seconds"])
                        checked += 1
        self.assertEqual(checked, 125 * len(c.arcs) * 2)

    def test_every_result_keeps_all_twelve_decisions(self):
        for arc in self.content.arcs:
            for category in ("success", "complication", "failure"):
                e = self.engine(arc=arc)
                e.advance()
                for rank in range(1, 13):
                    self.assertEqual(e.current["rank"], rank)
                    distribution = probabilities(e.current["choices"][1], e.state, self.content.config)
                    roll = {"success": 0, "complication": (distribution["success"]+distribution["objective"])/2,
                            "failure": .99999}[category]
                    e.rng = FixedRandom(roll)
                    result = e.choose(1)
                    self.assertEqual(result["outcome"], category)
                    e.advance()
                self.assertTrue(e.finished)
                self.assertEqual(getattr(e.state, category + "_count"), 12)

    def test_seed_reproduces_text_variants_and_results(self):
        a, b = self.engine(), self.engine()
        chooser = lambda e: e.state.story_progress % 2
        complete(a, chooser)
        complete(b, chooser)
        self.assertEqual(a.journal, b.journal)
        self.assertEqual(a.debug_snapshot(), b.debug_snapshot())

    def test_seed_variation_changes_several_story_elements(self):
        stories = set()
        for seed in range(20):
            e = self.engine(seed)
            complete(e, lambda _: 0)
            stories.add((e.state.arc_id, e.encounter["id"], e.revelation["id"],
                         tuple(r["outcome"] for r in e.journal["choices"])))
        self.assertGreater(len(stories), 15)

    def test_initial_parameters_are_more_than_decorations(self):
        for hero in self.content.heroes:
            e = StoryEngine(self.content, hero, "city", "book", 8, "lantern")
            affected = 0
            e.advance()
            while not e.finished:
                affected += any(any(m["label"] == "Formation du héros" for m in probabilities(choice, e.state, self.content.config)["modifiers"])
                                for choice in e.current["choices"])
                e.choose(0)
                e.advance()
            self.assertGreaterEqual(affected, 2)
        for item in self.content.items:
            e = StoryEngine(self.content, "rogue", "city", item, 8, "lantern")
            used = 0
            e.advance()
            while not e.finished:
                if e.current["rank"] in (3, 7, 11):
                    expected_item = {**self.content.items[item], **e.arc.get("item_overrides", {}).get(item, {})}
                    self.assertEqual(e.current["choices"][0]["text"], expected_item[
                        {3:"first_action",7:"second_action",11:"climax_action"}[e.current["rank"]]])
                    dist = probabilities(e.current["choices"][0], e.state, self.content.config)
                    self.assertTrue(any(m["label"] == "Objet choisi et disponible" for m in dist["modifiers"]))
                    used += 1
                e.choose(0)
                e.advance()
            self.assertEqual(used, 3)
        for location in self.content.locations:
            e = StoryEngine(self.content, "rogue", location, "book", 8, "lantern")
            complete(e, lambda _: 0)
            texts = "\n".join(s["text"] for s in e.journal["scenes"])
            self.assertIn(self.content.locations[location]["core"], texts)
            self.assertIn(self.content.locations[location]["decision"], texts)

    def test_probabilities_and_boundaries(self):
        e = self.engine()
        e.advance()
        choice = e.current["choices"][0]
        distribution = probabilities(choice, e.state, self.content.config)
        self.assertAlmostEqual(sum(distribution[k] for k in ("success", "complication", "failure")), 1)
        for roll, expected in ((0, "success"), (distribution["success"], "complication"),
                               (distribution["objective"], "failure"), (.999, "failure")):
            self.assertEqual(resolve(choice, e.state, FixedRandom(roll), self.content.config)[0], expected)
        huge = copy.deepcopy(choice)
        huge["modifiers"] = [{"label":"fort", "when":{}, "delta":1}]
        self.assertEqual(probabilities(huge, e.state, self.content.config)["objective"], .9)
        huge["modifiers"][0]["delta"] = -1
        self.assertEqual(probabilities(huge, e.state, self.content.config)["objective"], .35)

    def test_previous_decisions_change_later_odds_and_text(self):
        e = self.engine(arc="lantern")
        e.advance()
        before = probabilities(e.current["choices"][0], e.state, self.content.config)["objective"]
        e.state.flags.add("unstable")
        after = probabilities(e.current["choices"][0], e.state, self.content.config)["objective"]
        self.assertLess(after, before)
        e.state.flags.remove("unstable")
        e.state.allies.add("companion")
        complete(e, lambda _: 1)
        rank10 = next(s for s in e.journal["scenes"] if s["id"] == "lantern_10")
        self.assertIn("memory_ally", rank10["variants"])

    def test_branch_then_rejoin(self):
        paths = []
        for branch in (0, 1):
            e = self.engine(arc="lantern")
            e.advance()
            while not e.finished:
                e.choose(branch if e.current["rank"] == 4 else 1)
                e.advance()
            paths.append([s["id"] for s in e.journal["scenes"]])
        self.assertEqual(paths[0][5], "lantern_5")
        self.assertEqual(paths[1][5], "lantern_5b")
        self.assertEqual(paths[0][6], paths[1][6])

    def test_new_adventure_erases_previous_world(self):
        a = self.engine()
        a.state.flags.add("custom")
        a.state.allies.add("friend")
        a.state.inventory.add("extra")
        a.state.events.append("old")
        b = self.engine()
        self.assertNotIn("custom", b.state.flags)
        self.assertFalse(b.state.allies)
        self.assertEqual(b.state.inventory, {"book"})
        self.assertFalse(b.state.events)
        self.assertIsNot(a.state.previous_outcomes, b.state.previous_outcomes)

    def test_invalid_input_and_double_click(self):
        e = self.engine()
        with self.assertRaises(ValueError):
            e.choose(0)
        e.advance()
        for invalid in (-1, 2, "0", True):
            with self.assertRaises(ValueError):
                e.choose(invalid)
        e.choose(0)
        with self.assertRaises(ValueError):
            e.choose(0)
        with self.assertRaises(ValueError):
            StoryEngine(self.content, "absent", "city", "book")

    def test_debug_journal_complete_and_partial_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            for mode in ("intro", "ready", "pending", "middle", "finished"):
                e = self.engine(arc="rain")
                if mode != "intro":
                    e.advance()
                if mode in ("pending", "middle"):
                    e.choose(0)
                    if mode == "middle":
                        e.advance()
                if mode == "finished":
                    complete(e, lambda state: state.state.story_progress % 2)
                e.export_session(path)
                rebuilt = StoryEngine.replay(self.content, path)
                self.assertEqual(e.journal, rebuilt.journal)
                self.assertEqual(e.debug_snapshot(), rebuilt.debug_snapshot())
                self.assertEqual(bool(e.pending), bool(rebuilt.pending))
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["seed"], 42)
                self.assertEqual(payload["configuration"]["item"], "book")
            payload["choices"][0]["roll"] = .1234567
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                StoryEngine.replay(self.content, path)

    def test_template_cannot_execute_or_access_attributes(self):
        for text in ("{hero.__class__}", "{missing}", "{hero!r}", "{hero:>10}"):
            with self.assertRaises(ValueError):
                self.content.render(text, {"hero":"test"})

    def test_rules_are_declarative_and_update_sets(self):
        state = StoryState("rogue", "city", "key", 1)
        self.assertTrue(matches({"all":[{"hero":"rogue"},{"not":{"flag":"closed"}}]}, state))
        apply_effects({"set_flags":["closed"],"add_inventory":["key"],"add_allies":["friend"]}, state)
        self.assertTrue(matches({"any":[{"flag":"closed"},{"hero":"mage"}]}, state))
        apply_effects({"unset_flags":["closed"],"remove_inventory":["key"],"remove_allies":["friend"]}, state)
        self.assertFalse(state.flags or state.inventory or state.allies)
        with self.assertRaises(ValueError):
            matches({"exec":"anything"}, state)

    def test_simulator_statistics_and_repeatability(self):
        first = simulate(self.content, 120, 18)
        self.assertEqual(first, simulate(self.content, 120, 18))
        self.assertEqual(first["decisions"], {12:120})
        self.assertEqual(sum(first["arcs"].values()), 120)
        self.assertEqual(sum(first["outcomes_total"].values()), 1440)
        self.assertEqual(first["timing"]["outside_target"], 0)
        self.assertEqual(first["scenes"]["lantern_intro"], first["arcs"]["lantern"])

    def test_audio_hash_identifies_the_actual_text(self):
        self.assertNotEqual(segment_id("scene", "narration", "Bonjour"), segment_id("scene", "narration", "Bonsoir"))


if __name__ == "__main__":
    unittest.main()
