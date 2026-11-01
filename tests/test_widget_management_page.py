"""Widget management interactions with isolated configuration and eventful controls."""

import copy
from types import SimpleNamespace

import pytest
from core.config_manager import ConfigManager
from core.localization import t
from pages import widgets
from winui3.microsoft.ui.xaml import Visibility
from winui3.microsoft.ui.xaml.controls import InfoBarSeverity


class Items(list):
    @property
    def size(self):
        return len(self)


class Control:
    def __init__(self, text=""):
        self.children = Items()
        self.items = Items()
        self._text = text
        self._selected_index = -1
        self._checked = False
        self.is_enabled = True
        self.is_open = False
        self.is_expanded = False
        self.visibility = Visibility.VISIBLE
        self.names = {}
        self.check_events = 0

    def as_(self, kind):
        return self

    def find_name(self, name):
        return self.names[name]

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        changed = value != self._text
        self._text = value
        if changed and hasattr(self, "text_changed"):
            self.text_changed(self, None)

    @property
    def selected_index(self):
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value):
        changed = value != self._selected_index
        self._selected_index = value
        if changed and hasattr(self, "selection_changed"):
            self.selection_changed(self, None)

    @property
    def is_checked(self):
        return self._checked

    @is_checked.setter
    def is_checked(self, value):
        changed = value != self._checked
        self._checked = value
        if changed and hasattr(self, "checked_changed"):
            self.check_events += 1
            self.checked_changed(value)

    def add_click(self, callback):
        self.clicked = callback

    def add_text_changed(self, callback):
        self.text_changed = callback

    def add_selection_changed(self, callback):
        self.selection_changed = callback


@pytest.fixture
def page(tmp_path, monkeypatch):
    monkeypatch.setenv("YASB_CONFIG_HOME", str(tmp_path))
    manager = ConfigManager()
    manager.config.update(
        {
            "widgets": {
                "clock_main": {"type": "yasb.clock.ClockWidget", "options": {"label": "time"}},
                "shared": {"type": "yasb.clock.ClockWidget", "options": {}},
                "cpu": {"type": "yasb.cpu.CpuWidget", "options": {}},
                "spare": {"type": "custom.Widget", "options": {}},
            },
            "bars": {
                "main": {"widgets": {"left": ["clock_main", "shared"], "center": ["shared"], "right": ["cpu"]}},
                "other": {"widgets": {"left": ["spare"], "center": [], "right": []}},
            },
        }
    )
    instance = object.__new__(widgets.WidgetsPage)
    instance._config_manager = manager
    instance.changed = []
    instance.created_rows = []
    instance._app = SimpleNamespace(
        _widgets_selected_bar="main",
        mark_unsaved=lambda: instance.changed.append(True),
        _content_area=Control(),
    )
    instance._ui = SimpleNamespace(
        create_text_block=lambda text, style: Control(text),
        create_combobox_item=lambda text: Control(text),
    )
    instance._widget_registry = {
        "yasb.clock.ClockWidget": SimpleNamespace(name="时钟", category="系统"),
        "yasb.cpu.CpuWidget": SimpleNamespace(name="处理器", category="硬件"),
    }
    instance._search_query = ""
    instance._selected_widgets = set()
    instance._visible_widget_names = []
    instance._widget_rows = []
    instance._selection_boxes = {}
    instance._syncing_selection = False
    instance._empty_labels = {}
    instance._filter_input = Control()
    instance._filter_count = Control()
    instance._selection_count = Control()
    instance._batch_status = Control()
    instance._batch_buttons = {name: Control() for name in ("select", "clear", "duplicate", "disable", "move")}

    def create_sections():
        instance._widget_panels = {position: Control() for position in ("left", "center", "right")}
        instance._section_expanders = {position: Control() for position in ("left", "center", "right", "disabled")}
        instance._disabled_widgets_panel = Control()

    def create_item(name, position, index, total):
        row, checkbox = Control(), Control()
        checkbox.checked_changed = lambda checked: instance._set_widget_selected(name, checked)
        instance._selection_boxes.setdefault(name, []).append(checkbox)
        instance.created_rows.append((name, position, index, total, row))
        return row

    instance._create_sections = create_sections
    instance._create_widget_item = create_item
    create_sections()
    instance._load_widgets()
    assert len(instance._widget_rows) == 5
    return instance


