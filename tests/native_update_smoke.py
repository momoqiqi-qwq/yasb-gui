"""Verify release cards and portable download clicks in a hidden real WinUI window."""

import os
import sys
import traceback
from datetime import timedelta
from pathlib import Path

root = Path(__file__).resolve().parents[1]
case = root / "work" / "native-update-smoke"
os.environ["APPDATA"] = str(case / "profile")
os.environ["TEMP"] = str(case / "temp")
Path(os.environ["TEMP"]).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / "app"))

from core.application import ConfiguratorApp  # noqa: E402
from core.constants import GITHUB_YASB_GUI  # noqa: E402
from core.preferences import get_preferences  # noqa: E402
from pages import app_settings  # noqa: E402
from winui3.microsoft.ui.xaml import Application, DispatcherTimer, Window  # noqa: E402
from winui3.microsoft.ui.xaml.automation.peers import ButtonAutomationPeer  # noqa: E402
from winui3.microsoft.ui.xaml.controls import (  # noqa: E402
    Button,
    Grid,
    HyperlinkButton,
    StackPanel,
    TextBlock,
    XamlControlsResources,
)
from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import (  # noqa: E402
    InitializeOptions,
    initialize,
)


class Smoke(ConfiguratorApp):
    def _on_launched(self, args):
        try:
            self.resources.merged_dictionaries.append(XamlControlsResources())
            get_preferences().set("ui_animations", False)
            self._window = Window()
            self._window.activate()
            self._window.app_window.hide()
            app_settings.IS_EXECUTABLE = True
            self.downloads = []
            app_settings.webbrowser.open = lambda url: self.downloads.append(url)
            self.steps = iter(self.verify())
            self.timer = DispatcherTimer()
            self.timer.interval = timedelta(milliseconds=100)
            self.timer.add_tick(self.tick)
            self.timer.start()
        except Exception:
            self.finish(traceback.format_exc())

    def tick(self, sender, args):
        try:
            next(self.steps)
        except StopIteration:
            self.finish(
                "PASS: real WinUI portable/MSIX labels, fork release links and portable click without install/close"
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

    def update_card(self, extension, packaged):
        url = f"https://example.invalid/update.{extension}"
        app_settings.app_updater.get_available_update = lambda: ("9.0.0", url)
        app_settings.app_updater.is_msix_install = lambda: packaged
        card = self._app_settings_page._create_app_update_card()
        self._window.content = card
        grid = card.child.as_(Grid)
        panel = grid.find_name("ControlContainer").as_(StackPanel).children.get_at(0).as_(StackPanel)
        notes = panel.children.get_at(0).as_(HyperlinkButton)
        assert notes.navigate_uri.absolute_uri == f"{GITHUB_YASB_GUI}/releases/tag/v9.0.0"
        return url, panel.children.get_at(1).as_(Button)

    def verify(self):
        url, button = self.update_card("exe", False)
        yield
        assert button.content.as_(TextBlock).text == "下载便携版"
        ButtonAutomationPeer(button).invoke()
        yield
        assert self.downloads == [url]
        _, button = self.update_card("msixbundle", True)
        yield
        assert button.content.as_(TextBlock).text == "下载并安装"
        assert len(self.downloads) == 1


def init(args):
    global instance
    instance = Smoke()


with initialize(options=InitializeOptions(0)):
    Application.start(init)
sys.exit(0 if instance.success else 1)
