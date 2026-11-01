"""Exercise widget management in a hidden, isolated real WinUI window.

Run directly on Windows with the matching Windows App Runtime installed.
No user configuration is loaded or saved and no update checks are started.
"""

# ruff: noqa: E402
import copy
import os
import sys
import time
import traceback
from datetime import timedelta
from pathlib import Path

root = Path(__file__).resolve().parents[1]
case = root / "work" / "native-widgets-smoke"
os.environ["APPDATA"] = str(case / "profile")
os.environ["YASB_CONFIG_HOME"] = str(case / "config")
os.environ["TEMP"] = str(case / "temp")
Path(os.environ["TEMP"]).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / "app"))

from core.application import ConfiguratorApp
from core.localization import t
from core.preferences import get_preferences
from winui3.microsoft.ui.xaml import Application, DispatcherTimer, ElementTheme, FrameworkElement, Visibility, Window
from winui3.microsoft.ui.xaml.automation.peers import (
    AppBarButtonAutomationPeer,
    CheckBoxAutomationPeer,
    MenuFlyoutItemAutomationPeer,
)
from winui3.microsoft.ui.xaml.controls import (
    Button,
    ComboBox,
    ContentControl,
    MenuFlyout,
    MenuFlyoutItem,
    Page,
    XamlControlsResources,
)
from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import InitializeOptions, initialize


