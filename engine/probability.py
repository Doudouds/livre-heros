from .rules import matches


def probabilities(choice, state, config):
    p = choice["base_success"]
    applied = []
    for modifier in choice.get("modifiers", []):
        if matches(modifier["when"], state):
            p += modifier["delta"]
            applied.append({"label": modifier["label"], "delta": modifier["delta"]})
    p = min(config["probability_max"], max(config["probability_min"], p))
    share = choice.get("complication_share", 0.30)
    return {"objective": p, "success": p * (1 - share),
            "complication": p * share, "failure": 1 - p,
            "modifiers": applied}


def resolve(choice, state, rng, config):
    distribution = probabilities(choice, state, config)
    roll = rng.random()
    if roll < distribution["success"]:
        outcome = "success"
    elif roll < distribution["objective"]:
        outcome = "complication"
    else:
        outcome = "failure"
    return outcome, roll, distribution
