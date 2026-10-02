"""Regression checks for unrestricted editing and safe configuration round trips."""

import json
import string
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from core.advanced_config import (
    dump_mapping,
    parse_mapping,
    parse_screens,
    parse_width,
    replace_global,
    replace_widgets,
    validate_bar,
)
from core.config_manager import ConfigManager


@pytest.mark.parametrize("text, expected", [("auto", "auto"), ("75%", "75%"), ("640", 640), (" 100% ", "100%")])
def test_width_modes(text, expected):
    assert parse_width(text) == expected


@pytest.mark.parametrize("text", ["", "0", "-1", "0%", "101%", "nan%", "inf%", "false", "3.5"])
def test_invalid_width(text):
    with pytest.raises(ValueError):
        parse_width(text)


@pytest.mark.parametrize("text", ["", "[]", "[1]", "[null]", "['']", "[name"])
def test_invalid_screens(text):
    with pytest.raises(Exception):
        parse_screens(text)


def test_screens_are_data_not_code(tmp_path):
    marker = tmp_path / "must-not-exist"
    parse_screens(f"[__import__('pathlib').Path('{marker.as_posix()}').touch()]")
    assert not marker.exists()
    assert parse_screens('["primary", "显示器 1"]') == ["primary", "显示器 1"]


@pytest.mark.parametrize("text", ["", "[]", "true", "123", "1: value", "a: 1\na: 2"])
def test_invalid_mapping(text):
    with pytest.raises(Exception):
        parse_mapping(text)


def test_roundtrip_preserves_extension_values():
    original = {"extension": {"label": "00123", "empty": "", "nullable": None, "off": False}, "title": "中文"}
    assert parse_mapping(dump_mapping(original)) == original
    assert "中文" in dump_mapping(original)


def test_replace_global_keeps_bars_widgets_and_deletes_removed_settings():
    config = {"debug": True, "old": 1, "bars": {"main": {}}, "widgets": {"clock": {}}}
    bars, widgets = config["bars"], config["widgets"]
    replace_global(config, {"debug": False, "custom": {"value": "007"}})
    assert config["bars"] is bars and config["widgets"] is widgets
    assert "old" not in config
    assert config["custom"]["value"] == "007"


@pytest.mark.parametrize("data", [{"bars": {}}, {"widgets": {}}, {"debug": "false"}, {"tooltip": []}])
def test_invalid_global_does_not_change_config(data):
    config = {"debug": True, "bars": {}, "widgets": {}}
    original = config.copy()
    with pytest.raises(ValueError):
        replace_global(config, data)
    assert config == original


@pytest.mark.parametrize(
    "data",
    [
        {"screens": "primary"},
        {"screens": []},
        {"dimensions": []},
        {"dimensions": {"height": 0}},
        {"dimensions": {"width": True}},
        {"widgets": {"left": ["missing"]}},
        {"widgets": {"left": "clock"}},
    ],
)
def test_invalid_bar(data):
    with pytest.raises(ValueError):
        validate_bar(data, {"clock"})


def test_valid_bar_preserves_unknown_options():
    data = parse_mapping('dimensions: {width: "640", height: 30}\nwidgets: {left: [clock]}\ncustom: {name: 中文}')
    validate_bar(data, {"clock"})
    assert data["dimensions"]["width"] == 640
    assert data["custom"]["name"] == "中文"


def test_save_does_not_coerce_or_remove_custom_values(tmp_path, monkeypatch):
    monkeypatch.setenv("YASB_CONFIG_HOME", str(tmp_path))
    manager = ConfigManager()
    manager.load_config()
    values = {"label": "123", "token": "00123", "blank": "", "null": None, "map": {}, "list": [], "off": False}
    manager.config["custom"] = values.copy()
    assert manager.save_config()
    assert manager.config["custom"] == values
    assert manager.load_config()["custom"] == values
    assert not manager.has_config_changed()


def test_chinese_locale_preserves_format_placeholders():
    locale_dir = Path(__file__).parent.parent / "app/core/locales"
    english = json.loads((locale_dir / "en.json").read_text(encoding="utf-8"))
    chinese = json.loads((locale_dir / "zh_CN.json").read_text(encoding="utf-8"))
    formatter = string.Formatter()
    for key, value in english.items():
        expected = {field for _, field, _, _ in formatter.parse(value) if field}
        actual = {field for _, field, _, _ in formatter.parse(chinese[key]) if field}
        assert expected == actual, key


def test_custom_widget_classes_and_extension_fields():
    config = {"bars": {"main": {"widgets": {"left": ["custom"]}}}}
    data = {"custom": {"type": "my_package.custom.Widget", "options": {"label": "你好"}, "extension": False}}
    replace_widgets(config, data)
    assert config["widgets"] == data


@pytest.mark.parametrize("data", [{}, {"clock": {}}, {"clock": {"type": "x", "options": []}}])
def test_widget_editor_rejects_broken_references_without_mutation(data):
    config = {"bars": {"main": {"widgets": {"left": ["clock"]}}}, "widgets": {"clock": {"type": "x"}}}
    original = config["widgets"]
    with pytest.raises(ValueError):
        replace_widgets(config, data)
    assert config["widgets"] is original
