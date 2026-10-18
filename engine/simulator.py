import itertools
import random
from collections import Counter
from statistics import mean

from .story_engine import StoryEngine


def complete(engine, chooser):
    if engine.current["kind"] == "intro":
        engine.advance()
    while not engine.finished:
        engine.choose(chooser(engine))
        engine.advance()
    return engine


def simulate(content, count=10000, seed=2026, policy="random"):
    if type(count) is not int or count < 1:
        raise ValueError("Le nombre de parties doit être positif.")
    if policy not in ("random", "a", "b", "alternate"):
        raise ValueError("Politique de choix inconnue.")
    rng = random.Random(seed)
    durations, arcs, endings, scenes, outcomes = [], Counter(), Counter(), Counter(), Counter()
    decisions = Counter()
    for _ in range(count):
        engine = StoryEngine(content, rng.choice(list(content.heroes)), rng.choice(list(content.locations)),
                             rng.choice(list(content.items)), rng.getrandbits(64))
        chooser = {"random": lambda e: rng.randrange(2), "a": lambda e: 0, "b": lambda e: 1,
                   "alternate": lambda e: e.state.story_progress % 2}[policy]
        complete(engine, chooser)
        state = engine.state
        durations.append(state.estimated_seconds)
        decisions[state.story_progress] += 1
        arcs[state.arc_id] += 1
        endings[f"{state.arc_id}:{state.conclusion}"] += 1
        scenes.update(s["id"] for s in engine.journal["scenes"])
        for key in ("success", "complication", "failure"):
            outcomes[key] += getattr(state, key + "_count")
    ordered = sorted(durations)
    percentile = lambda fraction: ordered[min(count-1, int((count-1)*fraction))] / 60
    for sid in content.scenes:
        scenes.setdefault(sid, 0)
    usage = sorted(scenes.items(), key=lambda pair: (pair[1], pair[0]))
    return {"count": count, "simulation_seed": seed, "choice_policy": policy,
            "timing": {"words_per_minute": content.config["words_per_minute"],
                       "choice_seconds": content.config["choice_seconds"],
                       "mean_minutes": round(mean(durations)/60, 3),
                       "minimum_minutes": round(min(durations)/60, 3),
                       "maximum_minutes": round(max(durations)/60, 3),
                       "p05_minutes": round(percentile(.05), 3), "p95_minutes": round(percentile(.95), 3),
                       "outside_target": sum(not content.config["minimum_seconds"] <= d <= content.config["maximum_seconds"] for d in durations)},
            "decisions": dict(sorted(decisions.items())), "arcs": dict(sorted(arcs.items())),
            "endings": dict(sorted(endings.items())), "outcomes_total": dict(outcomes),
            "outcomes_per_adventure": {k: round(v/count, 3) for k,v in outcomes.items()},
            "scenes": dict(sorted(scenes.items())), "least_used_scenes": usage[:10],
            "most_used_scenes": usage[-10:][::-1]}


def audit_configurations(content, seed=730):
    rows = []
    for index, (hero, location, item) in enumerate(itertools.product(content.heroes, content.locations, content.items)):
        for arc in content.arcs:
            for policy in ("a", "b"):
                engine = StoryEngine(content, hero, location, item, seed + index, arc)
                complete(engine, lambda e: 0 if policy == "a" else 1)
                rows.append({"hero": hero, "location": location, "item": item, "arc": arc,
                             "policy": policy, "decisions": engine.state.story_progress,
                             "minutes": round(engine.state.estimated_seconds / 60, 3),
                             "ending": engine.state.conclusion,
                             "valid": engine.finished and engine.state.story_progress == content.arcs[arc]["decision_count"]
                             and content.config["minimum_seconds"] <= engine.state.estimated_seconds <= content.config["maximum_seconds"]})
    return {"initial_configurations": 125, "arc_configurations": len(rows)//2,
            "adventures": len(rows), "valid": all(row["valid"] for row in rows), "results": rows}
