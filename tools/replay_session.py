import argparse
import json

from engine import Content, StoryEngine


def main():
    parser = argparse.ArgumentParser(description="Vérifier la reproduction exacte d'un journal debug")
    parser.add_argument("journal")
    args = parser.parse_args()
    try:
        engine = StoryEngine.replay(Content(), args.journal)
        print(json.dumps({"verified": True, "seed": engine.state.seed, "arc": engine.state.arc_id,
                          "decisions": engine.state.story_progress, "ending": engine.state.conclusion}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Journal non reproductible : {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
