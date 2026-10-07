"""Shared, staged defaults for buttons created through any GUI entry point."""

import copy
import html
import re

from core.button_icons import persistent_icon

BUTTON_CLASS = "yasbgui-button"
APPS_CLASS = "yasbgui-app-buttons"
BEGIN = "/* YASB GUI button defaults: begin */"
END = "/* YASB GUI button defaults: end */"
CSS = """/* YASB GUI button defaults: begin */
.yasbgui-button .widget-container, .home-widget .widget-container, .power-menu-widget .widget-container {
    padding: 0 12px;
    margin: 4px 0;
    border: 1px solid rgba(255, 255, 255, 0.084);
    border-radius: 12px;
    background-color: rgba(255, 255, 255, 0.04);
}
.yasbgui-button .widget-container:hover, .home-widget .widget-container:hover, .power-menu-widget .widget-container:hover {
    background-color: rgba(60, 60, 60, 0.7);
    border-color: rgba(255, 255, 255, 0.105);
}
.yasbgui-button .label, .yasbgui-button .yasbgui-icon, .home-widget .yasbgui-menu-icon,
.power-menu-widget .label, .power-menu-widget .yasbgui-menu-icon {
    padding: 0 4px;
    margin: 0;
    min-height: 24px;
    qproperty-alignment: AlignCenter;
}
.yasbgui-app-buttons .widget-container {
    padding: 0;
    margin: 0;
    border: 0;
    background-color: transparent;
}
.yasbgui-app-buttons .label {
    padding: 0 12px;
    margin: 4px;
    border: 1px solid rgba(255, 255, 255, 0.084);
    border-radius: 12px;
    background-color: rgba(255, 255, 255, 0.04);
    min-height: 24px;
    qproperty-alignment: AlignCenter;
}
.yasbgui-app-buttons .label:hover {
    background-color: rgba(60, 60, 60, 0.7);
    border-color: rgba(255, 255, 255, 0.105);
}
/* YASB GUI button defaults: end */
"""


def ensure_button_css(current):
    if BEGIN in current and END in current:
        return current  # Preserve edits inside the previously installed block.
    if BEGIN in current or END in current:
        raise ValueError("Button style block is incomplete; restore its begin/end comments")
    # Prepend so same-specificity user overrides remain authoritative.
    return CSS + "\n" + current


def image_label(value, directory, marker="yasbgui-icon"):
    if "<img " in value:

        def copy_asset(match):
            path = persistent_icon(html.unescape(match[2]), directory)
            return f"src={match[1]}{html.escape(path, quote=True)}{match[1]}"

        result = re.sub(r"src=(['\"])(.*?)\1", copy_asset, value)
        if marker == "yasbgui-menu-icon" and marker not in result:
            result = f'<span class="{marker}">{result}</span>'
        return result

    def replace_span(match):
        content = match[2].strip()
        if not content or "{" in content or "<" in content:
            return match[0]
        content = html.unescape(content)
        if not all(0xE000 <= ord(char) <= 0xF8FF for char in content):
            return match[0]  # Text spans must remain text, including localized labels.
        path = persistent_icon(content, directory)
        return f'<span class="{marker}"><img src="{html.escape(path, quote=True)}" width="20" height="20"/></span>'

    result = re.sub(r"<span([^>]*)>(.*?)</span>", replace_span, value)
    if "<" not in result:
        result = re.sub(r"[\ue000-\uf8ff]+", lambda match: replace_span(re.match(r"()(.*)", match[0])), result)
    return result


def prepare_button_options(type_path, original, directory, previous=None):
    options = copy.deepcopy(original)
    if type_path == "yasb.applications.ApplicationsWidget":
        old_icons = {entry.get("icon") for entry in (previous or {}).get("app_list", [])}
        for entry in options.get("app_list", []):
            if entry.get("icon") not in old_icons:
                entry["icon"] = persistent_icon(entry["icon"], directory)
        classes = options.get("class_name", "").split()
        if APPS_CLASS not in classes:
            options["class_name"] = " ".join([*classes, APPS_CLASS])
        if previous is None:
            options["image_icon_size"] = 20
        return options, True
    if type_path in ("yasb.home.HomeWidget", "yasb.power_menu.PowerMenuWidget") and previous is None:
        label = options.get("label", "")
        options["label"] = image_label(label, directory, "yasbgui-menu-icon")
        return options, True
    if type_path == "yasb.custom.CustomWidget":
        callbacks = options.get("callbacks", {})
        command = any(str(value).startswith("exec ") for value in callbacks.values())
        if not command and BUTTON_CLASS not in options.get("class_name", "").split():
            return options, False
        classes = options.get("class_name", "").split()
        if BUTTON_CLASS not in classes:
            options["class_name"] = " ".join([*classes, BUTTON_CLASS])
        for key in ("label", "label_alt", "label_placeholder"):
            if isinstance(options.get(key), str):
                options[key] = image_label(options[key], directory)
        return options, True
    return options, False
