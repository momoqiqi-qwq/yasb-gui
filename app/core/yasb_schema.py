"""Official versioned schemas, widget templates and localized diagnostics."""

import copy
import json
from functools import lru_cache
from pathlib import Path

from core.localization import t
from core.preferences import get_preferences
from jsonschema import Draft202012Validator

STABLE_VERSION = "v2.0.7"


def profile():
    value = get_preferences().get("yasb_schema_profile", "stable")
    return value if value in ("stable", "v2_0_6", "development") else "stable"


@lru_cache(maxsize=3)
def load_schema(selected=None):
    selected = selected or profile()
    return json.loads((Path(__file__).parent / "schemas" / f"{selected}.json").read_text(encoding="utf-8"))


def resolve(node, schema=None):
    schema = schema or load_schema(profile())
    if "$ref" in node:
        return {**schema["$defs"][node["$ref"].split("/")[-1]], **{k: v for k, v in node.items() if k != "$ref"}}
    return node


def widget_schemas(selected=None):
    schema = load_schema(selected or profile())
    result = {}
    for definition in schema["$defs"].values():
        properties = definition.get("properties", {})
        type_path = properties.get("type", {}).get("const")
        if type_path and "options" in properties:
            result[type_path] = resolve(properties["options"], schema)
    return result


def make_defaults(node, schema=None):
    schema = schema or load_schema(profile())
    node = resolve(node, schema)
    if "default" in node:
        return copy.deepcopy(node["default"])
    if "const" in node:
        return node["const"]
    if "enum" in node:
        return node["enum"][0]
    if "anyOf" in node or "oneOf" in node:
        choices = node.get("anyOf", node.get("oneOf", []))
        return make_defaults(next((c for c in choices if c.get("type") != "null"), choices[0]), schema)
    kind = node.get("type")
    if kind == "object":
        return {
            key: make_defaults(value, schema)
            for key, value in node.get("properties", {}).items()
            if "default" in value or key in node.get("required", [])
        }
    if kind == "array":
        return [make_defaults(node.get("items", {}), schema) for _ in range(node.get("minItems", 0))]
    if kind in ("integer", "number"):
        return max(node.get("minimum", 0), node.get("exclusiveMinimum", -1) + 1)
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    return "" if not node.get("minLength") else "value"


def errors_for(data, node=None, selected=None):
    schema = load_schema(selected or profile())
    target = {**(node or schema), "$defs": schema["$defs"]}
    errors = []
    for issue in sorted(Draft202012Validator(target).iter_errors(data), key=lambda e: str(list(e.absolute_path))):
        path = ".".join(str(part) for part in issue.absolute_path) or t("schema_root")
        errors.append(
            t(
                "schema_validation_error",
                path=path,
                rule=issue.validator,
                detail=json.dumps(issue.validator_value, ensure_ascii=False),
            )
        )
    return errors


def validate_options(type_path, options):
    node = widget_schemas().get(type_path)
    if node:
        errors = errors_for(options, node)
        if errors:
            raise ValueError("\n".join(errors[:8]))


def compatibility_errors(config):
    """Validate official settings while allowing explicitly custom Python widget types."""
    schema = copy.deepcopy(load_schema(profile()))
    # Custom widgets remain editable but get their own structural validation elsewhere.
    known = widget_schemas()
    data = copy.deepcopy(config)
    widgets = data.get("widgets", {})
    if not isinstance(widgets, dict):
        return errors_for(data, schema)
    option_errors = []
    for name, widget in widgets.items():
        if not isinstance(widget, dict) or not isinstance(widget.get("type"), str) or not widget.get("type"):
            return [t("error_widget_type") + ": " + str(name)]
        if not isinstance(widget.get("options", {}), dict):
            return [t("error_mapping", field=str(name) + ".options")]
        if widget.get("type") in known:
            option_errors.extend(
                str(name) + ".options: " + error
                for error in errors_for(widget.get("options", {}), known[widget["type"]])
            )
    if option_errors:
        return option_errors
    data["widgets"] = {k: v for k, v in widgets.items() if v.get("type") in known}
    return errors_for(data, schema)


def field_label(key):
    label = t("field_" + key)
    return t("schema_parameter") if label == "field_" + key else label
