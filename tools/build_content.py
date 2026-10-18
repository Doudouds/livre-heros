"""Compilation éditoriale facultative. Le runtime ne lit que les JSON finaux.

Les sources écrites à l'avance se trouvent dans content/authored. Ce compilateur
ajoute des règles déclaratives communes et des raccords, sans inventer de récit.
"""
import json
from pathlib import Path

from engine.content import ROOT


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def modifier(label, when, delta):
    return {"label": label, "when": when, "delta": delta}


def compile_choice(source, scene_id, index, destination, rank):
    mods = [modifier("Formation du héros", {"hero": h}, 0.14) for h in source["heroes"]]
    if index == 0 and rank in (3, 7, 11):
        # Une condition par objet garantit que son acquisition précède l'usage.
        mods.append(modifier("Objet choisi et disponible", {"any": [
            {"all": [{"item": i}, {"inventory": i}]} for i in ("sword", "book", "amulet", "compass", "key")
        ]}, 0.12))
    mods.extend([modifier("Repères préparés", {"flag": "prepared"}, 0.06),
                 modifier("Instabilité précédente", {"flag": "unstable"}, -0.07)])
    if rank >= 6:
        mods.append(modifier("Aide du compagnon", {"ally": "companion"}, 0.06))
    outcomes = {}
    for category, text in zip(("success", "complication", "failure"), source["results"]):
        effects = {"events": [f"{scene_id}:{index}:{category}"]}
        if category == "success":
            effects["set_flags"] = ["prepared"]
            if source.get("flag"):
                effects["set_flags"].append(source["flag"])
            if rank == 5 and index == 0:
                effects["add_allies"] = ["companion"]
        elif category == "complication":
            effects["set_flags"] = ["strain"]
            if rank == 5 and index == 0:
                effects["add_allies"] = ["companion"]
        else:
            effects["set_flags"] = ["unstable"]
        if source.get("repair") and category != "failure":
            effects["unset_flags"] = ["unstable", "strain"]
        outcomes[category] = {"text": text, "next": destination, "effects": effects,
                              "audio_file": "audio/files/{segment_id}.wav"}
    return {"id": f"{scene_id}_{index}", "text": source["text"],
            "base_success": source.get("base", 0.63 if index == 0 else 0.66),
            "complication_share": 0.30, "modifiers": mods, "outcomes": outcomes}


def build(root=ROOT):
    catalog = json.loads((root / "content/catalog.json").read_text(encoding="utf-8"))
    for path in sorted((root / "content/authored").glob("*.json")):
        source = json.loads(path.read_text(encoding="utf-8"))
        if source.get("format") == "authored_graph":
            write(root / f"content/arcs/{source['arc']['id']}.json", source["arc"])
            write(root / f"content/scenes/{source['arc']['id']}.json", {"scenes": source["scenes"]})
            continue
        arc_id = source["id"]
        scenes = []
        prefix = lambda suffix: f"{arc_id}_{suffix}"
        intro = {"id": prefix("intro"), "arc": arc_id, "kind": "intro", "rank": 0, "act": 1,
                 "title": source["title"], "text": source["intro"] + "\n\n{hero_origin}\n\n{item_appearance}\n\n{encounter_intro}",
                 "next": prefix("1"), "conditions": {}, "effects": {}, "variants": [],
                 "audio_file": "audio/files/{segment_id}.wav"}
        scenes.append(intro)
        records = [(rank, str(rank), stage) for rank, stage in enumerate(source["stages"], 1)]
        records.append((5, "5b", source["branch"]))
        for rank, suffix, stage in records:
            scene_id = prefix(suffix)
            variants = [{k: v for k, v in variant.items() if k != "ranks"}
                        for variant in catalog["state_variants"] if rank in variant["ranks"]]
            effects = {}
            # Le véritable identifiant du lieu est ajouté via variantes, sans paramètre d'effet implicite.
            if rank == 1:
                effects = {}
                for location in ("castle", "forest", "mountain", "city", "ruins"):
                    variants.append({"id": f"visit_{location}", "when": {"location": location},
                                     "effects": {"visit_locations": [location]}})
            choices = []
            for index, choice in enumerate(stage["choices"]):
                destination = "$ending" if rank == 12 else prefix(str(rank + 1))
                if rank == 4 and index == 1:
                    destination = prefix("5b")
                choices.append(compile_choice(choice, scene_id, index, destination, rank))
            scenes.append({"id": scene_id, "arc": arc_id, "kind": "decision", "rank": rank,
                           "act": (rank - 1) // 3 + 1, "title": stage["title"],
                           "text": stage["text"] + "\n\n" + catalog["insertions"][str(rank)],
                           "conditions": {}, "effects": effects, "variants": variants, "choices": choices,
                           "audio_file": "audio/files/{segment_id}.wav"})
        selectors = [
            ("secret", {"flag": "secret"}),
            ("alliance", {"all": [{"ally": "companion"}, {"min_success": 4}]}),
            ("radiant", {"all": [{"min_success": 7}, {"not": {"flag": "unstable"}}]}),
            ("cost", {"min_complication": 3}),
            ("resilient", {})
        ]
        for ending, when in selectors:
            data = source["endings"][ending]
            scenes.append({"id": prefix("end_" + ending), "arc": arc_id, "kind": "ending",
                           "act": 5, "rank": 13, "title": data["title"], "ending": ending,
                           "text": data["text"] + "\n\n{location_departure}\n\n{item_epilogue}",
                           "conditions": {}, "effects": {}, "variants": [],
                           "audio_file": "audio/files/{segment_id}.wav"})
        arc = {"id": arc_id, "title": source["title"], "description": source["description"],
               "item_overrides": source.get("item_overrides", {}),
               "conditions": {}, "decision_count": 12, "start": prefix("intro"),
               "revelations": source["revelations"],
               "endings": [{"scene": prefix("end_" + ending), "when": when} for ending, when in selectors]}
        write(root / f"content/arcs/{arc_id}.json", arc)
        write(root / f"content/scenes/{arc_id}.json", {"scenes": scenes})
    print("Les manuscrits éditoriaux ont été compilés en JSON narratifs.")


if __name__ == "__main__":
    build()
