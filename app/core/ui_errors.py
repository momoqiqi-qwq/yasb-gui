"""Chinese summaries for technical parser diagnostics; original text stays in logs."""

import re

from core.localization import get_instance, t


def display_error(error):
    message = str(error)
    if get_instance().get_current_language() != "zh_CN" or re.search(r"[\u4e00-\u9fff]", message):
        return t(message)
    if message.startswith("advanced_error_"):
        return t(message)
    position = re.search(r"(?:Line|line) (\d+)(?:, (?:Col|Column|column) (\d+))?", message)
    if position:
        return t("error_yaml_position", line=position[1], column=position[2] or "1")
    for text, key in (
        ("boolean required", "error_boolean"),
        ("mapping required", "error_mapping"),
        ("Unknown widgets:", "error_widget_reference"),
        ("positive integer", "error_positive"),
        ("Widget type mismatch", "error_widget_type"),
        ("widget type required", "error_widget_type"),
        ("YAML", "error_yaml_generic"),
        ("while parsing", "error_yaml_generic"),
        ("found duplicate", "error_yaml_generic"),
        ("unknown position", "error_widget_position"),
    ):
        if text in message:
            field = message.split(":", 1)[0] if ":" in message else "YAML"
            return t(key, field=field)
    return t("error_yaml_generic")
