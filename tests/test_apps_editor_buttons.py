"""Exercise every application editor button handler with isolated controls."""

import copy
from types import SimpleNamespace

import pytest
from core.apps_editor import APPS_TYPE
from core.localization import t
from core.yasb_schema import make_defaults, widget_schemas
from ui import apps_editor, command_presets
from winui3.microsoft.ui.xaml.controls import ContentDialogButton


class Children(list):
    def append(self, value):
        super().append(value)

    def insert_at(self, index, value):
        self.insert(index, value)


class Control:
    def __init__(self, text=""):
        self.children = Children()
        self.text = text
        self.is_enabled = True
        self.selected_index = 0

    def add_click(self, callback):
        self.clicked = callback

    def add_selection_changed(self, callback):
        self.selected = callback

    def click(self):
        assert self.is_enabled
        self.clicked(self, None)


class Factory:
    escape_xml = staticmethod(lambda value: value)

    def create_stack_panel(self, **kwargs):
        return Control()

    def create_text_block(self, text, **kwargs):
        return Control(text)

    def create_button(self, text):
        return Control(text)

    def create_combobox(self, *args):
        return Control()


@pytest.fixture
def editor(monkeypatch):
    monkeypatch.setattr(apps_editor, "UIFactory", Factory)
    monkeypatch.setattr(command_presets, "UIFactory", Factory)
    monkeypatch.setattr(apps_editor, "TextBox", Control)
    monkeypatch.setattr(apps_editor, "ScrollViewer", Control)
    dialog = Control()
    dialog.add_closing = lambda callback: setattr(dialog, "closing", callback)
    dialog.add_closed = lambda callback: setattr(dialog, "closed", callback)
    dialog.show_async = lambda: None
    applied, dirty, refresh = [], [], []
    app = SimpleNamespace(create_dialog=lambda xaml: dialog, mark_unsaved=lambda: dirty.append(True))
    original = make_defaults(widget_schemas()[APPS_TYPE])
    original["app_list"] = [
        {"name": "A", "icon": "A", "launch": "a.exe"},
        {"name": "B", "icon": "B", "launch": "b.exe"},
    ]
    snapshot = copy.deepcopy(original)
    apps_editor.show_apps_editor(app, original, applied.append, lambda: refresh.append(True))
    return SimpleNamespace(
        dialog=dialog,
        original=original,
        snapshot=snapshot,
        applied=applied,
        dirty=dirty,
        refresh=refresh,
        body=dialog.content,
        rows=dialog.content.children[4].content,
    )


def apply(editor):
    args = SimpleNamespace(result=ContentDialogButton.PRIMARY, cancel=False)
    editor.dialog.closing(None, args)
    return args


def test_up_down_delete_preserve_unsaved_fields_and_boundaries(editor):
    first, second = editor.rows.children
    assert not first.children[4].children[1].is_enabled
    assert not second.children[4].children[2].is_enabled
    first.children[1].text = "Edited A"
    first.children[4].children[2].click()  # Down
    assert editor.rows.children[1].children[1].text == "Edited A"
    editor.rows.children[1].children[4].children[1].click()  # Up
    editor.rows.children[1].children[4].children[3].click()  # Delete B
    assert not apply(editor).cancel
    assert [item["name"] for item in editor.applied[0]["app_list"]] == ["Edited A"]
    assert editor.original == editor.snapshot


def test_icon_selection_and_cancel(editor, monkeypatch):
    monkeypatch.setattr(apps_editor, "pick_files", lambda **kwargs: ["C:\\图片\\a.png"])
    editor.rows.children[0].children[4].children[0].click()
    assert editor.rows.children[0].children[2].text == "C:\\图片\\a.png"
    monkeypatch.setattr(apps_editor, "pick_files", lambda **kwargs: [])
    editor.rows.children[0].children[4].children[0].click()
    assert editor.rows.children[0].children[2].text == "C:\\图片\\a.png"
    editor.dialog.closing(None, SimpleNamespace(result=ContentDialogButton.NONE, cancel=False))
    assert not editor.applied and not editor.dirty and editor.original == editor.snapshot


def test_browse_multiselect_and_duplicate_use_current_draft(editor, monkeypatch, tmp_path):
    path = tmp_path / "new.exe"
    path.touch()
    from core.apps_editor import application_entry

    editor.rows.children[0].children[3].text = application_entry(path)["launch"]
    monkeypatch.setattr(apps_editor, "pick_files", lambda: [str(path), str(path)])
    editor.body.children[1].click()
    assert len(editor.rows.children) == 2  # Existing edited command matches; do not append.
    editor.rows.children[0].children[3].text = "custom.exe"
    editor.body.children[1].click()
    assert len(editor.rows.children) == 3
    assert not apply(editor).cancel


def test_preset_requires_explicit_apply_then_adds_command(editor):
    combo, button = editor.body.children[2].children
    assert not button.is_enabled
    combo.selected_index = 1
    combo.selected(combo, None)
    assert len(editor.rows.children) == 2
    button.click()
    assert len(editor.rows.children) == 3
    assert not apply(editor).cancel
    assert editor.applied[-1]["app_list"][-1]["launch"].startswith("powershell.exe ")


def test_manual_command_button_validates_before_apply(editor):
    editor.body.children[3].click()
    assert apply(editor).cancel and not editor.applied
    editor.rows.children[-1].children[3].text = "notepad.exe"
    assert not apply(editor).cancel
    editor.dialog.closed(None, SimpleNamespace(result=ContentDialogButton.PRIMARY))
    assert editor.refresh == [True] and editor.dirty == [True]


def test_browse_errors_keep_list_and_report_failure(editor, monkeypatch):
    def fail():
        raise OSError("picker unavailable")

    monkeypatch.setattr(apps_editor, "pick_files", fail)
    editor.body.children[1].click()
    assert len(editor.rows.children) == 2
    assert "picker unavailable" in editor.body.children[-1].text


def test_all_buttons_have_handlers(editor):
    for index in (1, 3):
        assert callable(editor.body.children[index].clicked)
    assert callable(editor.body.children[2].children[1].clicked)
    for row in editor.rows.children:
        assert all(callable(button.clicked) for button in row.children[4].children)
    assert editor.body.children[3].text == t("apps_add_command")
