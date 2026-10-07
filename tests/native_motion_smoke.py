"""Actual WinUI animation clocks and lifetime checks using an isolated profile."""

# ruff: noqa: E402
import os
import sys
import traceback
from datetime import timedelta
from pathlib import Path

root = Path.cwd()
os.environ["APPDATA"] = str(root / "work/motion-smoke-profile")
os.environ["YASB_CONFIG_HOME"] = str(root / "work/motion-smoke-config")
Path(os.environ["YASB_CONFIG_HOME"]).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / "app"))
from core.application import ConfiguratorApp
from core.preferences import get_preferences
from ui import motion
from ui.controls import UIFactory
from winui3.microsoft.ui.xaml import Application, DispatcherTimer, Window
from winui3.microsoft.ui.xaml.automation.peers import ButtonAutomationPeer
from winui3.microsoft.ui.xaml.controls import Button, ComboBox, ContentControl, Grid, StackPanel, XamlControlsResources
from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import InitializeOptions, initialize


class Smoke(ConfiguratorApp):
    def _on_launched(self, args):
        try:
            self.resources.merged_dictionaries.append(XamlControlsResources())
            get_preferences().set("ui_animations", True)
            self.system_setting = motion.system_animations_enabled()
            motion.system_animations_enabled = lambda: True
            self._window = Window()
            self._content_area = ContentControl()
            self._window.content = self._content_area
            self.panel = StackPanel()
            self.button = UIFactory.create_button("Press")
            self.button.name = "plain"
            self.card = motion.instrument_button(Button(), card=True)
            self.card.name = "card"
            self.card.content = UIFactory.create_text_block("Widget card")
            self.panel.children.append(self.button)
            self.panel.children.append(self.card)
            self._content_area.content = self.panel
            self._window.activate()
            self._window.app_window.hide()
            self.steps = iter(self.verify())
            self.timer = DispatcherTimer()
            self.timer.interval = timedelta(milliseconds=100)
            self.timer.add_tick(self.tick)
            self.timer.start()
        except Exception:
            self.finish(traceback.format_exc())

    def tick(self, s, e):
        try:
            next(self.steps)
        except StopIteration:
            self.finish(
                "PASS: real WinUI scale/opacity/translation clocks, immediate clicks, rapid transitions, disable reset, Windows/app reduced motion, unload/reload cleanup"
            )
        except Exception:
            self.finish(traceback.format_exc())

    def finish(self, message):
        self.success = message.startswith("PASS:")
        print(message, flush=True)
        (root / "work/motion-smoke-result.txt").write_text(message, encoding="utf-8")
        if hasattr(self, "timer"):
            self.timer.stop()
        if hasattr(self, "_window"):
            self._window.close()
        self.exit()

    def states(self):
        return {state.control.name: state for state in motion._active if isinstance(state, motion._ButtonMotion)}

    def verify(self):
        yield
        states = self.states()
        assert set(states) == {"plain", "card"}, (set(states), self.button.render_transform)
        plain, card = states["plain"], states["card"]
        plain.animate(0.97, 80)
        yield
        yield
        assert abs(plain.transform.scale_x - 0.97) < 0.0001, plain.transform.scale_x
        clicks = []
        self.button.add_click(lambda s, e: clicks.append(True))
        ButtonAutomationPeer(self.button).invoke()
        ButtonAutomationPeer(self.button).invoke()
        assert len(clicks) == 2
        self.button.is_enabled = False
        assert plain.transform.scale_x == 1 and plain.storyboard is None
        self.button.is_enabled = True
        card.animate(1.008, 200)
        yield
        yield
        yield
        assert abs(card.transform.scale_x - 1.008) < 0.0001, card.transform.scale_x
        navigation = motion.PageMotion(self._content_area)
        navigation.play()
        yield
        assert 0 < self._content_area.opacity < 1, self._content_area.opacity
        assert 0 < navigation.transform.y < 12, navigation.transform.y
        navigation.play()
        navigation.play()
        yield
        yield
        yield
        assert self._content_area.opacity == 1 and navigation.transform.y == 0
        setting = self._app_settings_page._preference_card(
            "ui_animations", [(True, "setting_on"), (False, "setting_off")]
        )
        self.panel.children.append(setting)
        selector = (
            setting.child.as_(Grid).find_name("ControlContainer").as_(StackPanel).children.get_at(0).as_(ComboBox)
        )
        assert selector.selected_index == 0
        selector.selected_index = 1
        yield
        assert get_preferences().get("ui_animations") is False
        assert card.transform.scale_x == 1
        plain.animate(0.97, 80)
        navigation.play()
        assert plain.storyboard is None and navigation.storyboard is None
        selector.selected_index = 0
        yield
        assert get_preferences().get("ui_animations") is True
        motion.system_animations_enabled = lambda: False
        plain.animate(0.97, 80)
        navigation.play()
        assert plain.transform.scale_x == 1 and plain.storyboard is None and navigation.storyboard is None
        motion.system_animations_enabled = lambda: True
        self._content_area.content = StackPanel()
        yield
        assert not self.states(), self.states()
        assert motion._has_identity_transform(self.button) and motion._has_identity_transform(self.card)
        self._content_area.content = self.panel
        yield
        assert set(self.states()) == {"plain", "card"}
        assert self.states()["plain"] is not plain
        self._content_area.content = StackPanel()
        yield
        assert not self.states()


def init(args):
    global instance
    instance = Smoke()


with initialize(options=InitializeOptions(0)):
    Application.start(init)
sys.exit(0 if instance.success else 1)
