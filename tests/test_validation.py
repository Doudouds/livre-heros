import copy
import unittest

from engine import Content
from engine.validator import validate


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content()

    def mutated(self):
        return copy.deepcopy(self.content)

    def test_full_content_all_paths_and_compatibilities(self):
        report = validate(self.content)
        self.assertTrue(report.valid, report.errors[:10])
        self.assertEqual(report.configuration_count, 125)
        self.assertEqual(report.arc_configuration_count, 125 * len(self.content.arcs))
        self.assertEqual(report.content_metrics["arcs"], len(self.content.arcs))
        self.assertGreaterEqual(report.content_metrics["prepared_narration_minutes"], 120)
        for bounds in report.duration_bounds.values():
            self.assertGreaterEqual(bounds["minimum_minutes"], 18)
            self.assertLessEqual(bounds["maximum_minutes"], 22)

    def test_missing_destination(self):
        c = self.mutated()
        c.scenes["lantern_1"]["choices"][0]["outcomes"]["failure"]["next"] = "missing"
        self.assertTrue(any("inexistante" in error for error in validate(c, False).errors))

    def test_unreachable_scene(self):
        c = self.mutated()
        c.scenes["orphan"] = {**c.scenes["lantern_1"], "id":"orphan"}
        self.assertTrue(any("inaccessible" in error for error in validate(c, False).errors))

    def test_cycle(self):
        c = self.mutated()
        c.scenes["lantern_1"]["choices"][0]["outcomes"]["failure"]["next"] = "lantern_1"
        self.assertTrue(any("boucle" in error for error in validate(c, False).errors))

    def test_missing_conclusion(self):
        c = self.mutated()
        c.arcs["lantern"]["endings"][-1]["when"] = {"flag":"never"}
        self.assertTrue(any("conclusion" in error for error in validate(c, False).errors))

    def test_invalid_probability_choice_count_and_unknown_condition(self):
        for mutation in ("probability", "choices", "rule"):
            c = self.mutated()
            if mutation == "probability":
                c.scenes["lantern_1"]["choices"][0]["base_success"] = 2.0
            elif mutation == "choices":
                c.scenes["lantern_1"]["choices"].pop()
            else:
                c.scenes["lantern_1"]["conditions"] = {"python":"True"}
            self.assertFalse(validate(c, False).valid)

    def test_choice_with_no_destination_or_non_object(self):
        for mutation in ("empty", "missing", "not_object"):
            c = self.mutated()
            outcome = c.scenes["lantern_1"]["choices"][0]["outcomes"]["success"]
            if mutation == "empty":
                outcome["next"] = ""
            elif mutation == "missing":
                del outcome["next"]
            else:
                c.scenes["lantern_1"]["choices"][0]["outcomes"]["success"] = None
            self.assertFalse(validate(c, False).valid)

    def test_incompatible_arc_and_scene(self):
        c = self.mutated()
        c.arcs["lantern"]["conditions"] = {"hero":"knight"}
        report = validate(c, False)
        self.assertTrue(any("arc incompatible" in error for error in report.errors))
        c = self.mutated()
        c.scenes["lantern_1"]["conditions"] = {"item":"key"}
        self.assertTrue(any("Scène incompatible" in error for error in validate(c, False).errors))

    def test_duration_too_short_and_too_long(self):
        # Une scène suffit à modifier tous les chemins d'un arc ; l'audit mesure
        # les mots réellement assemblés, sans faire confiance à une durée saisie.
        c = self.mutated()
        c.scenes["lantern_intro"]["text"] = "Longue histoire. " * 500
        self.assertTrue(any("hors durée" in error for error in validate(c).errors))
        c = self.mutated()
        c.config["words_per_minute"] = 500
        self.assertTrue(any("hors durée" in error for error in validate(c).errors))

    def test_undeclared_template(self):
        c = self.mutated()
        c.scenes["lantern_intro"]["text"] += " {unknown}"
        self.assertTrue(any("Substitution" in error for error in validate(c, False).errors))


if __name__ == "__main__":
    unittest.main()
