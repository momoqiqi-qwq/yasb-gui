"""Editable command and keyboard templates validated against official YASB schemas."""

from core.localization import t
from core.yasb_schema import make_defaults, widget_schemas


def command_templates():
    type_path = "yasb.custom.CustomWidget"
    templates = []
    for name, key, json_output, shortcuts in (
        ("custom_text", "widgets_template_text", False, False),
        ("custom_json", "widgets_template_json", True, False),
        ("custom_shortcuts", "widgets_template_shortcuts", False, True),
    ):
        options = make_defaults(widget_schemas()[type_path])
        options["class_name"] = "custom-widget"
        options["label"] = "{data[message]}" if json_output else "{data}"
        options["label_placeholder"] = t("template_loading")
        options["exec_options"].update(
            {
                "run_cmd": "powershell.exe -NoProfile -Command \"@{ message = 'Hello YASB' } | ConvertTo-Json -Compress\""
                if json_output
                else "powershell.exe -NoProfile -Command \"Write-Output 'Hello YASB'\"",
                "return_format": "json" if json_output else "string",
                "run_interval": 5000,
                "encoding": "utf-8",
                "use_shell": True,
            }
        )
        if shortcuts:
            options["keybindings"] = [{"keys": "ctrl+alt+y", "action": "exec notepad.exe", "screen": "active"}]
            options["callbacks"]["on_left"] = "exec notepad.exe"
        templates.append(
            {
                "id": name,
                "name": t(key),
                "category": t("schema_templates"),
                "description": t("widgets_template_desc"),
                "type_path": type_path,
                "defaults": options,
                "doc_link": "https://docs.yasb.dev/latest/widgets/custom",
            }
        )
    return templates
