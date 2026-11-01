"""Batch commands preserve bar scope, YAML data, and all-or-nothing validation."""

from copy import deepcopy
from io import StringIO

import pytest
from core.config_manager import ConfigManager
from core.widget_helpers import (
    add_widget_to_bar,
    delete_disabled_widget,
    delete_widget,
    disable_widget,
    duplicate_widget,
    enable_widget,
    move_widget,
)
from core.widget_management import apply_widget_action
from ruamel.yaml import YAML


@pytest.fixture
def manager():
    result = object.__new__(ConfigManager)
    result._config = {
        "widgets": {
            "a": {"type": "custom.Widget", "options": {"nested": {"value": 1}}},
            "b": {"type": "custom.Widget", "options": {}},
            "unused": {"type": "custom.Widget", "options": {}},
        },
        "bars": {
            "main": {"widgets": {"left": ["a", "b", "a"], "center": ["a"], "right": []}},
            "other": {"widgets": {"left": ["a"], "center": [], "right": ["b"]}},
        },
    }
    return result


def test_batch_disable_removes_all_references_only_in_current_bar(manager):
    original_widgets = deepcopy(manager.get_widgets())
    other = deepcopy(manager.get_bar("other"))
    assert apply_widget_action(manager, "main", ["a", "a", "unused"], "disable") == ["a"]
    assert manager.get_bar("main")["widgets"] == {"left": ["b"], "center": [], "right": []}
    assert manager.get_bar("other") == other
    assert manager.get_widgets() == original_widgets
    assert apply_widget_action(manager, "main", ["a"], "disable") == []


def test_batch_move_deduplicates_and_enables_in_selection_order(manager):
    other = deepcopy(manager.get_bar("other"))
    assert apply_widget_action(manager, "main", ["unused", "a", "unused"], "move", "right") == ["unused", "a"]
    assert manager.get_bar("main")["widgets"] == {"left": ["b"], "center": [], "right": ["unused", "a"]}
    assert manager.get_bar("other") == other
    assert apply_widget_action(manager, "main", ["unused", "a"], "move", "right") == []


def test_move_into_bar_without_positions_writes_to_actual_config(manager):
    manager.config["bars"]["empty"] = {}
    assert enable_widget(manager, "empty", "a", "left")
    assert manager.get_bar("empty")["widgets"] == {"left": ["a"]}
    assert not enable_widget(manager, "empty", "a", "left")


def test_duplicate_all_occurrences_and_unused_widget(manager):
    manager.get_widgets()["a_1"] = {"type": "custom.Widget", "options": {}}
    other = deepcopy(manager.get_bar("other"))
    assert apply_widget_action(manager, "main", ["a", "unused", "a"], "duplicate") == ["a_2", "unused_1"]
    assert manager.get_bar("main")["widgets"] == {
        "left": ["a", "a_2", "b", "a", "a_2"],
        "center": ["a", "a_2"],
        "right": [],
    }
    assert manager.get_bar("other") == other
    manager.get_widget("a_2")["options"]["nested"]["value"] = 99
    assert manager.get_widget("a")["options"]["nested"]["value"] == 1
    assert manager.get_widget("unused_1") == manager.get_widget("unused")


def test_duplicate_disabled_widget_does_not_create_none_position(manager):
    before = deepcopy(manager.get_bar("main"))
    assert duplicate_widget(manager, "main", "unused", None) == "unused_1"
    assert manager.get_bar("main") == before


def test_duplicate_without_selected_bar_copies_only_definitions(manager):
    before = deepcopy(manager.get_bars())
    assert apply_widget_action(manager, None, ["a", "unused"], "duplicate") == ["a_1", "unused_1"]
    assert duplicate_widget(manager, None, "a", None) == "a_2"
    assert manager.get_bars() == before


def test_duplicate_in_config_without_any_bars(manager):
    del manager.config["bars"]
    assert apply_widget_action(manager, None, ["a"], "duplicate") == ["a_1"]
    assert "bars" not in manager.config
    with pytest.raises(ValueError):
        apply_widget_action(manager, None, ["a"], "move", "left")


@pytest.mark.parametrize("action,position", [("duplicate", None), ("disable", None), ("move", "right")])
def test_invalid_later_selection_has_no_partial_changes(manager, action, position):
    before = deepcopy(manager.config)
    with pytest.raises(ValueError):
        apply_widget_action(manager, "main", ["a", "missing"], action, position)
    assert manager.config == before


@pytest.mark.parametrize(
    "names,action,position",
    [
        ("a", "move", "right"),
        (["a", None], "duplicate", None),
        (["a"], "move", "invalid"),
        (["a"], "delete", None),
        (["a"], "disable", "left"),
    ],
)
def test_invalid_inputs_leave_config_unchanged(manager, names, action, position):
    before = deepcopy(manager.config)
    with pytest.raises(ValueError):
        apply_widget_action(manager, "main", names, action, position)
    assert manager.config == before


@pytest.mark.parametrize("invalid", [None, "a", {"left": ["a"], "right": None}, {"unknown": []}, {"left": [1]}])
def test_invalid_bar_structure_is_rejected_before_mutating(manager, invalid):
    manager.get_bar("main")["widgets"] = invalid
    before = deepcopy(manager.config)
    with pytest.raises(ValueError):
        apply_widget_action(manager, "main", ["a", "b"], "move", "right")
    assert manager.config == before


def test_single_move_rejects_missing_source_and_invalid_destination_without_losing_source(manager):
    before = deepcopy(manager.config)
    assert not move_widget(manager, "main", "b", "center", "right")
    assert manager.config == before
    manager.get_bar("main")["widgets"]["right"] = None
    before = deepcopy(manager.config)
    assert not move_widget(manager, "main", "a", "left", "right")
    assert manager.config == before


