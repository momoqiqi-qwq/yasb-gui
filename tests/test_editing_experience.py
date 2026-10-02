"""Regression coverage for file safety, preferences and save completion."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from core import file_io
from core.application import ConfiguratorApp
from core.config_manager import ConfigManager
from core.preferences import Preferences, editor_options, get_preferences
from winrt.windows.foundation import AsyncStatus


@pytest.fixture
def config(tmp_path, monkeypatch):
    directory = tmp_path / "yasb"
    directory.mkdir()
    monkeypatch.setenv("YASB_CONFIG_HOME", str(directory))
    (directory / "config.yaml").write_text(
        "# My setup\nwatch_config: true # live reload\nbars: {}\nwidgets: {}\n", encoding="utf-8"
    )
    (directory / "styles.css").write_text(".bar {color: red}", encoding="utf-8")
    manager = ConfigManager()
    manager.load_config()
    manager.load_styles()
    return manager


def test_empty_css_can_be_saved_and_previous_content_is_backed_up(config):
    assert config.save_styles("")
    assert Path(config.styles_path).read_text() == ""
    assert not config.has_styles_changed("")
    assert next(config.backup_directory.glob("styles.css.*.bak")).read_text() == ".bar {color: red}"


def test_failed_replacement_retains_original_and_dirty_state(config, monkeypatch):
    original = Path(config.config_path).read_bytes()
    config.config["debug"] = True
    monkeypatch.setattr(file_io.os, "replace", lambda *args: (_ for _ in ()).throw(PermissionError("locked")))
    assert not config.save_config()
    assert Path(config.config_path).read_bytes() == original
    assert config.has_config_changed()
    assert sorted(p.name for p in Path(config.config_path).parent.iterdir()) == ["config.yaml", "styles.css"]


def test_yaml_comments_and_quotes_survive_repeated_saves(config):
    path = Path(config.config_path)
    path.write_text(path.read_text() + 'custom: "001" # exact value\n', encoding="utf-8")
    config.load_config()
    config.config["debug"] = True
    assert config.save_config()
    config.load_config()
    assert config.save_config()
    text = Path(config.config_path).read_text()
    assert text.count("# My setup") == 1
    assert "# live reload" in text
    assert 'custom: "001" # exact value' in text


def test_backup_retention_is_per_file_and_can_be_disabled(config):
    prefs = get_preferences()
    prefs.set("backup_retention", 2)
    for value in range(5):
        assert config.save_styles(str(value))
    assert len(list(config.backup_directory.glob("styles.css.*.bak"))) == 2
    assert config.save_config()
    assert len(list(config.backup_directory.glob("config.yaml.*.bak"))) == 1
    prefs.set("backup_before_save", False)
    assert config.save_styles("disabled")
    assert len(list(config.backup_directory.glob("styles.css.*.bak"))) == 2


def test_schema_directive_tracks_profile_without_duplicate_headers(config):
    path = Path(config.config_path)
    path.write_text("# yaml-language-server: $schema=old\n" + path.read_text(), encoding="utf-8")
    config.load_config()
    get_preferences().set("yasb_schema_profile", "v2_0_6")
    assert config.save_config()
    text = path.read_text()
    assert text.count("yaml-language-server") == 1
    assert "/v2.0.6/schema.json" in text
    assert "# My setup" in text


def test_preferences_keep_existing_choices_after_reopen(tmp_path):
    (tmp_path / "settings.json").write_text('{"theme":"dark","editor_word_wrap":"off","custom":42}')
    prefs = Preferences()
    assert prefs.get("theme") == "dark"
    assert prefs.get("backup_before_save") is True
    prefs.set("editor_minimap", True)
    reopened = Preferences()
    assert reopened.get("editor_word_wrap") == "off"
    assert reopened.get("editor_minimap") is True
    assert reopened.get("custom") == 42


def test_editor_settings_map_to_monaco_options():
    prefs = get_preferences()
    prefs.set("editor_tab_size", 4)
    prefs.set("editor_line_numbers", "relative")
    prefs.set("editor_minimap", True)
    assert editor_options()["tabSize"] == 4
    assert editor_options()["lineNumbers"] == "relative"
    assert editor_options()["minimap"]["enabled"] is True


def save_harness(config, draft):
    operation = SimpleNamespace(completed=None, get_results=lambda: '""')
    harness = SimpleNamespace(
        _saving=False,
        _unsaved_config=False,
        _unsaved_styles=True,
        _unsaved_changes=True,
        _config_manager=config,
        _styles_page=SimpleNamespace(_editor_ready=True, _draft_content=draft),
        _styles_webview=SimpleNamespace(execute_script_async=lambda script: operation),
        _save_button=SimpleNamespace(is_enabled=True),
        _update_save_button_style=lambda: None,
        errors=[],
    )
    harness.mark_saved = lambda: ConfiguratorApp.mark_saved(harness)
    harness._show_save_error = harness.errors.append
    return harness, operation


def test_async_save_waits_for_completion_and_accepts_empty_css(config):
    harness, operation = save_harness(config, "")
    closed = []
    ConfiguratorApp._save_config(harness, on_saved=lambda: closed.append(not harness._saving))
    assert harness._saving and harness._unsaved_changes
    assert not closed
    operation.completed(operation, AsyncStatus.COMPLETED)
    assert closed == [True]
    assert not harness._unsaved_changes
    assert Path(config.styles_path).read_text() == ""


def test_async_read_failure_preserves_draft_and_does_not_close(config):
    harness, operation = save_harness(config, "draft")
    closed = []
    ConfiguratorApp._save_config(harness, on_saved=lambda: closed.append(True))
    operation.completed(operation, AsyncStatus.ERROR)
    assert harness._unsaved_changes and not harness._saving
    assert harness.errors and not closed
    assert Path(config.styles_path).read_text() == ".bar {color: red}"


def test_write_failure_preserves_draft_and_does_not_close(config, monkeypatch):
    harness, operation = save_harness(config, "")
    monkeypatch.setattr(config, "save_styles", lambda content: False)
    closed = []
    ConfiguratorApp._save_config(harness, on_saved=lambda: closed.append(True))
    operation.completed(operation, AsyncStatus.COMPLETED)
    assert harness._unsaved_changes and harness._save_button.is_enabled
    assert harness.errors and not closed


def test_new_edit_during_save_stays_dirty(config):
    harness, operation = save_harness(config, "")
    closed = []
    ConfiguratorApp._save_config(harness, on_saved=lambda: closed.append(True))
    harness._styles_page._draft_content = "new edit"
    operation.completed(operation, AsyncStatus.COMPLETED)
    assert harness._unsaved_changes and not closed


def test_partial_save_only_clears_successful_config_changes(config, monkeypatch):
    harness, operation = save_harness(config, "")
    config.config["debug"] = True
    harness._unsaved_config = True
    monkeypatch.setattr(config, "save_styles", lambda content: False)
    ConfiguratorApp._save_config(harness)
    operation.completed(operation, AsyncStatus.COMPLETED)
    assert not harness._unsaved_config
    assert harness._unsaved_styles and harness._unsaved_changes


def test_revisiting_styles_retains_page_and_draft(config):
    from pages.styles import StylesPage

    refreshed = []
    app = SimpleNamespace(
        _config_manager=config,
        _content_area=SimpleNamespace(content=None),
        apply_editor_options=lambda: refreshed.append(True),
    )
    page = StylesPage(app)
    page._page = object()
    page._draft_content = "unsaved css"
    page.show()
    assert app._content_area.content is page._page
    assert page._draft_content == "unsaved css"
    assert refreshed == [True]


def test_cache_clear_preserves_preferences_and_backups(tmp_path, monkeypatch):
    from pages import app_settings

    data = tmp_path / "profile"
    data.mkdir()
    settings = data / "settings.json"
    settings.write_text('{"theme":"dark"}')
    backups = data / "backups"
    backups.mkdir()
    backup = backups / "config.yaml.bak"
    backup.write_text("original")
    cache = tmp_path / "webview"
    cache.mkdir()
    (cache / "cached").write_text("cache")
    monkeypatch.setattr(app_settings, "WEBVIEW_CACHE_DIR", str(cache))
    monkeypatch.setattr(app_settings.subprocess, "Popen", lambda *args, **kwargs: None)
    app = SimpleNamespace(_window=SimpleNamespace(close=lambda: None))
    app_settings.AppSettingsPage._clear_cache_and_restart(SimpleNamespace(_app=app))
    assert settings.read_text() == '{"theme":"dark"}'
    assert backup.read_text() == "original"
    assert not (cache / "cached").exists()
