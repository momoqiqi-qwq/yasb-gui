"""Presets must match their execution context and never replace drafts implicitly."""

import base64
import json
import shutil
import subprocess

import pytest
from core.command_presets import command_button_templates, command_presets, field_presets, powershell_command
from core.preferences import get_preferences
from core.yasb_schema import errors_for, resolve, widget_schemas


@pytest.mark.parametrize("profile", ["stable", "v2_0_6", "development"])
def test_command_buttons_are_click_only_and_compatible(profile, monkeypatch):
    monkeypatch.setitem(get_preferences()._settings, "yasb_schema_profile", profile)
    templates = command_button_templates()
    assert len(templates) == 12
    assert len({template["id"] for template in templates}) == len(templates)
    for template in templates:
        options = template["defaults"]
        assert options["exec_options"]["run_cmd"] is None
        assert options["callbacks"]["on_left"].startswith("exec ")
        assert errors_for(options, widget_schemas()[template["type_path"]]) == []


def test_presets_cover_system_map_and_encoded_commands():
    presets = command_presets()
    system_actions = {"start_menu", "search", "quick_settings", "notification_center"}
    for preset in presets:
        if preset["id"] in system_actions:
            assert preset["launch"] == preset["id"]
        else:
            tokens = preset["launch"].split()
            assert len(tokens) == 4 and tokens[:3] == ["powershell.exe", "-NoProfile", "-EncodedCommand"]
            assert base64.b64decode(tokens[-1]).decode("utf-16-le").startswith("Start-Process ")


def test_callbacks_only_offer_this_components_builtin_actions():
    volume = resolve(widget_schemas()["yasb.volume.VolumeWidget"]["properties"]["callbacks"])
    options = field_presets(("callbacks", "on_left"), volume)
    actions = {item["value"] for item in options}
    assert {"toggle_volume_menu", "toggle_mute", "do_nothing"} <= actions
    assert "toggle_power_menu" not in actions
    assert "exec start_menu" in actions
    assert field_presets(("label",), volume) == []


def test_polling_commands_return_data_instead_of_launching_apps():
    presets = field_presets(("exec_options", "run_cmd"), {})
    assert len(presets) == 2
    for preset in presets:
        script = base64.b64decode(preset["value"].split()[-1]).decode("utf-16-le")
        assert "ConvertTo-Json" in script and "Start-Process" not in script


def test_powershell_presets_parse_and_time_poll_returns_json():
    if not shutil.which("powershell.exe"):
        pytest.skip("Windows PowerShell is not available")
    commands = [p["launch"] for p in command_presets() if p["launch"].startswith("powershell.exe ")]
    polling = field_presets(("exec_options", "run_cmd"), {})
    commands.extend(p["value"] for p in polling)
    for command in commands:
        script = base64.b64decode(command.split()[-1]).decode("utf-16-le")
        literal = script.replace("'", "''")
        parser = f"$tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseInput('{literal}',[ref]$tokens,[ref]$errors);if($errors.Count){{exit 1}}"
        result = subprocess.run(powershell_command(parser).split(), capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
    result = subprocess.run(polling[0]["value"].split(), capture_output=True, timeout=15)
    assert result.returncode == 0
    assert "message" in json.loads(result.stdout)