def test_single_move_changes_only_first_reference_in_clicked_position(manager):
    assert move_widget(manager, "main", "a", "left", "right")
    assert manager.get_bar("main")["widgets"] == {"left": ["b", "a"], "center": ["a"], "right": ["a"]}
    assert manager.get_bar("other")["widgets"]["left"] == ["a"]


def test_single_move_does_not_duplicate_existing_target_reference(manager):
    manager.get_bar("main")["widgets"]["right"] = ["a"]
    assert move_widget(manager, "main", "a", "left", "right")
    assert manager.get_bar("main")["widgets"] == {"left": ["b", "a"], "center": ["a"], "right": ["a"]}


def test_single_duplicate_changes_only_first_reference_in_clicked_position(manager):
    assert duplicate_widget(manager, "main", "a", "left") == "a_1"
    assert manager.get_bar("main")["widgets"] == {"left": ["a", "a_1", "b", "a"], "center": ["a"], "right": []}
    before = deepcopy(manager.config)
    assert duplicate_widget(manager, "main", "b", "center") is None
    assert manager.config == before


def test_single_disable_changes_only_first_reference_in_clicked_position(manager):
    assert disable_widget(manager, "main", "a", "left")
    assert manager.get_bar("main")["widgets"] == {"left": ["b", "a"], "center": ["a"], "right": []}


@pytest.mark.parametrize("action", ["move", "duplicate", "disable"])
def test_single_commands_isolate_shared_positions_and_whole_bars(manager, action):
    main = manager.get_bar("main")
    main["widgets"]["left"] = main["widgets"]["center"] = ["a"]
    manager.config["bars"]["other"] = main
    other_before = deepcopy(main)
    if action == "move":
        assert move_widget(manager, "main", "a", "left", "right")
        assert manager.get_bar("main")["widgets"]["left"] == []
    elif action == "duplicate":
        assert duplicate_widget(manager, "main", "a", "left") == "a_1"
        assert manager.get_bar("main")["widgets"]["left"] == ["a", "a_1"]
    else:
        assert disable_widget(manager, "main", "a", "left")
        assert manager.get_bar("main")["widgets"]["left"] == []
    assert manager.get_bar("main")["widgets"]["center"] == ["a"]
    assert manager.get_bar("other") == other_before


def test_invalid_single_actions_do_not_report_success_or_create_orphan_copy(manager):
    before = deepcopy(manager.config)
    assert duplicate_widget(manager, "missing", "a", "left") is None
    assert not enable_widget(manager, "main", "missing", "left")
    assert not delete_disabled_widget(manager, "missing")
    assert not delete_widget(manager, "main", "missing", "left")
    assert manager.config == before


def test_batch_changes_do_not_follow_shared_bar_aliases(manager):
    manager.get_bar("other")["widgets"] = manager.get_bar("main")["widgets"]
    other = deepcopy(manager.get_bar("other"))
    apply_widget_action(manager, "main", ["a"], "move", "right")
    assert manager.get_bar("other") == other


def test_batch_changes_do_not_follow_whole_bar_aliases(manager):
    manager.config["bars"]["other"] = manager.get_bar("main")
    other = deepcopy(manager.get_bar("other"))
    apply_widget_action(manager, "main", ["a"], "move", "right")
    assert manager.get_bar("other") == other
    assert manager.get_bar("main")["widgets"]["right"] == ["a"]


@pytest.mark.parametrize("action", ["move", "duplicate"])
def test_shared_position_lists_are_processed_once_each(manager, action):
    positions = manager.get_bar("main")["widgets"]
    positions["left"] = positions["right"] = ["a"]
    if action == "move":
        apply_widget_action(manager, "main", ["a"], action, "right")
        positions = manager.get_bar("main")["widgets"]
        assert positions["left"] == []
        assert positions["right"] == ["a"]
    else:
        apply_widget_action(manager, "main", ["a"], action)
        positions = manager.get_bar("main")["widgets"]
        assert positions["left"] == ["a", "a_1"]
        assert positions["right"] == ["a", "a_1"]


def test_duplicate_preserves_yaml_comments_quotes_and_independent_anchors(manager):
    parser = YAML()
    parser.preserve_quotes = True
    manager._config = parser.load("""widgets:
  a: &widget
    type: custom.Widget
    options:
      label: "quoted" # preserve label note
      nested: &nested {value: 1}
      alias: *nested
  linked: *widget
bars:
  main:
    widgets:
      left: [a]
""")
    assert apply_widget_action(manager, "main", ["a"], "duplicate") == ["a_1"]
    duplicate = manager.get_widget("a_1")
    duplicate["options"]["nested"]["value"] = 2
    assert duplicate["options"]["alias"]["value"] == 2
    assert manager.get_widget("a")["options"]["nested"]["value"] == 1
    stream = StringIO()
    parser.dump(manager.config, stream)
    text = stream.getvalue()
    assert text.count('label: "quoted" # preserve label note') == 2
    restored = parser.load(text)
    assert restored["widgets"]["a_1"]["options"]["nested"]["value"] == 2
    assert restored["widgets"]["linked"]["options"]["nested"]["value"] == 1


def test_adding_widgets_deep_copies_nested_template_defaults(manager):
    template = {"id": "new", "type_path": "custom.Widget", "defaults": {"nested": {"value": 1}}}
    first = add_widget_to_bar(manager, "main", template, "left")
    second = add_widget_to_bar(manager, "main", template, "right")
    manager.get_widget(first)["options"]["nested"]["value"] = 2
    assert manager.get_widget(second)["options"]["nested"]["value"] == 1
    assert template["defaults"]["nested"]["value"] == 1