class Smoke(ConfiguratorApp):
    def _on_launched(self, args):
        try:
            self.resources.merged_dictionaries.append(XamlControlsResources())
            get_preferences().set("ui_animations", False)
            self._config_manager.config.update(
                {
                    "widgets": {
                        "clock": {"type": "yasb.clock.ClockWidget", "options": {"label": "{HH}:{mm}"}},
                        "status": {"type": "custom.StatusWidget", "options": {}},
                        "inactive": {"type": "custom.InactiveWidget", "options": {}},
                    },
                    "bars": {
                        "other": {"widgets": {"left": ["clock"], "center": [], "right": []}},
                        "main": {"widgets": {"left": ["clock", "status"], "center": ["clock"], "right": []}},
                    },
                }
            )
            self.other_bar = copy.deepcopy(self._config_manager.get_bar("other"))
            self._widgets_selected_bar = "main"
            self.dirty_count = 0
            self._window = Window()
            self._window.title = "YASB GUI widget management smoke"
            self._content_area = ContentControl()
            self._window.content = self._content_area
            self._window.activate()
            self._window.app_window.hide()
            self.steps = iter(self.verify())
            self.deadline = time.monotonic() + 20
            self.timer = DispatcherTimer()
            self.timer.interval = timedelta(milliseconds=100)
            self.timer.add_tick(self.tick)
            self.timer.start()
        except Exception:
            self.finish(traceback.format_exc())

    def mark_unsaved(self, *args, **kwargs):
        self.dirty_count += 1

    def tick(self, sender, args):
        try:
            if time.monotonic() > self.deadline:
                raise TimeoutError("Native widget checks exceeded 20 seconds")
            next(self.steps)
        except StopIteration:
            self.finish(
                "PASS: real WinUI XAML, local search without row rebuild, checkbox synchronization, "
                "visible selection, batch duplicate/move/disable, bar scope and selection retention, "
                "disabled copy, no-bar management, light/dark themes and narrow command overflow"
            )
        except Exception:
            self.finish(traceback.format_exc())

    def finish(self, message):
        self.success = message.startswith("PASS:")
        print(message, flush=True)
        (case / "result.txt").write_text(message, encoding="utf-8")
        if hasattr(self, "timer"):
            self.timer.stop()
        if self._window:
            self._window.close()
        self.exit()

    def invoke(self, action):
        button = self._widgets_page._batch_buttons[action]
        assert button.is_enabled, action
        AppBarButtonAutomationPeer(button).invoke()

    def verify(self):
        page = self._widgets_page
        page.show()
        yield
        assert self._content_area.content is not None, "WidgetsPage.show did not load XAML"
        assert self._widgets_selected_bar == "main"
        assert len(page._widget_rows) == 4
        assert page._visible_widget_names == ["clock", "status", "inactive"]
        original_rows = [row for _, row, _, _ in page._widget_rows]

        page._filter_input.text = "CLOCK"
        yield
        assert page._visible_widget_names == ["clock"]
        assert [row for _, row, _, _ in page._widget_rows] == original_rows
        assert len(page._selection_boxes["clock"]) == 2
        CheckBoxAutomationPeer(page._selection_boxes["clock"][0]).toggle()
        yield
        assert page._selected_widgets == {"clock"}
        assert all(box.is_checked for box in page._selection_boxes["clock"])
        self.invoke("clear")
        yield
        assert not page._selected_widgets
        assert not any(box.is_checked for box in page._selection_boxes["clock"])

        self.invoke("select")
        yield
        assert page._selected_widgets == {"clock"}
        self.invoke("duplicate")
        yield
        assert self.dirty_count == 1
        positions = self._config_manager.get_bar("main")["widgets"]
        assert positions["left"] == ["clock", "clock_1", "status"]
        assert positions["center"] == ["clock", "clock_1"]
        assert self._config_manager.get_bar("other") == self.other_bar
        assert not page._selected_widgets and page._batch_status.is_open

        page._filter_input.text = "clock_1"
        yield
        self.invoke("select")
        yield
        move_menu = page._batch_buttons["move"].flyout.as_(MenuFlyout)
        right_item = move_menu.items.get_at(2).as_(MenuFlyoutItem)
        assert right_item.text == t("widgets_right")
        MenuFlyoutItemAutomationPeer(right_item).invoke()
        yield
        positions = self._config_manager.get_bar("main")["widgets"]
        assert positions["left"] == ["clock", "status"]
        assert positions["center"] == ["clock"]
        assert positions["right"] == ["clock_1"]
        assert self.dirty_count == 2

        self.invoke("select")
        yield
        self.invoke("disable")
        yield
        positions = self._config_manager.get_bar("main")["widgets"]
        assert all("clock_1" not in names for names in positions.values())
        assert self._config_manager.get_widget("clock_1") is not None
        assert self.dirty_count == 3
        assert not page._batch_buttons["disable"].is_enabled
        assert self._config_manager.get_bar("other") == self.other_bar

        page._filter_input.text = "inactive"
        yield
        row = next(row for name, row, _, _ in page._widget_rows if name == "inactive")
        menu = row.find_name("MainButton").as_(Button).context_flyout.as_(MenuFlyout)
        duplicate_item = None
        for candidate in menu.items:
            try:
                item = candidate.as_(MenuFlyoutItem)
            except OSError:
                continue  # MenuFlyoutSeparator does not implement this interface.
            if item.text == t("widgets_duplicate"):
                duplicate_item = item
                break
        assert duplicate_item is not None, "Disabled widget copy menu is missing"
        MenuFlyoutItemAutomationPeer(duplicate_item).invoke()
        yield
        assert self._config_manager.get_widget("inactive_1") is not None
        assert all("inactive_1" not in names for names in self._config_manager.get_bar("main")["widgets"].values())
        assert self.dirty_count == 4

        page._filter_input.text = ""
        yield
        self.invoke("select")
        yield
        content = self._content_area.content.as_(Page).content.as_(FrameworkElement)
        selector = content.find_name("BarSelector").as_(ComboBox)
        selector.selected_index = 0
        yield
        assert self._widgets_selected_bar == "other"
        assert not page._selected_widgets
        page.show()
        yield
        assert self._widgets_selected_bar == "other"
        assert not page._selected_widgets

        self._config_manager.config["bars"] = {}
        page.show()
        yield
        assert self._widgets_selected_bar is None
        assert len(page._visible_widget_names) == 5
        assert all(position == "disabled" for _, _, _, position in page._widget_rows)
        assert all(
            page._section_expanders[position].visibility == Visibility.COLLAPSED
            for position in ("left", "center", "right")
        )
        for _, row, _, _ in page._widget_rows:
            menu = row.find_name("MainButton").as_(Button).context_flyout.as_(MenuFlyout)
            assert all(not menu.items.get_at(index).as_(MenuFlyoutItem).is_enabled for index in range(3))
        page._filter_input.text = "status"
        yield
        self.invoke("select")
        yield
        assert not page._batch_buttons["move"].is_enabled
        assert not page._batch_buttons["disable"].is_enabled
        self.invoke("duplicate")
        yield
        assert self._config_manager.get_widget("status_1") is not None
        assert self._config_manager.get_bars() == {}
        assert self.dirty_count == 5

        # Approximate the page space left by a 960px app window plus its sidebar.
        self._content_area.width = 640
        for theme in (ElementTheme.LIGHT, ElementTheme.DARK):
            self._content_area.requested_theme = theme
            self._content_area.update_layout()
            yield
            native_page = self._content_area.content.as_(Page)
            assert native_page.actual_theme == theme
            assert native_page.actual_width > 0
            assert any(button.is_in_overflow for button in page._batch_buttons.values())
            assert all(button.label for button in page._batch_buttons.values())


def init(args):
    global instance
    instance = Smoke()


try:
    with initialize(options=InitializeOptions(0)):
        Application.start(init)
    sys.exit(0 if instance.success else 1)
except Exception:
    result = traceback.format_exc()
    print(result, flush=True)
    (case / "result.txt").write_text(result, encoding="utf-8")
    sys.exit(1)
