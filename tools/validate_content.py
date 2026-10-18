import argparse
import json
from pathlib import Path

from engine import Content
from engine.validator import validate


def main():
    parser = argparse.ArgumentParser(description="Valider JSON, graphe, compatibilité et durée")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = validate(Content()).to_dict()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"valid": False, "errors": [f"Chargement impossible : {exc}"]}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
