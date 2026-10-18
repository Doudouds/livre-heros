"""Vérifier que des parties réelles trouvent leurs segments dans le manifeste."""
import argparse
import json
import random
from pathlib import Path

from engine import Content, StoryEngine


def verify(content, path, count=250, seed=101):
    ids = set()
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if "{" in record["text"] or "}" in record["text"]:
                raise ValueError("Une substitution n'a pas été résolue.")
            ids.add(record["segment_id"])
    rng = random.Random(seed)
    checked = 0
    for _ in range(count):
        engine = StoryEngine(content, rng.choice(list(content.heroes)), rng.choice(list(content.locations)),
                             rng.choice(list(content.items)), rng.getrandbits(64))
        while True:
            if engine.current["segment_id"] not in ids:
                raise ValueError(f"Narration absente : {engine.current['segment_id']}")
            checked += 1
            if engine.current["choice_segment_id"]:
                if engine.current["choice_segment_id"] not in ids:
                    raise ValueError(f"Choix absents : {engine.current['choice_segment_id']}")
                checked += 1
            if engine.finished:
                break
            if engine.current["kind"] == "intro":
                engine.advance()
            else:
                result = engine.choose(rng.randrange(2))
                if not engine.arc.get("inline_consequences"):
                    if result["segment_id"] not in ids:
                        raise ValueError(f"Conséquence absente : {result['segment_id']}")
                    checked += 1
                engine.advance()
    return {"valid": True, "manifest_segments": len(ids), "adventures_checked": count,
            "segments_checked": checked, "seed": seed}


def main():
    parser = argparse.ArgumentParser(description="Vérifier la couverture TTS sans synthèse vocale")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--count", type=int, default=250)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(Content(), args.manifest, args.count)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
