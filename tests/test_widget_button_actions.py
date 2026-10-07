"""Widget menu actions update configuration, dirty state and refresh together."""

import copy
from types import SimpleNamespace

import pytest
from core.config_manager import ConfigManager
from pages.widgets import WidgetsPage


@pytest.fixture
def page(tmp_path, monkeypatch):
    monkeypatch.setenv("YASB_CONFIG_HOME", str(tmp_path))
    manager = ConfigManager()
    manager.config.update(
        {
            "widgets": {
                "a": {"type": "custom.Widget", "options": {"nested": {"value": 1}}},
                "b": {"type": "custom.Widget", "options": {}},
            },
            "bars": {
                "main": {"widgets": {"left": ["a", "b"], "center": [], "right": []}},
                "other": {"widgets": {"left": [], "center": ["a"], "right": []}},
            },
        }
    )
    instance = object.__new__(WidgetsPage)
    instance._config_manager = manager
    instance.changed, instance.refreshed = [], []
    instance._app = SimpleNamespace(_widgets_selected_bar="main", mark_unsaved=lambda: instance.changed.append(True))
    instance._load_widgets = lambda: instance.refreshed.append(True)
    return instance


def test_up_down_and_disabled_boundaries(page):
    page._move_widget_order("a", "left", -1)
    assert not page.changed
    page._move_widget_order("a", "left", 1)
    assert page._config_manager.get_bar("main")["widgets"]["left"] == ["b", "a"]
    page._move_widget_order("a", "left", -1)
    assert page._config_manager.get_bar("main")["widgets"]["left"] == ["a", "b"]
    assert len(page.changed) == len(page.refreshed) == 2


def test_move_position(page):
    page._move_widget("a", "left", "right")
    positions = page._config_manager.get_bar("main")["widgets"]
    assert positions["left"] == ["b"] and positions["right"] == ["a"]
    assert page.changed and page.refreshed


def test_repeated_reorder_clicks_apply_immediately(page):
    page._animate_and_move_widget("a", "left", 1, 0)
    assert page._config_manager.get_bar("main")["widgets"]["left"] == ["b", "a"]
    assert len(page.changed) == len(page.refreshed) == 1
    page._animate_and_move_widget("a", "left", -1, 1)
    assert page._config_manager.get_bar("main")["widgets"]["left"] == ["a", "b"]
    assert len(page.changed) == len(page.refreshed) == 2
    page._animate_and_move_widget("a", "left", -1, 0)
    assert len(page.changed) == len(page.refreshed) == 2


def test_duplicate_has_independent_options(page):
    page._duplicate_widget("a", "left")
    assert page._config_manager.get_bar("main")["widgets"]["left"] == ["a", "a_1", "b"]
    duplicate = page._config_manager.get_widget("a_1")
    duplicate["options"]["nested"]["value"] = 2
    assert page._config_manager.get_widget("a")["options"]["nested"]["value"] == 1
    assert page.changed and page.refreshed


def test_disable_and_enable_keep_options(page):
    original = copy.deepcopy(page._config_manager.get_widget("a"))
    page._disable_widget("a", "left")
    assert page._config_manager.get_widget("a") == original
    assert "a" not in page._config_manager.get_bar("main")["widgets"]["left"]
    page._enable_widget("a", "center")
    assert page._config_manager.get_bar("main")["widgets"]["center"] == ["a"]
    assert len(page.changed) == len(page.refreshed) == 2


@pytest.mark.parametrize("disabled", [False, True])
def test_delete_removes_references_from_all_bars(page, disabled):
    if disabled:
        page._disable_widget("a", "left")
        page._delete_disabled_widget("a")
    else:
        page._delete_widget("a", "left")
    assert page._config_manager.get_widget("a") is None
    for bar in page._config_manager.get_bars().values():
        assert all("a" not in names for names in bar["widgets"].values())
    assert page.changed and page.refreshed


def test_rename_updates_all_references_and_rejects_duplicate(page):
    manager = page._config_manager
    assert not manager.rename_widget("a", "b")
    assert manager.rename_widget("a", "renamed")
    assert manager.get_widget("a") is None and manager.get_widget("renamed")
    assert manager.get_bar("main")["widgets"]["left"] == ["renamed", "b"]
    assert manager.get_bar("other")["widgets"]["center"] == ["renamed"]
