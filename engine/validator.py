import itertools
import math
from dataclasses import asdict, dataclass, field

from .content import word_count, spoken_scene
from .rules import CONDITION_KEYS, EFFECT_KEYS, matches
from .story_state import StoryState
from .variants import templates
from .schema_validation import check_schema


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    configuration_count: int = 0
    arc_configuration_count: int = 0
    duration_bounds: dict = field(default_factory=dict)
    content_metrics: dict = field(default_factory=dict)

    @property
    def valid(self):
        return not self.errors

    def to_dict(self):
        return {"valid": self.valid, **asdict(self)}


def all_choices(scene):
    yield from scene.get("choices", [])
    for variant in scene.get("variants", []):
        yield from variant.get("choices", [])


def destinations(scene, arc):
    if scene.get("kind") == "intro":
        return {scene.get("next", "")}
    result = set()
    for choice in all_choices(scene):
        for outcome in choice.get("outcomes", {}).values():
            target = outcome.get("next", "")
            if target == "$ending":
                result.update(e["scene"] for e in arc.get("endings", []))
            else:
                result.add(target)
    return result


def condition_errors(condition, content, path):
    errors = []
    if not isinstance(condition, dict):
        return [f"{path} : condition non objet"]
    for key, value in condition.items():
        if key not in CONDITION_KEYS:
            errors.append(f"{path} : condition inconnue {key}")
        elif key in ("all", "any"):
            if not isinstance(value, list) or (key == "any" and not value):
                errors.append(f"{path} : {key} doit contenir une liste de conditions")
            else:
                for child in value:
                    errors.extend(condition_errors(child, content, path))
        elif key == "not":
            errors.extend(condition_errors(value, content, path))
        elif key in ("hero", "item", "location"):
            catalog = {"hero": content.heroes, "item": content.items, "location": content.locations}[key]
            if not isinstance(value, str) or value not in catalog:
                errors.append(f"{path} : {key} inconnu {value}")
        elif key.startswith("min_"):
            if type(value) is not int or value < 0:
                errors.append(f"{path} : compteur minimum invalide")
        elif not isinstance(value, str) or not value:
            errors.append(f"{path} : référence de condition invalide")
    return errors


def effect_errors(effects, path):
    if not isinstance(effects, dict):
        return [f"{path} : effets non objet"]
    return [f"{path} : effet invalide {key}" for key, value in effects.items()
            if key not in EFFECT_KEYS or not isinstance(value, list)
            or any(not isinstance(v, str) or not v for v in value)]


