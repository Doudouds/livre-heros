"""Validateur du sous-ensemble JSON Schema utilisé par le contrat local.

Sans dépendance réseau. Les mots-clés pris en charge sont explicitement ceux du
schéma fourni ; pour un contrat tiers complet, utiliser un validateur JSON Schema.
"""
import math


def check_schema(value, schema, root=None, path="$", depth=0):
    root = schema if root is None else root
    if depth > 80:
        return [f"{path} : imbrication excessive"]
    if "$ref" in schema:
        reference = schema["$ref"]
        if not reference.startswith("#/"):
            return [f"{path} : référence de schéma non locale"]
        target = root
        for part in reference[2:].split("/"):
            target = target[part]
        return check_schema(value, target, root, path, depth + 1)
    errors = []
    recur = lambda child, rule, name=path: check_schema(child, rule, root, name, depth + 1)
    for keyword, required_count in (("oneOf", 1), ("anyOf", None)):
        if keyword in schema:
            count = sum(not recur(value, rule) for rule in schema[keyword])
            if (required_count is not None and count != required_count) or (required_count is None and count == 0):
                errors.append(f"{path} : {keyword} non satisfait")
    for rule in schema.get("allOf", []):
        errors.extend(recur(value, rule))
    if "not" in schema and not recur(value, schema["not"]):
        errors.append(f"{path} : forme interdite")
    if "if" in schema:
        branch = "then" if not recur(value, schema["if"]) else "else"
        if branch in schema:
            errors.extend(recur(value, schema[branch]))
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} : valeur attendue {schema['const']}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} : valeur hors liste")
    kind = schema.get("type")
    predicates = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
                  "string": lambda v: isinstance(v, str), "integer": lambda v: type(v) is int,
                  "number": lambda v: type(v) in (int, float) and math.isfinite(v),
                  "null": lambda v: v is None, "boolean": lambda v: type(v) is bool}
    if kind:
        kinds = kind if isinstance(kind, list) else [kind]
        if not any(predicates[k](value) for k in kinds):
            return errors + [f"{path} : type attendu {kind}"]
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path} : champ requis {key}")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                errors.extend(recur(child, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path} : champ inconnu {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(recur(child, schema["additionalProperties"], f"{path}.{key}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            errors.append(f"{path} : nombre d'éléments invalide")
        if "items" in schema:
            for i, child in enumerate(value):
                errors.extend(recur(child, schema["items"], f"{path}[{i}]"))
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        errors.append(f"{path} : texte trop court")
    if type(value) in (int, float):
        if not math.isfinite(value) or value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            errors.append(f"{path} : nombre hors limites")
    return errors