def filter_to(page, query):
    page._filter_input.text = query
    page._on_filter_changed()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("时钟", ["clock_main", "shared"]),
        ("CLOCKWIDGET", ["clock_main", "shared"]),
        ("  系统\tCLOCK  ", ["clock_main", "shared"]),
        ("clock_MAIN 时钟", ["clock_main"]),
        ("硬件 CPU", ["cpu"]),
        ("custom.widget spare", ["spare"]),
        ("时钟 硬件", []),
        (" \t ", ["clock_main", "shared", "cpu", "spare"]),
    ],
)
def test_filter_matches_all_terms_and_reuses_rows(page, query, expected):
    rows = list(page._widget_rows)
    config = copy.deepcopy(page._config_manager.config)
    created = len(page.created_rows)
    filter_to(page, query)
    assert page._visible_widget_names == expected
    assert len(page.created_rows) == created
    assert page._widget_rows == rows
    for name, row, *_ in rows:
        assert row.visibility == (Visibility.VISIBLE if name in expected else Visibility.COLLAPSED)
    assert page._filter_count.text == t("widgets_filter_count", visible=len(expected), total=4)
    assert page._config_manager.config == config
    assert not page.changed


def test_filter_clears_selection_and_select_all_only_selects_visible_names(page):
    page._select_visible_widgets()
    assert page._selected_widgets == {"clock_main", "shared", "cpu", "spare"}
    filter_to(page, "时钟")
    assert not page._selected_widgets
    assert all(not box.is_checked for boxes in page._selection_boxes.values() for box in boxes)
    page._select_visible_widgets()
    assert page._selected_widgets == {"clock_main", "shared"}
    assert page._selection_count.text == t("widgets_selected_count", count=2)
    assert page._batch_buttons["duplicate"].is_enabled
    assert page._batch_buttons["disable"].is_enabled
    filter_to(page, "unmatched")
    assert not page._selected_widgets
    assert not page._batch_buttons["select"].is_enabled
    assert not page._batch_buttons["duplicate"].is_enabled
    for label, _ in page._empty_labels.values():
        assert label.visibility == Visibility.VISIBLE
        assert label.text == t("widgets_filter_empty")


def test_duplicate_references_share_selection_without_recursive_events(page):
    first, second = page._selection_boxes["shared"]
    first.is_checked = True
    assert first.is_checked and second.is_checked
    assert page._selected_widgets == {"shared"}
    assert page._selection_count.text == t("widgets_selected_count", count=1)
    second.is_checked = False
    assert not first.is_checked and not second.is_checked
    assert not page._selected_widgets
    assert first.check_events == second.check_events == 2
    assert not page._syncing_selection


def test_batch_calls_core_once_and_marks_and_refreshes_once(page, monkeypatch):
    filter_to(page, "时钟")
    page._select_visible_widgets()
    calls, refreshed = [], []

    def apply(manager, bar_name, names, action, position):
        calls.append((manager, bar_name, names, action, position))
        return names

    monkeypatch.setattr(widgets, "apply_widget_action", apply)
    page._load_widgets = lambda: refreshed.append(True)
    page._apply_batch_action("move", "right")
    assert calls == [(page._config_manager, "main", ["clock_main", "shared"], "move", "right")]
    assert page.changed == refreshed == [True]
    assert not page._selected_widgets
    assert page._batch_status.is_open
    assert page._batch_status.severity == InfoBarSeverity.SUCCESS
    assert page._batch_status.message == t("widgets_batch_done", count=2)


