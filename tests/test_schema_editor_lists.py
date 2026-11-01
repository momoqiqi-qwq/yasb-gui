"""Regression tests for list editing helpers exposed by the schema form."""

import copy

from core.yasb_schema import errors_for, make_defaults, widget_schemas


def test_object_list_defaults_are_valid_for_button_like_entries():
    node = widget_schemas()["yasb.applications.ApplicationsWidget"]
    options = make_defaults(node)
    options["app_list"] = [{"icon": "", "launch": "floorp.exe -P work", "name": "Work"}]
    assert errors_for(options, node) == []


def test_list_drafts_can_be_reordered_or_removed_without_mutating_original():
    original = {"actions": [{"id": "work"}, {"id": "personal"}]}
    draft = copy.deepcopy(original)
    draft["actions"][0], draft["actions"][1] = draft["actions"][1], draft["actions"][0]
    draft["actions"].pop()
    assert original["actions"] == [{"id": "work"}, {"id": "personal"}]
    assert draft["actions"] == [{"id": "personal"}]
