"""Validated, round-trip YAML editing without discarding extension settings."""

from io import StringIO

from ruamel.yaml import YAML


def yaml_parser():
    parser = YAML()
    parser.preserve_quotes = True
    parser.allow_unicode = True
    parser.indent(mapping=2, sequence=4, offset=2)
    return parser


def dump_mapping(data):
    stream = StringIO()
    yaml_parser().dump(data, stream)
    return stream.getvalue()


def parse_mapping(text):
    data = yaml_parser().load(text)
    if not isinstance(data, dict):
        raise ValueError("advanced_error_mapping")
    if any(not isinstance(key, str) for key in data):
        raise ValueError("advanced_error_keys")
    return data


def parse_screens(text):
    text = text.strip()
    data = yaml_parser().load(text) if text.startswith("[") else [text]
    if not isinstance(data, list) or not data or any(not isinstance(v, str) or not v.strip() for v in data):
        raise ValueError("advanced_error_screens")
    return data


def parse_width(text):
    text = text.strip()
    if text == "auto":
        return text
    if text.isdecimal() and int(text) > 0:
        return int(text)
    if text.endswith("%"):
        try:
            percent = float(text[:-1])
            if 0 < percent <= 100:
                return text
        except ValueError:
            pass
    raise ValueError("advanced_error_width")


def validate_global(data):
    if "bars" in data or "widgets" in data:
        raise ValueError("advanced_error_scope")
    for key in ("watch_stylesheet", "watch_config", "debug", "update_check", "show_systray", "system_colors"):
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f"{key}: boolean required")
    for key in ("komorebi", "glazewm", "tooltip"):
        if key in data and not isinstance(data[key], dict):
            raise ValueError(f"{key}: mapping required")


def validate_bar(data, widget_names):
    for key in ("enabled", "context_menu"):
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f"{key}: boolean required")
    for key in ("alignment", "dimensions", "padding", "window_flags", "blur_effect", "animation", "layouts", "widgets"):
        if key in data and not isinstance(data[key], dict):
            raise ValueError(f"{key}: mapping required")
    if "screens" in data:
        screens = data["screens"]
        if not isinstance(screens, list) or not screens or any(not isinstance(v, str) or not v for v in screens):
            raise ValueError("advanced_error_screens")
    dimensions = data.get("dimensions", {})
    if "width" in dimensions:
        width = dimensions["width"]
        if isinstance(width, bool) or not isinstance(width, (int, str)):
            raise ValueError("advanced_error_width")
        dimensions["width"] = parse_width(str(width))
    if "height" in dimensions:
        height = dimensions["height"]
        if isinstance(height, bool) or not isinstance(height, int) or height <= 0:
            raise ValueError("dimensions.height: positive integer required")
    for position, names in data.get("widgets", {}).items():
        if position not in ("left", "center", "right"):
            raise ValueError(f"widgets.{position}: unknown position")
        if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ValueError(f"widgets.{position}: list of names required")
        missing = set(names) - set(widget_names)
        if missing:
            raise ValueError("Unknown widgets: " + ", ".join(sorted(missing)))


def replace_global(config, data):
    validate_global(data)
    for key in list(config):
        if key not in ("bars", "widgets"):
            del config[key]
    config.update(data)


def replace_widgets(config, data):
    """Accept custom widget classes while rejecting broken bar references."""
    for name, widget in data.items():
        if not isinstance(widget, dict) or not isinstance(widget.get("type"), str) or not widget["type"].strip():
            raise ValueError(f"{name}: widget type required")
        if "options" in widget and not isinstance(widget["options"], dict):
            raise ValueError(f"{name}.options: mapping required")
    for bar in config.get("bars", {}).values():
        for names in bar.get("widgets", {}).values():
            missing = set(names or []) - set(data)
            if missing:
                raise ValueError("Unknown widgets: " + ", ".join(sorted(missing)))
    config["widgets"] = data
