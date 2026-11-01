"""Regression cases for round-trip edits, schema profiles and release formats."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from core import code_editor, file_io, schema_fetcher, updater, widget_helpers, yasb_schema
from core.config_manager import ConfigManager
from core.preferences import get_preferences
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("YASB_CONFIG_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "# setup\nbars: {}\nwidgets:\n  clock:\n    type: yasb.clock.ClockWidget\n"
        '    options:\n      label: "Clock" # label\n',
        encoding="utf-8",
    )
    manager = ConfigManager()
    manager.load_config()
    return manager


def test_comment_only_edit_is_dirty_and_revert_is_clean(config):
    original = copy.deepcopy(config.config)
    config.config.yaml_set_comment_before_after_key("widgets", before="new comment")
    assert config.has_config_changed()
    config._config = original
    assert not config.has_config_changed()


def test_quote_only_edit_is_dirty_and_persists(config):
    options = config.get_widget("clock")["options"]
    assert isinstance(options["label"], DoubleQuotedScalarString)
    options["label"] = SingleQuotedScalarString("Clock")
    assert config.has_config_changed()
    assert config.save_config()
    assert not config.has_config_changed()
    assert "label: 'Clock' # label" in Path(config.config_path).read_text(encoding="utf-8")
    config.load_config()
    assert not config.has_config_changed()


@pytest.mark.parametrize("wrapped", [False, True])
def test_widget_yaml_comment_edit_survives_apply_and_save(config, wrapped):
    options = '# changed comment\nlabel: "Clock" # label\n'
    text = (
        options
        if not wrapped
        else 'type: yasb.clock.ClockWidget\noptions:\n  # changed comment\n  label: "Clock" # label\n'
    )
    success, error = widget_helpers.save_widget_options(config, "clock", text)
    assert success, error
    assert config.has_config_changed()
    assert config.save_config()
    assert "# changed comment" in Path(config.config_path).read_text(encoding="utf-8")


def test_editor_parser_retains_top_level_comments():
    data, error = code_editor.parse_yaml('# user note\nlabel: "Clock"\n')
    assert error is None
    assert "# user note" in code_editor.dict_to_yaml(data)


def test_delete_widget_clears_every_bar_reference(config):
    config.config["bars"] = {
        "main": {"widgets": {"left": ["clock", "other", "clock"], "center": ["clock", "clock"]}},
        "second": {"widgets": {"right": ["clock", "clock"]}},
    }
    assert config.delete_widget("clock")
    assert config.get_widgets() == {}
    assert config.get_bar("main")["widgets"] == {"left": ["other"], "center": []}
    assert config.get_bar("second")["widgets"] == {"right": []}


@pytest.fixture
def schema_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(schema_fetcher, "SCHEMA_DB_PATH", tmp_path / "widget_schemas.json")


def database(selected, field):
    return {
        "_meta": {"version": 2, "profile": selected, "source": schema_fetcher._schema_source(selected)},
        "widgets": {"yasb.notes.NotesWidget": {"hierarchy": {"_root": {"type": "dict", "children": [field]}}}},
    }


def test_schema_cache_is_isolated_when_switching_profiles(schema_cache):
    for selected in ("stable", "v2_0_6", "development"):
        assert schema_fetcher.save_schema_database(database(selected, selected), selected=selected)
    for selected in ("development", "v2_0_6", "stable", "development"):
        get_preferences().set("yasb_schema_profile", selected)
        assert schema_fetcher.get_widget_key_hierarchy("yasb.notes.NotesWidget")["_root"]["children"] == [selected]


@pytest.mark.parametrize("invalid", ["profile", "source", "version"])
def test_mismatched_schema_cache_uses_bundled_profile(schema_cache, invalid):
    data = database("stable", "wrong_field")
    data["_meta"][invalid] = "wrong"
    assert schema_fetcher.save_schema_database(data)
    node = yasb_schema.widget_schemas("stable")["yasb.notes.NotesWidget"]
    expected = schema_fetcher._build_key_hierarchy(node, yasb_schema.load_schema("stable")["$defs"])
    assert schema_fetcher.get_widget_key_hierarchy("yasb.notes.NotesWidget") == expected
    assert not schema_fetcher.is_database_valid()


def test_schema_save_failure_preserves_previous_cache(schema_cache, monkeypatch):
    old = database("stable", "before")
    assert schema_fetcher.save_schema_database(old)
    monkeypatch.setattr(file_io.os, "replace", lambda *args: (_ for _ in ()).throw(PermissionError("locked")))
    assert not schema_fetcher.save_schema_database(database("stable", "after"))
    assert schema_fetcher.load_schema_database() == old


def test_download_profile_is_captured_before_user_switches(schema_cache, monkeypatch):
    def download(callback=None, selected=None):
        assert selected == "stable"
        get_preferences().set("yasb_schema_profile", "development")
        return yasb_schema.load_schema("stable")

    monkeypatch.setattr(schema_fetcher, "_download_schema_json", download)
    success, message = schema_fetcher.update_schema_database()
    assert success, message
    assert schema_fetcher.load_schema_database("stable")["_meta"]["profile"] == "stable"
    assert schema_fetcher.load_schema_database("development") == {}


@pytest.fixture
def app_updater(tmp_path, monkeypatch):
    client = updater.AppUpdater()
    client._metadata_path = tmp_path / "updates.json"
    monkeypatch.setattr(client, "is_msix_install", lambda: False)
    monkeypatch.setattr(client, "_get_system_arch", lambda: "x64")
    return client


def release(assets, **extra):
    return {
        "tag_name": "v9.0.0",
        "assets": [{"name": name, "browser_download_url": f"https://example.invalid/{name}"} for name in assets],
        **extra,
    }


def mock_releases(monkeypatch, releases):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(releases).encode()

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *args, **kwargs: Response())


@pytest.mark.parametrize("extension", ["exe", "zip"])
def test_portable_release_is_available(app_updater, monkeypatch, extension):
    name = f"YASB-GUI-9.0.0-x64-portable.{extension}"
    mock_releases(monkeypatch, [release([name])])
    success, message, version, url = app_updater.check_for_update(skip_rate_limit=True)
    assert success, message
    assert version == "9.0.0" and url.endswith(name)
    assert app_updater.get_available_update() == (version, url)
    assert not app_updater.can_install_update(url)


def test_msix_and_portable_choose_their_own_assets(app_updater, monkeypatch):
    bundle = f"YASB.GUI_9.0.0_{updater.APP_ID.split('_')[1]}.msixbundle"
    exe = "YASB-GUI-9.0.0-x64-portable.exe"
    mock_releases(monkeypatch, [release([bundle, "YASB-GUI-9.0.0-x64-portable.zip", exe])])
    assert app_updater.check_for_update(skip_rate_limit=True)[3].endswith(exe)
    monkeypatch.setattr(app_updater, "is_msix_install", lambda: True)
    assert app_updater.get_available_update() is None  # portable cache is incompatible
    url = app_updater.check_for_update(skip_rate_limit=True)[3]
    assert url.endswith(bundle)
    assert app_updater.can_install_update(url)


def test_updater_skips_drafts_and_prereleases(app_updater, monkeypatch):
    exe = "YASB-GUI-9.0.0-x64-portable.exe"
    mock_releases(monkeypatch, [release([], draft=True), release([], prerelease=True), release([exe])])
    assert app_updater.check_for_update(skip_rate_limit=True)[3].endswith(exe)


def test_wrong_architecture_does_not_offer_download(app_updater, monkeypatch):
    mock_releases(monkeypatch, [release(["YASB-GUI-9.0.0-arm64-portable.exe"])])
    success, _, version, url = app_updater.check_for_update(skip_rate_limit=True)
    assert not success and version is None and url is None
    assert app_updater.get_available_update() is None


def test_portable_update_never_launches_appx_installer(app_updater, monkeypatch):
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Unexpected installer launch"))
    success, _ = app_updater.install_update("C:/downloads/update.exe")
    assert not success


def test_msix_install_quotes_literal_paths(app_updater, monkeypatch):
    calls = []
    monkeypatch.setattr(app_updater, "is_msix_install", lambda: True)
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kwargs: calls.append(args))
    success, message = app_updater.install_update("C:/O'Brien/update.msixbundle")
    assert success, message
    assert "-Path 'C:/O''Brien/update.msixbundle'" in calls[0][-1]
    assert "shell:AppsFolder\\" in calls[0][-1]


def test_bundled_schema_startup_still_checks_app_updates(monkeypatch):
    from core import application

    actions = []
    monkeypatch.setattr(application, "IS_EXECUTABLE", True)
    monkeypatch.setattr(yasb_schema, "widget_schemas", lambda: {"test": {}})
    app = SimpleNamespace(
        _widgets_page=SimpleNamespace(reload_registry=lambda: actions.append("registry")),
        _show_initial_content=lambda: actions.append("content"),
        _check_app_updates_background=lambda: actions.append("updates"),
    )
    application.ConfiguratorApp._check_schema_database(app)
    assert actions == ["registry", "content", "updates"]
