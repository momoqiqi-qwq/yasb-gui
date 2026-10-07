"""Regression tests for Explorer selection and safe application-list editing."""

import base64
import copy

import pytest
from core.apps_editor import APPS_TYPE, application_entry, parse_selection, update_app_list
from core.yasb_schema import errors_for, make_defaults, widget_schemas


def test_explorer_single_multiple_and_cancel():
    assert parse_selection("") == []
    assert parse_selection("C:\\Program Files\\中文.exe\0\0") == ["C:\\Program Files\\中文.exe"]
    assert parse_selection("C:\\应用目录\0one.exe\0two.lnk\0\0") == ["C:\\应用目录\\one.exe", "C:\\应用目录\\two.lnk"]


@pytest.mark.parametrize("extension", [".exe", ".lnk", ".url"])
def test_launch_keeps_literal_path_through_yasb_whitespace_split(tmp_path, extension):
    path = tmp_path / ("中文 app's & $test" + extension)
    path.touch()
    entry = application_entry(path)
    tokens = entry["launch"].split()
    assert len(tokens) == 4
    script = base64.b64decode(tokens[-1]).decode("utf-16-le")
    assert script == "Start-Process -FilePath '" + str(path.resolve()).replace("'", "''") + "'"
    assert entry["name"] == path.stem
    assert entry["icon"]


def test_missing_or_wrong_file_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        application_entry(tmp_path / "missing.exe")
    path = tmp_path / "data.txt"
    path.touch()
    with pytest.raises(ValueError):
        application_entry(path)


@pytest.mark.parametrize("profile", ["stable", "v2_0_6", "development"])
def test_list_change_preserves_settings_and_does_not_mutate_draft(tmp_path, profile):
    node = widget_schemas(profile)[APPS_TYPE]
    original = make_defaults(node)
    original.update(label="custom", class_name="my-apps", image_icon_size=24, tooltip=False)
    original["app_list"] = [{"icon": "A", "launch": "old command", "name": None}]
    snapshot = copy.deepcopy(original)
    path = tmp_path / "app.exe"
    path.touch()
    entries = copy.deepcopy(original["app_list"])
    entries.append(application_entry(path))
    result = update_app_list(original, entries)
    assert original == snapshot
    assert {k: v for k, v in result.items() if k != "app_list"} == {
        k: v for k, v in original.items() if k != "app_list"
    }
    assert errors_for(result, node, selected=profile) == []
    entries.clear()
    assert len(result["app_list"]) == 2


def test_apps_routes_to_special_editor_and_yaml_is_still_available(monkeypatch, tmp_path):
    from pages import widgets

    widget = {"type": APPS_TYPE, "options": {"label": "x", "app_list": []}}
    page = object.__new__(widgets.WidgetsPage)
    from types import SimpleNamespace

    page._config_manager = SimpleNamespace(get_widget=lambda name: widget, config_path=tmp_path / "config.yaml")
    staged = []
    page._app = SimpleNamespace(stage_button_styles=lambda: staged.append(True))
    page._widget_registry = {}
    page._load_widgets = lambda: None
    calls = []
    monkeypatch.setattr(widgets, "show_apps_editor", lambda *args: calls.append(args))
    page._show_widget_editor_dialog = lambda **kwargs: calls.append(kwargs)
    page._show_edit_widget_dialog("apps", "left")
    assert calls[-1][1] is widget["options"]
    calls[-1][2]({"label": "new", "app_list": []})
    assert staged == [True]
    assert widget["options"]["label"] == "new"
    page._show_edit_widget_dialog("apps", "left", yaml_only=True)
    assert calls[-1]["widget_type"] == APPS_TYPE