@pytest.mark.parametrize("failed", [False, True])
def test_noop_or_invalid_batch_preserves_selection_without_dirty_state(page, monkeypatch, failed):
    page._set_widget_selected("spare", True)
    refreshed = []
    before = copy.deepcopy(page._config_manager.config)

    def apply(*args):
        if failed:
            raise ValueError("Invalid target")
        return []

    monkeypatch.setattr(widgets, "apply_widget_action", apply)
    page._load_widgets = lambda: refreshed.append(True)
    page._apply_batch_action("disable")
    assert not page.changed and not refreshed
    assert page._selected_widgets == {"spare"}
    assert page._config_manager.config == before
    assert page._batch_status.is_open
    expected = InfoBarSeverity.ERROR if failed else InfoBarSeverity.INFORMATIONAL
    assert page._batch_status.severity == expected
    assert page._batch_status.message == (
        t("widgets_batch_error", error="Invalid target") if failed else t("widgets_batch_no_change")
    )


def test_empty_selection_never_calls_core(page, monkeypatch):
    def unexpected(*args):
        pytest.fail("An empty selection must not invoke a batch")

    monkeypatch.setattr(widgets, "apply_widget_action", unexpected)
    page._apply_batch_action("duplicate")
    assert not page.changed and not page._batch_status.is_open


def test_no_bar_keeps_definitions_visible_and_allows_duplicate_only(page):
    page._config_manager.config["bars"] = {}
    page._app._widgets_selected_bar = None
    page._load_widgets()
    assert page._visible_widget_names == ["clock_main", "shared", "cpu", "spare"]
    assert all(position == "disabled" for _, _, _, position in page._widget_rows)
    assert all(page._section_expanders[pos].visibility == Visibility.COLLAPSED for pos in ("left", "center", "right"))
    page._set_widget_selected("clock_main", True)
    assert page._batch_buttons["duplicate"].is_enabled
    assert not page._batch_buttons["move"].is_enabled
    assert not page._batch_buttons["disable"].is_enabled
    page._apply_batch_action("duplicate")
    assert page._config_manager.get_widget("clock_main_1") == page._config_manager.get_widget("clock_main")
    assert page.changed == [True]
    assert page._config_manager.get_bars() == {}


@pytest.mark.parametrize(("previous", "expected"), [("other", "other"), ("deleted", "main"), (None, "main")])
def test_show_restores_existing_bar_and_loads_once(page, monkeypatch, previous, expected):
    content = Control()
    names = (
        "PageTitle",
        "SelectBarLabel",
        "BarSelector",
        "AddWidgetButton",
        "AddWidgetText",
        "SectionsPanel",
        "WidgetFilter",
        "FilterCount",
        "SelectionCount",
        "BatchStatus",
        "SelectVisibleButton",
        "ClearSelectionButton",
        "BatchDuplicateButton",
        "BatchDisableButton",
        "BatchMoveButton",
        "BatchHint",
    )
    content.names = {name: Control() for name in names}
    native_page = Control()
    native_page.content = content
    monkeypatch.setattr(widgets, "XamlReader", SimpleNamespace(load=lambda xaml: native_page))
    page._setup_widget_data = lambda: None
    page._setup_batch_controls = lambda: None
    refreshed = []
    page._load_widgets = lambda: refreshed.append(page._app._widgets_selected_bar)
    page._app._widgets_selected_bar = previous
    page._search_query = "时钟"
    page.show()
    assert page._app._content_area.content is native_page
    assert page._app._widgets_selected_bar == expected
    assert refreshed == [expected]
    assert content.names["WidgetFilter"].text == "时钟"
    page._selected_widgets = {"shared"}
    page._batch_status.is_open = True
    next_bar = "main" if expected == "other" else "other"
    content.names["BarSelector"].selected_index = 0 if next_bar == "main" else 1
    assert refreshed == [expected, next_bar]
    assert page._app._widgets_selected_bar == next_bar
    assert not page._selected_widgets
    assert not page._batch_status.is_open
