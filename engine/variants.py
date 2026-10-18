"""Énumération des états qui changent un segment, pour audit et export TTS.

Cette énumération donne une enveloppe conservative : certains états peuvent ne
pas être atteignables sur un même chemin. Elle n'écrit pas de récit nouveau.
"""
import copy
import itertools
import json
from functools import lru_cache

from .rules import apply_effects, matches
from .story_state import StoryState
from .content import text_values


def references(condition, collected):
    for key, value in (condition or {}).items():
        if key in ("all", "any"):
            for child in value:
                references(child, collected)
        elif key == "not":
            references(value, collected)
        elif key in ("flag", "ally", "inventory"):
            collected[key].add(value)
        elif key.startswith("min_"):
            collected[key].add(value)


def possible_states(scene, hero, location, item):
    refs = {key: set() for key in ("flag", "ally", "inventory", "min_success", "min_complication", "min_failure")}
    references(scene.get("conditions", {}), refs)
    for variant in scene.get("variants", []):
        references(variant.get("when", {}), refs)
    dimensions = []
    for key in ("flag", "ally", "inventory"):
        dimensions.extend((key, name, [False, True]) for name in sorted(refs[key]))
    for key in ("min_success", "min_complication", "min_failure"):
        if refs[key]:
            dimensions.append((key, None, sorted({0, *refs[key]})))
    if len(dimensions) > 14:
        raise ValueError(f"Trop de dépendances d'état pour l'audit exhaustif de {scene['id']}.")
    for values in itertools.product(*(dimension[2] for dimension in dimensions)):
        state = StoryState(hero, location, item, 0)
        state.inventory.add(item)
        for (key, name, _), value in zip(dimensions, values):
            if key.startswith("min_"):
                setattr(state, key.removeprefix("min_") + "_count", value)
            else:
                field = {"flag": "flags", "ally": "allies", "inventory": "inventory"}[key]
                if value:
                    getattr(state, field).add(name)
                else:
                    getattr(state, field).discard(name)
        if matches(scene.get("conditions", {}), state):
            yield state


def selector_references(condition):
    found = set()
    for key, value in (condition or {}).items():
        if key in ("hero", "location", "item"):
            found.add(key)
        elif key in ("all", "any"):
            for child in value:
                found.update(selector_references(child))
        elif key == "not":
            found.update(selector_references(value))
    return found


def templates(scene, hero, location, item):
    selectors = selector_references(scene.get("conditions", {}))
    for variant in scene.get("variants", []):
        selectors.update(selector_references(variant.get("when", {})))
    # Catalog prose is rendered later. Cache only the state-dependent assembly,
    # keyed by the complete scene so content edits cannot reuse stale templates.
    key = json.dumps(scene, ensure_ascii=False, sort_keys=True)
    prepared = _prepared_templates(key, hero if "hero" in selectors else "",
                                   location if "location" in selectors else "", item)
    for text, choices, ids in prepared:
        yield text, copy.deepcopy(choices), list(ids)


@lru_cache(maxsize=2048)
def _prepared_templates(source, hero, location, item):
    scene = json.loads(source)
    seen = set()
    result = []
    for state in possible_states(scene, hero, location, item):
        apply_effects(scene.get("effects", {}), state)
        text = scene["text"]
        choices = scene.get("choices", [])
        variant_ids = []
        values = {}
        for variant in scene.get("variants", []):
            if matches(variant.get("when", {}), state):
                variant_ids.append(variant["id"])
                values.update(variant.get("values", {}))
                text = variant.get("text", text)
                if "append" in variant:
                    text += "\n\n" + variant["append"]
                choices = variant.get("choices", choices)
                apply_effects(variant.get("effects", {}), state)
        text = text_values(text, values)
        choices = copy.deepcopy(choices)
        for choice in choices:
            choice["text"] = text_values(choice["text"], values)
            for outcome in choice["outcomes"].values():
                outcome["text"] = text_values(outcome["text"], values)
        key = text, tuple(c["id"] for c in choices), tuple(variant_ids)
        if key not in seen:
            seen.add(key)
            result.append((text, choices, tuple(variant_ids)))
    return tuple(result)
