"""Command presets shared by application entries, callbacks and command widgets."""

import base64
import html

from core.button_icons import bundled_icon
from core.localization import t
from core.yasb_schema import make_defaults, resolve, widget_schemas


def powershell_command(script):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return f"powershell.exe -NoProfile -EncodedCommand {encoded}"


def command_presets():
    presets = []
    for identifier, script, icon in (
        ("explorer", "Start-Process explorer.exe", "\ue8b7"),
        ("notepad", "Start-Process notepad.exe", "\ue70f"),
        ("calculator", "Start-Process calc.exe", "\ue8ef"),
        ("settings", "Start-Process 'ms-settings:'", "\ue713"),
        ("task_manager", "Start-Process taskmgr.exe", "\ue9d9"),
        ("control_panel", "Start-Process control.exe", "\ue713"),
        ("recycle_bin", "Start-Process explorer.exe -ArgumentList 'shell:RecycleBinFolder'", "\ue74d"),
        ("terminal", "Start-Process powershell.exe", "\ue756"),
    ):
        presets.append(
            {
                "id": identifier,
                "name": t("preset_" + identifier),
                "icon": bundled_icon(identifier),
                "launch": powershell_command(script),
            }
        )
    # These names are handled by YASB's function_map in apps and exec callbacks.
    for identifier, icon in (
        ("start_menu", "\ue700"),
        ("search", "\ue721"),
        ("quick_settings", "\ue713"),
        ("notification_center", "\ue91c"),
    ):
        presets.append(
            {
                "id": identifier,
                "name": t("preset_" + identifier),
                "icon": bundled_icon(identifier),
                "launch": identifier,
            }
        )
    return presets


def field_presets(path, parent_node):
    """Scope built-in actions to this callback schema, never to unrelated widgets."""
    if not path:
        return []
    key = path[-1]
    is_callback = len(path) > 1 and path[-2] == "callbacks"
    if is_callback:
        actions = ["do_nothing"]
        for raw in resolve(parent_node).get("properties", {}).values():
            default = resolve(raw).get("default")
            if isinstance(default, str) and default and default not in actions:
                actions.append(default)
        result = [{"name": t("preset_builtin", action=value), "value": value} for value in actions]
        result.extend({"name": p["name"], "value": "exec " + p["launch"]} for p in command_presets())
        return result
    if key == "run_cmd":
        # Polling commands must return data rather than repeatedly opening apps.
        return [
            {"name": t("preset_data_" + identifier), "value": powershell_command(script)}
            for identifier, script in (
                ("time", "@{message=(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')} | ConvertTo-Json -Compress"),
                ("computer", "@{message=($env:COMPUTERNAME + ' / ' + $env:USERNAME)} | ConvertTo-Json -Compress"),
            )
        ]
    if key in ("launch", "command"):
        # function_map names are not executable commands for polling run_cmd.
        return [{"name": p["name"], "value": p["launch"]} for p in command_presets() if " " in p["launch"]]
    return []


def command_button_templates():
    type_path = "yasb.custom.CustomWidget"
    result = []
    for preset in command_presets():
        options = make_defaults(widget_schemas()[type_path])
        label = f'<span class="yasbgui-icon"><img src="{html.escape(preset["icon"], quote=True)}" width="20" height="20"/></span>'
        options.update(class_name="yasbgui-button", label=label, tooltip=True, tooltip_label=preset["name"])
        options["exec_options"]["run_cmd"] = None
        options["exec_options"]["run_once"] = True
        options["callbacks"]["on_left"] = "exec " + preset["launch"]
        result.append(
            {
                "id": "command_" + preset["id"],
                "name": preset["name"],
                "category": t("preset_command_buttons"),
                "description": t("preset_button_desc"),
                "type_path": type_path,
                "defaults": options,
                "doc_link": "https://docs.yasb.dev/latest/widgets/custom",
            }
        )
    return result
