"""Export de textes préparés, jamais de synthèse vocale. JSON Lines UTF-8."""
import argparse
import itertools
import json
import os
from pathlib import Path

from engine import Content, StoryEngine
from engine.content import segment_id, spoken_scene
from engine.story_state import StoryState
from engine.variants import templates


def entry(scene_id, role, text, content, emotion="adventurous"):
    key = segment_id(scene_id, role, text)
    return {"segment_id": key, "scene_id": scene_id, "role": role, "speaker": "narrator",
            "emotion": emotion, "text": text, "estimated_seconds": round(content.seconds(text), 2),
            "output_file": f"{content.config['audio_root']}/{key}.wav"}


def all_segments(content):
    seen = set()
    for arc in content.arcs.values():
        scenes = [s for s in content.scenes.values() if s["arc"] == arc["id"]]
        dependencies = json.dumps(scenes, ensure_ascii=False)
        encounters = content.catalog["encounters"] if "{encounter_" in dependencies else content.catalog["encounters"][:1]
        revelations = arc["revelations"] if "{revelation_" in dependencies else arc["revelations"][:1]
        for hero, location, item in itertools.product(content.heroes, content.locations, content.items):
            state = StoryState(hero, location, item, 0)
            contexts = [content.context(state, npc, revelation, arc) for npc in encounters for revelation in revelations]
            prepared = {s["id"]: list(templates(s, hero, location, item)) for s in scenes}
            incoming = {s["id"]: set() for s in scenes}
            if arc.get("inline_consequences"):
                incoming[arc["start"]].add("")
                for source in scenes:
                    if source["kind"] == "intro":
                        incoming[source["next"]].add("")
                    for _, choices, _ in prepared[source["id"]]:
                        for choice in choices:
                            for outcome in choice["outcomes"].values():
                                targets = [e["scene"] for e in arc["endings"]] if outcome["next"] == "$ending" else [outcome["next"]]
                                for target in targets:
                                    incoming[target].add(outcome["text"])
            for scene in scenes:
                for text, choices, _ in prepared[scene["id"]]:
                    for context in contexts:
                        rendered = content.render(text, context)
                        labels = [{"text": content.render(c["text"], context)} for c in choices]
                        prefixes = incoming[scene["id"]] if arc.get("inline_consequences") else [""]
                        records = []
                        for prefix in sorted(prefixes):
                            full_text = content.render(prefix, context) + "\n\n" + rendered if prefix else rendered
                            records.append(entry(scene["id"], "narration", spoken_scene(full_text, labels), content,
                                                 "warm" if scene["kind"] == "ending" else "mysterious"))
                        if not arc.get("inline_consequences"):
                            for choice in choices:
                                for name, outcome in choice["outcomes"].items():
                                    records.append(entry(scene["id"], choice["id"] + "_" + name,
                                                         content.render(outcome["text"], context), content,
                                                         "reassuring" if name == "failure" else "adventurous"))
                        for record in records:
                            if record["segment_id"] not in seen:
                                seen.add(record["segment_id"])
                                yield record


def session_segments(content, path):
    engine = StoryEngine.replay(content, path)
    for scene in engine.journal["scenes"]:
        yield entry(scene["id"], "narration", scene["spoken_text"], content)
    if not engine.arc.get("inline_consequences"):
        for result in engine.journal["choices"]:
            yield entry(result["scene"], result["choice_id"] + "_" + result["outcome"], result["text"], content)


def export(content, path, session=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for record in session_segments(content, session) if session else all_segments(content):
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return count


def main():
    parser = argparse.ArgumentParser(description="Exporter les textes complets pour Chatterbox, sans générer d'audio")
    parser.add_argument("--output", type=Path, default=Path("reports/tts_manifest.jsonl"))
    parser.add_argument("--session", type=Path, help="Limiter l'export à une partie enregistrée")
    parser.add_argument("--arc", help="Limiter l'export global à un conte, par exemple cages")
    args = parser.parse_args()
    content = Content()
    if args.arc:
        if args.session:
            parser.error("Utiliser --arc ou --session, séparément.")
        if args.arc not in content.arcs:
            parser.error("Conte inconnu : " + args.arc)
        content.arcs = {args.arc: content.arcs[args.arc]}
    print(f"{export(content, args.output, args.session)} segments exportés dans {args.output}")


if __name__ == "__main__":
    main()
