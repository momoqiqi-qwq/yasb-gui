"""Version-specific coverage for official schemas, templates, localization and compatibility."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from core.preferences import get_preferences
from core.ui_errors import display_error
from core.writing_templates import command_templates
from core.yasb_schema import compatibility_errors, errors_for, load_schema, make_defaults, widget_schemas

PROFILES = ["v2_0_6", "stable", "development"]
WIDGETS = [(profile, name, node) for profile in PROFILES for name, node in widget_schemas(profile).items()]


@pytest.mark.parametrize("selected, type_path, node", WIDGETS, ids=[f"{p}:{n}" for p, n, _ in WIDGETS])
def test_every_official_widget_template_is_valid(selected, type_path, node):
    options = make_defaults(node, load_schema(selected))
    assert errors_for(options, node, selected) == [], type_path


@pytest.mark.parametrize("selected", PROFILES)
def test_official_catalog_has_complete_chinese_names_and_fields(selected):
    translations = json.loads(
        (Path(__file__).parent.parent / "app/core/locales/zh_CN.json").read_text(encoding="utf-8")
    )
    for type_path in widget_schemas(selected):
        key = "widget_" + type_path.rsplit(".", 1)[0].replace(".", "_")
        assert re.search(r"[\u4e00-\u9fff]", translations[key]), key
    for definition in load_schema(selected)["$defs"].values():
        for key in definition.get("properties", {}):
            assert "field_" + key in translations, key


@pytest.mark.parametrize("selected", PROFILES)
def test_writing_templates_are_valid(selected, monkeypatch):
    monkeypatch.setitem(get_preferences()._settings, "yasb_schema_profile", selected)
    for template in command_templates():
        node = widget_schemas()[template["type_path"]]
        assert errors_for(template["defaults"], node) == []


def test_stable_rejects_development_only_bar_style(monkeypatch):
    config = {"widgets": {}, "bars": {"main": {"style": "adaptive"}}}
    monkeypatch.setitem(get_preferences()._settings, "yasb_schema_profile", "stable")
    assert compatibility_errors(config)
    monkeypatch.setitem(get_preferences()._settings, "yasb_schema_profile", "development")
    assert compatibility_errors(config) == []


def test_custom_classes_still_editable(monkeypatch):
    monkeypatch.setitem(get_preferences()._settings, "yasb_schema_profile", "stable")
    assert compatibility_errors({"widgets": {"custom": {"type": "custom.module.Widget", "options": {}}}}) == []


def test_parser_errors_are_shown_in_chinese():
    assert "第 4 行" in display_error("Line 4, Column 2: expected mapping")
    assert "组件" in display_error("Unknown widgets: missing")


def test_monaco_chinese_pack_is_bundled_and_enabled():
    folder = Path(__file__).parent.parent / "app/core/editor"
    pack = (folder / "monaco/vs/nls.messages.zh-cn.js").read_text(encoding="utf-8")
    assert 'define("vs/nls.messages.zh-cn"' in pack
    assert '_VSCODE_NLS_LANGUAGE="zh-cn"' in pack
    html = (folder / "code_editor.html").read_text(encoding="utf-8")
    assert "{ '*': 'zh-cn' }" in html