def number_between(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate_choice(choice, content, path):
    errors = []
    for key in ("id", "text"):
        if not isinstance(choice.get(key), str) or not choice[key]:
            errors.append(f"{path} : {key} manquant")
    if not number_between(choice.get("base_success"), 0, 1):
        errors.append(f"{path} : probabilité invalide")
    if not number_between(choice.get("complication_share", 0.3), 0.05, 0.95):
        errors.append(f"{path} : part de complication invalide (trois résultats doivent rester possibles)")
    for mod in choice.get("modifiers", []):
        if not number_between(mod.get("delta"), -1, 1):
            errors.append(f"{path} : modificateur invalide")
        errors.extend(condition_errors(mod.get("when", {}), content, path))
    errors.extend(effect_errors(choice.get("effects", {}), path))
    outcomes = choice.get("outcomes", {})
    if set(outcomes) != {"success", "complication", "failure"}:
        errors.append(f"{path} : trois résultats sont nécessaires")
    for name, outcome in outcomes.items():
        if not isinstance(outcome.get("next"), str) or not outcome["next"]:
            errors.append(f"{path}/{name} : choix sans destination")
        if not isinstance(outcome.get("text"), str) or not outcome["text"]:
            errors.append(f"{path}/{name} : conséquence sans texte")
        errors.extend(effect_errors(outcome.get("effects", {}), path))
    return errors


def _structural(content, report):
    for catalog_name in ("heroes", "locations", "items"):
        if len(getattr(content, catalog_name)) != 5:
            report.errors.append(f"Le catalogue {catalog_name} doit contenir cinq propositions.")
    cfg = content.config
    for key in ("words_per_minute", "choice_seconds", "minimum_seconds", "maximum_seconds"):
        if not number_between(cfg.get(key), 0.1 if key != "choice_seconds" else 0, 10000):
            report.errors.append(f"Configuration : {key} invalide")
    if not number_between(cfg.get("probability_min"), 0.01, 0.99) or not number_between(cfg.get("probability_max"), 0.01, 0.99):
        report.errors.append("Configuration : bornes de probabilité invalides")
    elif cfg["probability_min"] > cfg["probability_max"]:
        report.errors.append("Configuration : bornes de probabilité inversées")
    if cfg.get("minimum_seconds", 0) > cfg.get("maximum_seconds", 0):
        report.errors.append("Configuration : bornes de durée inversées")
    for sid, scene in content.scenes.items():
        if scene.get("arc") not in content.arcs:
            report.errors.append(f"{sid} : arc inexistant")
        if scene.get("kind") not in ("intro", "decision", "ending"):
            report.errors.append(f"{sid} : type de scène invalide")
        for key in ("id", "title", "text"):
            if not isinstance(scene.get(key), str) or not scene[key]:
                report.errors.append(f"{sid} : {key} manquant")
        if type(scene.get("rank")) is not int or scene["rank"] < 0:
            report.errors.append(f"{sid} : rang invalide")
        if type(scene.get("act")) is not int or not 1 <= scene["act"] <= 5:
            report.errors.append(f"{sid} : acte invalide")
        report.errors.extend(condition_errors(scene.get("conditions", {}), content, sid))
        report.errors.extend(effect_errors(scene.get("effects", {}), sid))
        if scene.get("kind") == "decision" and len(scene.get("choices", [])) != 2:
            report.errors.append(f"{sid} : exactement deux choix sont nécessaires")
        if scene.get("kind") == "intro" and not scene.get("next"):
            report.errors.append(f"{sid} : introduction sans destination")
        if scene.get("kind") == "ending" and (not scene.get("ending") or scene.get("choices") or scene.get("next")):
            report.errors.append(f"{sid} : conclusion mal formée")
        for variant in scene.get("variants", []):
            report.errors.extend(condition_errors(variant.get("when", {}), content, sid))
            report.errors.extend(effect_errors(variant.get("effects", {}), sid))
            if "choices" in variant and len(variant["choices"]) != 2:
                report.errors.append(f"{sid} : variante avec nombre de choix invalide")
        for choice in all_choices(scene):
            report.errors.extend(validate_choice(choice, content, sid))
    for aid, arc in content.arcs.items():
        count = arc.get("decision_count")
        if type(count) is not int or not 11 <= count <= 13:
            report.errors.append(f"{aid} : nombre de décisions invalide")
        report.errors.extend(condition_errors(arc.get("conditions", {}), content, aid))
        if not arc.get("revelations"):
            report.errors.append(f"{aid} : aucune révélation")
        endings = arc.get("endings", [])
        if not endings or endings[-1].get("when") != {}:
            report.errors.append(f"{aid} : arc sans conclusion de repli inconditionnelle")
        for ending in endings:
            report.errors.extend(condition_errors(ending.get("when", {}), content, aid))
            target = content.scenes.get(ending.get("scene"))
            if not target or target.get("kind") != "ending" or target.get("arc") != aid:
                report.errors.append(f"{aid} : conclusion inexistante ou hors de l'arc")
        start = content.scenes.get(arc.get("start"))
        if not start or start.get("kind") != "intro" or start.get("arc") != aid or start.get("rank") != 0:
            report.errors.append(f"{aid} : introduction invalide")
            continue
        graph = {}
        for sid, scene in content.scenes.items():
            if scene.get("arc") != aid:
                continue
            graph[sid] = destinations(scene, arc)
            for target in graph[sid]:
                other = content.scenes.get(target)
                if other is None:
                    report.errors.append(f"{sid} : lien vers une scène inexistante {target}")
                elif other.get("arc") != aid:
                    report.errors.append(f"{sid} : destination hors de l'arc {target}")
                elif type(scene.get("rank")) is int and other.get("rank") != scene["rank"] + 1:
                    report.errors.append(f"{sid} : transition qui ne progresse pas d'un rang vers {target}")
            if scene.get("kind") == "decision" and type(count) is int and not 1 <= scene.get("rank", -1) <= count:
                report.errors.append(f"{sid} : décision hors du budget")
            if scene.get("kind") == "ending" and type(count) is int and scene.get("rank") != count + 1:
                report.errors.append(f"{sid} : conclusion prématurée ou tardive")
        reached, visiting = set(), set()

        def visit(sid):
            if sid in visiting:
                report.errors.append(f"{aid} : boucle infinie potentielle à {sid}")
                return
            if sid in reached or sid not in graph:
                return
            visiting.add(sid)
            for target in graph[sid]:
                visit(target)
            visiting.remove(sid)
            reached.add(sid)

        visit(arc["start"])
        for sid in graph.keys() - reached:
            report.errors.append(f"{aid} : scène inaccessible {sid}")


def content_metrics(content):
    prose = set()
    for scene in content.scenes.values():
        for paragraph in scene["text"].split("\n\n"):
            if not (paragraph.startswith("{") and paragraph.endswith("}")):
                prose.add(paragraph)
        for variant in scene.get("variants", []):
            for key in ("text", "append"):
                if key in variant:
                    prose.add(variant[key])
        for choice in all_choices(scene):
            prose.update(outcome["text"] for outcome in choice["outcomes"].values())
    for collection, fields in ((content.heroes.values(), ("origin", "observation", "plan")),
                               (content.locations.values(), ("approach", "hazard", "secret", "core", "decision", "departure")),
                               (content.items.values(), ("appearance", "first", "second", "climax", "epilogue")),
                               (content.catalog["encounters"], ("intro", "story"))):
        for record in collection:
            prose.update(record[key] for key in fields)
    for arc in content.arcs.values():
        prose.update(r["text"] for r in arc["revelations"])
        for overrides in arc.get("item_overrides", {}).values():
            prose.update(overrides.values())
    words = sum(word_count(text) for text in prose)
    return {"arcs": len(content.arcs), "scenes": len(content.scenes),
            "distinct_prose_blocks": len(prose), "prepared_unique_words": words,
            "prepared_narration_minutes": round(words / content.config["words_per_minute"], 2)}


def _bounds(content, arc, hero, location, item):
    local = {}
    state = StoryState(hero, location, item, 0)
    for scene in content.scenes.values():
        if scene["arc"] != arc["id"]:
            continue
        options = list(templates(scene, hero, location, item))
        if not options:
            raise ValueError(f"Scène incompatible avec {hero}/{location}/{item} : {scene['id']}")
        dependencies = "\n".join([text for text, _, _ in options] +
                                 [c["text"] for _, choices, _ in options for c in choices] +
                                 [o["text"] for _, choices, _ in options for c in choices for o in c["outcomes"].values()])
        encounters = content.catalog["encounters"] if "{encounter_" in dependencies else content.catalog["encounters"][:1]
        revelations = arc["revelations"] if "{revelation_" in dependencies else arc["revelations"][:1]
        contexts = [content.context(state, npc, revelation, arc) for npc in encounters for revelation in revelations]
        durations = []
        for text, choices, _ in options:
            for context in contexts:
                rendered_choices = [{"text": content.render(c["text"], context)} for c in choices]
                duration = content.seconds(spoken_scene(content.render(text, context), rendered_choices))
                if not choices:
                    durations.append((duration, duration))
                else:
                    for choice in choices:
                        content.render(choice["text"], context)
                        for outcome in choice["outcomes"].values():
                            seconds = duration + content.seconds(content.render(outcome["text"], context)) + content.config["choice_seconds"]
                            durations.append((seconds, seconds))
        local[scene["id"]] = min(d[0] for d in durations), max(d[1] for d in durations)
    memo = {}

    def walk(sid):
        if sid in memo:
            return memo[sid]
        low, high = local[sid]
        following = destinations(content.scenes[sid], arc)
        if following:
            bounds = [walk(target) for target in following]
            low += min(b[0] for b in bounds)
            high += max(b[1] for b in bounds)
        memo[sid] = low, high
        return memo[sid]

    return walk(arc["start"])


def validate(content, check_duration=True):
    report = ValidationReport()
    schema = content.read(content.root / "content/schema.json")
    for aid, arc in content.arcs.items():
        report.errors.extend(check_schema(arc, schema["$defs"]["arc"], schema, aid))
    for sid, scene in content.scenes.items():
        report.errors.extend(check_schema(scene, schema["$defs"]["scene"], schema, sid))
    if report.errors:
        return report
    _structural(content, report)
    if report.errors:
        return report
    report.content_metrics = content_metrics(content)
    arc_bounds = {arc: [float("inf"), 0] for arc in content.arcs}
    for hero, location, item in itertools.product(content.heroes, content.locations, content.items):
        report.configuration_count += 1
        state = StoryState(hero, location, item, 0)
        compatible = [a for a in content.arcs.values() if matches(a.get("conditions", {}), state)]
        for arc in content.arcs.values():
            if arc not in compatible:
                report.errors.append(f"{arc['id']} : arc incompatible avec {hero}/{location}/{item}")
        if not compatible:
            report.errors.append(f"Aucun arc compatible : {hero}/{location}/{item}")
        for arc in compatible:
            report.arc_configuration_count += 1
            try:
                low, high = _bounds(content, arc, hero, location, item)
                arc_bounds[arc["id"]][0] = min(arc_bounds[arc["id"]][0], low)
                arc_bounds[arc["id"]][1] = max(arc_bounds[arc["id"]][1], high)
                if check_duration and (low < content.config["minimum_seconds"] or high > content.config["maximum_seconds"]):
                    report.errors.append(f"{arc['id']} {hero}/{location}/{item} : histoire estimée hors durée [{low/60:.2f}, {high/60:.2f}] min")
            except (KeyError, ValueError, TypeError) as exc:
                report.errors.append(f"{arc['id']} {hero}/{location}/{item} : {exc}")
    report.duration_bounds = {aid: {"minimum_minutes": round(bounds[0]/60, 2),
                                    "maximum_minutes": round(bounds[1]/60, 2)}
                              for aid, bounds in arc_bounds.items() if math.isfinite(bounds[0])}
    return report
