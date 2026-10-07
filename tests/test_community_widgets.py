"""Companion integration configuration and deployment regression coverage."""

import base64
import hashlib
import json
import os
import re
import subprocess

import pytest
from core import community_widgets as community
from core.preferences import get_preferences
from core.yasb_schema import errors_for, widget_schemas


@pytest.fixture(autouse=True)
def integration_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(community, "APP_DATA_DIR", str(tmp_path / "profile with space"))


@pytest.mark.parametrize("profile", ["stable", "v2_0_6", "development"])
@pytest.mark.parametrize("kind", ["device", "screenshot_full", "screenshot_region", "protonvpn"])
def test_generated_options_match_supported_schema(profile, kind, monkeypatch, tmp_path):
    monkeypatch.setitem(get_preferences()._settings, "yasb_schema_profile", profile)
    executable = tmp_path / "Proton VPN 测试.exe"
    executable.touch()
    options = community.build_community_options(kind, executable=str(executable) if kind == "protonvpn" else "")
    assert errors_for(options, widget_schemas()["yasb.custom.CustomWidget"]) == []
    assert options["exec_options"]["use_shell"] is False


def test_device_spaces_survive_yasb_polling_parser(tmp_path):
    exe = tmp_path / "设备 & test's.exe"
    exe.touch()
    options = community.build_community_options("device", executable=str(exe), interval=30)
    tokens = options["exec_options"]["run_cmd"].split(" ")
    command = base64.b64decode(tokens[-1]).decode("utf-16-le")
    assert str(exe).replace("'", "''") in command
    assert options["exec_options"]["run_interval"] == 30000


def test_callback_spaces_and_metacharacters_remain_literal(tmp_path):
    folder = tmp_path / "截图 & folder"
    options = community.build_community_options("screenshot_full", output_directory=str(folder))
    callback = options["callbacks"]["on_left"]
    # Match the upstream BaseWidget callback tokenizer.
    args = [s.strip('"') for s in re.findall(r'".+?"|[^ ]+', callback)]
    assert args[args.index("-OutputDirectory") + 1] == str(folder)
    assert args[args.index("-File") + 1].endswith("screenshot.ps1")


def test_pinned_device_and_license_are_deployed():
    path = community.installed_asset("vendor/device_status.exe")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == community.DEVICE_SHA256
    assert "MIT License" in path.with_name("MochaGlass-LICENSE.md").read_text()
    assert community.installed_asset("vendor/device_status.exe") == path


def test_modified_installed_script_is_not_silently_overwritten():
    path = community.installed_asset("screenshot.ps1")
    path.write_text("user changes")
    with pytest.raises(ValueError):
        community.installed_asset("screenshot.ps1")
    assert path.read_text() == "user changes"


@pytest.mark.parametrize(
    "kind,kwargs",
    [
        ("device", {"interval": 1}),
        ("device", {"interval": 3601}),
        ("device", {"executable": "missing.exe"}),
        ("protonvpn", {}),
        ("screenshot_full", {"output_directory": "relative/path"}),
    ],
)
def test_invalid_setup_fails_before_config_changes(kind, kwargs):
    with pytest.raises(ValueError):
        community.build_community_options(kind, **kwargs)


def test_device_json_runtime(tmp_path):
    executable = community.EXTENSIONS_DIR / "vendor/device_status.exe"
    process = subprocess.run(
        [str(executable)],
        capture_output=True,
        timeout=30,
        env={
            **os.environ,
            "TEMP": str(tmp_path),
            "TMP": str(tmp_path),
        },
    )
    assert process.returncode == 0
    data = json.loads(process.stdout)
    assert isinstance(data["compact"], str)
    assert isinstance(data["tooltip"], str)
    assert isinstance(data["count"], int)


def test_generated_polling_command_runs_with_profile_spaces(tmp_path):
    options = community.build_community_options("device")
    process = subprocess.run(
        options["exec_options"]["run_cmd"].split(" "),
        capture_output=True,
        timeout=30,
        env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
    )
    assert process.returncode == 0, process.stderr
    assert isinstance(json.loads(process.stdout)["count"], int)


def test_powershell_companions_parse():
    for script in community.EXTENSIONS_DIR.glob("*.ps1"):
        escaped = str(script).replace("'", "''")
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "$tokens=$null; $errors=$null; "
                f"[void][Management.Automation.Language.Parser]::ParseFile('{escaped}', [ref]$tokens, [ref]$errors); "
                "if ($errors.Count) { $errors | ForEach-Object Message; exit 1 }",
            ],
            capture_output=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("kind", ["device", "screenshot_full", "screenshot_region", "protonvpn"])
def test_existing_integration_can_be_recognized_after_rename_and_style_change(kind, tmp_path):
    exe = tmp_path / "Proton VPN.exe"
    exe.touch()
    options = community.build_community_options(kind, executable=str(exe) if kind == "protonvpn" else "")
    options["class_name"] = "my-personal-style"
    settings = community.integration_settings({"type": "yasb.custom.CustomWidget", "options": options})
    assert settings["kind"] == kind


def test_reconfigure_keeps_labels_styles_and_other_callbacks():
    original = community.build_community_options("screenshot_full")
    original.update(label="my label", class_name="custom-style", custom_setting=42)
    original["callbacks"]["on_right"] = "exec notepad.exe"
    generated = community.build_community_options("screenshot_region")
    result = community.update_integration_options(original, generated, "screenshot_region")
    assert result["label"] == "my label" and result["class_name"] == "custom-style"
    assert result["callbacks"]["on_right"] == "exec notepad.exe"
    assert result["custom_setting"] == 42
    assert (
        community.integration_settings({"type": "yasb.custom.CustomWidget", "options": original})["kind"]
        == "screenshot_full"
    )


def test_unknown_custom_command_is_not_claimed_as_integration():
    assert (
        community.integration_settings(
            {
                "type": "yasb.custom.CustomWidget",
                "options": {"exec_options": {"run_cmd": "echo custom"}, "callbacks": {"on_left": "exec notepad.exe"}},
            }
        )
        is None
    )


def test_dependency_check_reports_missing_program(tmp_path):
    assert community.integration_health({"kind": "protonvpn", "executable": str(tmp_path / "missing.exe")})
