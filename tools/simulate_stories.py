import argparse
import json
from pathlib import Path

from engine import Content
from engine.simulator import audit_configurations, simulate


def main():
    parser = argparse.ArgumentParser(description="Simuler des contes sans interface")
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--policy", choices=["random", "a", "b", "alternate"], default="random")
    parser.add_argument("--all-configurations", action="store_true", help="125 trios × six arcs × deux politiques")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = Content()
    report = audit_configurations(content, args.seed) if args.all_configurations else simulate(content, args.count, args.seed, args.policy)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        summary = {k:v for k,v in report.items() if k not in ("results", "scenes", "endings")}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0 if report.get("valid", True) and not report.get("timing", {}).get("outside_target", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
