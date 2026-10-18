import copy
import json
import random
import secrets
from dataclasses import asdict
from pathlib import Path

from .content import Content, choice_prompt, segment_id, spoken_scene
from .probability import probabilities, resolve
from .rules import apply_effects, matches
from .story_state import StoryState


class StoryEngine:
    JOURNAL_VERSION = 2

    def __init__(self, content, hero, location, item, seed=None, arc_id=None, revelation_id=None):
        self.content = content
        for selected, catalog in ((hero, content.heroes), (location, content.locations), (item, content.items)):
            if selected not in catalog:
                raise ValueError(f"Configuration inconnue : {selected}")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            raise ValueError("La graine doit être un entier.")
        seed = secrets.randbits(64) if seed is None else seed
        self.rng = random.Random(seed)
        self.state = StoryState(hero, location, item, seed)
        eligible = [a for a in content.arcs.values() if matches(a.get("conditions", {}), self.state)]
        if arc_id is None:
            if not eligible:
                raise ValueError("Aucun arc compatible avec cette configuration.")
            self.arc = self.rng.choice(eligible)
        else:
            self.arc = next((a for a in eligible if a["id"] == arc_id), None)
            if self.arc is None:
                raise ValueError(f"Arc absent ou incompatible : {arc_id}")
        self.forced_arc = arc_id
        self.state.arc_id = self.arc["id"]
        self.encounter = self.rng.choice(content.catalog["encounters"])
        if revelation_id is None:
            self.revelation = self.rng.choice(self.arc["revelations"])
        else:
            self.revelation = next((r for r in self.arc["revelations"] if r["id"] == revelation_id), None)
            if self.revelation is None:
                raise ValueError(f"Trame inconnue pour ce conte : {revelation_id}")
        self.context = content.context(self.state, self.encounter, self.revelation)
        self.state.flags.add("revelation_" + self.revelation["id"])
        self.state.inventory.add(item)
        self.state.met_characters.add(self.encounter["id"])
        self.journal = {"version": self.JOURNAL_VERSION, "seed": seed,
                        "configuration": {"hero": hero, "location": location, "item": item},
                        "forced_arc": arc_id, "arc": self.arc["id"],
                        "encounter": self.encounter["id"], "revelation": self.revelation["id"],
                        "scenes": [], "choices": [], "conclusion": None}
        if revelation_id is not None:
            self.journal["forced_revelation"] = revelation_id
        self.current = None
        self.pending = None
        self._enter(self.arc["start"])

    def _ending(self):
        for candidate in self.arc["endings"]:
            if matches(candidate.get("when", {}), self.state):
                return candidate["scene"]
        raise ValueError(f"L'arc {self.arc['id']} n'a pas de conclusion de repli.")

    def _enter(self, scene_id, lead_in=None):
        if scene_id == "$ending":
            scene_id = self._ending()
        if len(self.journal["scenes"]) > self.arc["decision_count"] + 2:
            raise ValueError("Le graphe dépasse le nombre prévu de scènes.")
        raw = self.content.scenes[scene_id]
        if raw["arc"] != self.arc["id"]:
            raise ValueError("Transition hors de l'arc.")
        if not matches(raw.get("conditions", {}), self.state):
            raise ValueError(f"Scène incompatible : {scene_id}")
        self.state.current_scene = scene_id
        self.state.current_act = raw["act"]
        apply_effects(raw.get("effects", {}), self.state)
        scene = copy.deepcopy(raw)
        selected = []
        scene_context = dict(self.context)
        for variant in raw.get("variants", []):
            if matches(variant.get("when", {}), self.state):
                selected.append(variant["id"])
                scene_context.update({key: self.content.render(value, self.context)
                                      for key, value in variant.get("values", {}).items()})
                if "text" in variant:
                    scene["text"] = variant["text"]
                if "append" in variant:
                    scene["text"] += "\n\n" + variant["append"]
                if "choices" in variant:
                    scene["choices"] = copy.deepcopy(variant["choices"])
                apply_effects(variant.get("effects", {}), self.state)
        scene["text"] = self.content.render(scene["text"], scene_context)
        if lead_in:
            scene["text"] = lead_in + "\n\n" + scene["text"]
        self.scene_context = scene_context
        for choice in scene.get("choices", []):
            choice["text"] = self.content.render(choice["text"], scene_context)
        scene["choice_prompt"] = choice_prompt(scene["choices"]) if scene.get("choices") else None
        scene["spoken_text"] = spoken_scene(scene["text"], scene.get("choices", []))
        scene["segment_id"] = segment_id(scene_id, "narration", scene["spoken_text"])
        # Les choix sont inclus dans ce WAV. Aucun second fichier à lancer.
        scene["choice_segment_id"] = None
        scene["estimated_duration"] = self.content.seconds(scene["spoken_text"])
        self.state.estimated_seconds += scene["estimated_duration"]
        scene["selected_variants"] = selected
        self.current = scene
        self.journal["scenes"].append({"id": scene_id, "variants": selected, "text": scene["text"],
                                       "spoken_text": scene["spoken_text"],
                                       "segment_id": scene["segment_id"],
                                       "choice_prompt": scene["choice_prompt"],
                                       "choice_segment_id": scene["choice_segment_id"],
                                       "estimated_duration": scene["estimated_duration"]})
        if scene["kind"] == "ending":
            self.state.conclusion = scene["ending"]
            self.journal["conclusion"] = scene["ending"]

    @property
    def finished(self):
        return self.state.conclusion is not None

    def choose(self, index):
        if self.pending is not None:
            raise ValueError("Lis la conséquence avant de poursuivre.")
        if self.current["kind"] != "decision":
            raise ValueError("Cette scène ne propose pas de choix.")
        if type(index) is not int or index not in (0, 1):
            raise ValueError("Le choix doit être 0 ou 1.")
        choice = self.current["choices"][index]
        outcome, roll, distribution = resolve(choice, self.state, self.rng, self.content.config)
        result = choice["outcomes"][outcome]
        text = self.content.render(result["text"], self.scene_context)
        apply_effects(choice.get("effects", {}), self.state)
        apply_effects(result.get("effects", {}), self.state)
        setattr(self.state, outcome + "_count", getattr(self.state, outcome + "_count") + 1)
        self.state.story_progress += 1
        duration = self.content.config["choice_seconds"]
        if not self.arc.get("inline_consequences"):
            duration += self.content.seconds(text)
        self.state.estimated_seconds += duration
        record = {"scene": self.current["id"], "choice_index": index, "choice_id": choice["id"],
                  "choice_text": choice["text"], "probabilities": distribution, "roll": roll,
                  "outcome": outcome, "text": text, "destination": result["next"],
                  "segment_id": segment_id(self.current["id"], choice["id"] + "_" + outcome, text)}
        self.state.previous_outcomes.append(copy.deepcopy(record))
        self.journal["choices"].append(record)
        self.pending = dict(record)
        self.pending["audio_file"] = result.get("audio_file")
        return self.pending

    def advance(self):
        if self.finished:
            raise ValueError("L'aventure est terminée.")
        if self.pending is not None:
            destination = self.pending["destination"]
            lead_in = self.pending["text"] if self.arc.get("inline_consequences") else None
            self.pending = None
            self._enter(destination, lead_in)
        elif self.current["kind"] == "intro":
            self._enter(self.current["next"])
        else:
            raise ValueError("Choisis une action avant de poursuivre.")
        return self.current

    def debug_snapshot(self):
        state = asdict(self.state)
        for key, value in list(state.items()):
            if isinstance(value, set):
                state[key] = sorted(value)
        state["arc_title"] = self.arc["title"]
        state["scene_variants"] = self.current["selected_variants"]
        state["next_probabilities"] = [probabilities(c, self.state, self.content.config)
                                        for c in self.current.get("choices", [])]
        return state

    def export_session(self, path):
        payload = copy.deepcopy(self.journal)
        payload["state"] = self.debug_snapshot()
        payload["pending"] = self.pending is not None
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def replay(cls, content, path):
        log = Content.read(path)
        if log.get("version") != cls.JOURNAL_VERSION:
            raise ValueError("Journal d'une ancienne version : les récits et leur découpage audio ont changé. Commence une nouvelle partie.")
        engine = cls(content, **log["configuration"], seed=log["seed"], arc_id=log.get("forced_arc"),
                     revelation_id=log.get("forced_revelation"))
        for saved in log["choices"]:
            if engine.current["kind"] == "intro":
                engine.advance()
            obtained = engine.choose(saved["choice_index"])
            for key in ("scene", "choice_id", "probabilities", "roll", "outcome", "text", "destination"):
                if obtained[key] != saved[key]:
                    raise ValueError(f"Le contenu a changé : différence dans {key}.")
            if saved is not log["choices"][-1] or not log.get("pending", False):
                engine.advance()
        # Un journal sans choix peut être enregistré après l'introduction.
        if not log["choices"] and len(log["scenes"]) == 2:
            engine.advance()
        for key, value in engine.journal.items():
            if value != log.get(key):
                raise ValueError(f"Le journal ne correspond plus au contenu : {key}.")
        if "state" in log and engine.debug_snapshot() != log["state"]:
            raise ValueError("L'état du journal ne correspond pas à la partie reproduite.")
        return engine
