"""Petit langage de conditions déclaratif : aucun eval ni code dans les JSON."""

CONDITION_KEYS = {"all", "any", "not", "hero", "item", "location", "flag", "ally",
                  "inventory", "min_success", "min_failure", "min_complication"}
EFFECT_KEYS = {"set_flags", "unset_flags", "add_allies", "remove_allies",
               "add_inventory", "remove_inventory", "visit_locations", "meet_characters",
               "add_enemies", "events"}


def matches(condition, state):
    if not condition:
        return True
    checks = []
    for key, value in condition.items():
        if key == "all":
            checks.append(all(matches(c, state) for c in value))
        elif key == "any":
            checks.append(any(matches(c, state) for c in value))
        elif key == "not":
            checks.append(not matches(value, state))
        elif key in {"hero", "item", "location"}:
            field = {"hero": "hero_type", "item": "chosen_item", "location": "mandatory_location"}[key]
            checks.append(getattr(state, field) == value)
        elif key in {"flag", "ally", "inventory"}:
            field = {"flag": "flags", "ally": "allies", "inventory": "inventory"}[key]
            checks.append(value in getattr(state, field))
        elif key in {"min_success", "min_failure", "min_complication"}:
            field = key.removeprefix("min_") + "_count"
            checks.append(getattr(state, field) >= value)
        else:
            raise ValueError(f"Condition inconnue : {key}")
    return all(checks)


def apply_effects(effects, state):
    fields = {"flags": "flags", "allies": "allies", "inventory": "inventory",
              "locations": "visited_locations", "characters": "met_characters", "enemies": "enemies"}
    for key, values in (effects or {}).items():
        if key not in EFFECT_KEYS:
            raise ValueError(f"Effet inconnu : {key}")
        if key == "events":
            state.events.extend(values)
            continue
        action, noun = key.split("_", 1)
        target = getattr(state, fields[noun])
        if action in {"unset", "remove"}:
            target.difference_update(values)
        else:
            target.update(values)
