"""Chapitres fidèles à leur manuscrit, avec deux choix sans tirage aléatoire."""
import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .content import Content, segment_id, spoken_scene


@dataclass
class BookState:
    book_id: str
    current_scene: str = ""
    story_progress: int = 0
    estimated_seconds: float = 0
    flags: set = field(default_factory=set)
    conclusion: str | None = None


def validate_book(book, root=None):
    scenes = book["scenes"]
    ids = {s["id"] for s in scenes}
    if len(ids) != len(scenes) or book["start"] not in ids:
        raise ValueError("Identifiants ou ouverture du chapitre incorrects.")
    decisions = [s for s in scenes if s["kind"] == "decision"]
    if len(decisions) != book["decision_count"]:
        raise ValueError("Le nombre de décisions du chapitre est incohérent.")
    for index, scene in enumerate(scenes):
        if not scene.get("text", "").strip() or not scene.get("image") or not scene.get("image_alt"):
            raise ValueError(f"Passage incomplet : {scene['id']}")
        if scene["kind"] not in ("decision", "ending"):
            raise ValueError(f"Type de passage inconnu : {scene['id']}")
        choices = scene.get("choices", [])
        if scene["kind"] == "decision":
            if len(choices) != 2 or len({c["id"] for c in choices}) != 2:
                raise ValueError(f"Deux choix distincts sont requis : {scene['id']}")
            for choice in choices:
                if not choice["text"].strip() or not choice["consequence"].strip():
                    raise ValueError(f"Choix incomplet : {scene['id']}")
                # Ce format conserve l'ordre du manuscrit, sans saut ni boucle.
                if index + 1 >= len(scenes) or choice["next"] != scenes[index + 1]["id"]:
                    raise ValueError(f"Transition hors de la trame : {scene['id']}")
        elif choices or index != len(scenes) - 1:
            raise ValueError("La clôture doit terminer le chapitre.")
        if root is not None:
            base = Path(root).resolve()
            asset = (base / scene["image"]).resolve()
            if not asset.is_relative_to(base) or not asset.is_file():
                raise ValueError(f"Illustration absente ou hors projet : {scene['image']}")
    if not scenes or scenes[0]["id"] != book["start"] or scenes[-1]["kind"] != "ending":
        raise ValueError("Le chapitre doit avoir une ouverture et une clôture.")


class BookEngine:
    JOURNAL_FORMAT = "interactive-book"
    JOURNAL_VERSION = 1

    def __init__(self, content, book_id="passeuse_ch1"):
        self.content = content
        self.book = content.books[book_id]
        validate_book(self.book)
        self.scenes = {s["id"]: s for s in self.book["scenes"]}
        self.arc = {"id": book_id, "title": self.book["title"], "inline_consequences": True}
        self.state = BookState(book_id)
        fingerprint = hashlib.sha256(json.dumps(self.book, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        self.journal = {"format": self.JOURNAL_FORMAT, "version": self.JOURNAL_VERSION,
                        "book": book_id, "content_hash": fingerprint, "scenes": [], "choices": [],
                        "conclusion": None}
        self.pending = None
        self._enter(self.book["start"])

    @property
    def finished(self):
        return self.state.conclusion is not None

    def _enter(self, scene_id, lead_in=None):
        scene = copy.deepcopy(self.scenes[scene_id])
        text = scene["text"]
        for echo in scene.get("echoes", []):
            if echo["flag"] in self.state.flags:
                text += "\n\n" + echo["text"]
        if lead_in:
            text = lead_in + "\n\n" + text
        scene["text"] = text
        scene["spoken_text"] = spoken_scene(text, scene.get("choices", []))
        scene["segment_id"] = segment_id(scene_id, "narration", scene["spoken_text"])
        self.state.current_scene = scene_id
        self.state.estimated_seconds += self.content.seconds(scene["spoken_text"])
        self.current = scene
        self.journal["scenes"].append({"id": scene_id, "text": text, "segment_id": scene["segment_id"]})
        if scene["kind"] == "ending":
            self.state.conclusion = "chapter_complete"
            self.journal["conclusion"] = self.state.conclusion

    def choose(self, index):
        if self.finished or self.current["kind"] != "decision" or self.pending is not None:
            raise ValueError("Ce passage n'attend pas de choix.")
        if type(index) is not int or index not in (0, 1):
            raise ValueError("Le choix doit être 0 ou 1.")
        choice = self.current["choices"][index]
        self.state.flags.update(choice.get("flags", []))
        self.state.story_progress += 1
        self.state.estimated_seconds += self.content.config["choice_seconds"]
        record = {"scene": self.current["id"], "choice_index": index, "choice_id": choice["id"],
                  "choice_text": choice["text"], "text": choice["consequence"], "destination": choice["next"]}
        self.journal["choices"].append(record)
        self.pending = copy.deepcopy(record)
        return self.pending

    def advance(self):
        if self.pending is None or self.finished:
            raise ValueError("Choisis une action avant de poursuivre.")
        record = self.pending
        self.pending = None
        self._enter(record["destination"], record["text"])
        return self.current

    def debug_snapshot(self):
        return {"book_id": self.state.book_id, "current_scene": self.state.current_scene,
                "story_progress": self.state.story_progress,
                "estimated_seconds": self.state.estimated_seconds,
                "flags": sorted(self.state.flags), "conclusion": self.state.conclusion}

    def export_session(self, path):
        payload = copy.deepcopy(self.journal)
        payload.update(state=self.debug_snapshot(), pending=self.pending is not None)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def replay(cls, content, path):
        log = Content.read(path)
        if log.get("format") != cls.JOURNAL_FORMAT or log.get("version") != cls.JOURNAL_VERSION:
            raise ValueError("Format de journal de livre inconnu.")
        engine = cls(content, log["book"])
        if log.get("content_hash") != engine.journal["content_hash"]:
            raise ValueError("Le chapitre a changé depuis l'enregistrement de ce journal.")
        for index, saved in enumerate(log["choices"]):
            if engine.choose(saved["choice_index"]) != saved:
                raise ValueError("Le journal ne correspond pas aux choix du chapitre.")
            if index < len(log["choices"]) - 1 or not log.get("pending", False):
                engine.advance()
        if any(log.get(key) != value for key, value in engine.journal.items()):
            raise ValueError("Le journal ne correspond pas aux passages du chapitre.")
        if log.get("state") != engine.debug_snapshot():
            raise ValueError("L'état du journal ne correspond pas au chapitre.")
        return engine
