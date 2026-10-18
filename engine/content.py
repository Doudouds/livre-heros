import hashlib
import json
import re
from pathlib import Path
from string import Formatter


ROOT = Path(__file__).resolve().parents[1]
WORD_PATTERN = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*", re.UNICODE)


def word_count(text):
    return len(WORD_PATTERN.findall(text))


def segment_id(scene_id, role, text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
    return f"{scene_id}_{role}_{digest}"


def choice_prompt(choices):
    return "Que fais-tu ? Choix 1 : " + choices[0]["text"].rstrip(".?!") + ". Ou choix 2 : " + choices[1]["text"].rstrip(".?!") + "."


def spoken_scene(text, choices):
    return text + "\n\n" + choice_prompt(choices) if choices else text


def text_values(text, values):
    """Insert authored fragments; leave catalog substitutions for render()."""
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


class Content:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.config = self.read(self.root / "config.json")
        self.catalog = self.read(self.root / "content/catalog.json")
        self.heroes = self._catalog("heroes")
        self.locations = self._catalog("locations")
        self.items = self._catalog("items")
        self.arcs = {}
        self.scenes = {}
        self.books = {}
        for path in sorted((self.root / "content/books").glob("*.json")):
            book = self.read(path)
            if book["id"] in self.books:
                raise ValueError(f"Livre dupliqué : {book['id']}")
            self.books[book["id"]] = book
        for path in sorted((self.root / "content/arcs").glob("*.json")):
            arc = self.read(path)
            if arc["id"] in self.arcs:
                raise ValueError(f"Arc dupliqué : {arc['id']}")
            self.arcs[arc["id"]] = arc
        for path in sorted((self.root / "content/scenes").glob("*.json")):
            for scene in self.read(path)["scenes"]:
                if scene["id"] in self.scenes:
                    raise ValueError(f"Scène dupliquée : {scene['id']}")
                self.scenes[scene["id"]] = scene
        if not self.arcs or not self.scenes:
            raise ValueError("Le contenu narratif est vide.")

    @staticmethod
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))

    def _catalog(self, name):
        records = self.read(self.root / f"content/{name}.json")
        result = {record["id"]: record for record in records}
        if len(result) != len(records):
            raise ValueError(f"Identifiant dupliqué dans {name}")
        return result

    def context(self, state, encounter, revelation, arc=None):
        context = dict(self.catalog.get("text_values", {}))
        for prefix, entry in (("hero", self.heroes[state.hero_type]),
                              ("location", self.locations[state.mandatory_location]),
                              ("item", self.items[state.chosen_item]),
                              ("encounter", encounter), ("revelation", revelation)):
            context.update({f"{prefix}_{k}": v for k, v in entry.items() if isinstance(v, str)})
        if arc is None:
            arc = self.arcs.get(state.arc_id, {})
        context.update(arc.get("text_values", {}))
        for prefix, selected in (("hero", state.hero_type), ("location", state.mandatory_location)):
            context.update({f"{prefix}_{key}": value for key, value in
                            arc.get(prefix + "_overrides", {}).get(selected, {}).items()})
        overrides = arc.get("item_overrides", {}).get(state.chosen_item, {})
        context.update({f"item_{key}": value for key, value in overrides.items()})
        return context

    @staticmethod
    def render(text, context):
        for _, key, spec, conversion in Formatter().parse(text):
            if key is not None and (key not in context or spec or conversion):
                raise ValueError(f"Substitution interdite ou inconnue : {key}")
        return text.format_map(context)

    def seconds(self, text):
        return word_count(text) * 60 / self.config["words_per_minute"]
