"""Manage existing integrations without overwriting their customized appearance."""

from core.community_widgets import community_templates, integration_health, integration_settings
from core.localization import t
from ui.community_editor import show_community_editor
from ui.controls import UIFactory
from winui3.microsoft.ui.xaml import Thickness
from winui3.microsoft.ui.xaml.controls import ScrollViewer


class CommunityPage:
    def __init__(self, app):
        self.app = app
        self.manager = app._config_manager
        self.ui = UIFactory()

    def show(self):
        panel = self.ui.create_stack_panel(spacing=12)
        panel.children.append(self.ui.create_page_title(t("community_manager_title")))
        panel.children.append(self.ui.create_text_block(t("community_manager_hint"), wrap=True))
        refresh = self.ui.create_button(t("history_refresh"))
        refresh.add_click(lambda s, e: self.show())
        panel.children.append(refresh)
        found = 0
        for name, widget in self.manager.get_widgets().items():
            settings = integration_settings(widget)
            if settings is None:
                continue
            found += 1
            template = next(item for item in community_templates() if item["community_kind"] == settings["kind"])
            panel.children.append(self.ui.create_text_block(name + " · " + template["name"], wrap=True))
            details = str(settings.get("executable", settings.get("output_directory", "")))
            if details:
                panel.children.append(self.ui.create_text_block(details, wrap=True, secondary=True))
            result = self.ui.create_text_block("", wrap=True)
            check = self.ui.create_button(t("community_check_dependencies"))

            def diagnose(sender, args, current=settings, target=result):
                try:
                    target.text = "\n".join(integration_health(current)) or t("community_dependencies_ok")
                except Exception as exc:
                    target.text = str(exc)

            check.add_click(diagnose)
            panel.children.append(check)
            panel.children.append(result)
            edit = self.ui.create_button(t("community_reconfigure"))

            def configure(sender, args, selected=widget, initial=settings, item=template):
                def apply(options):
                    selected["options"] = options

                show_community_editor(self.app, item, apply, self.show, settings=initial, original=selected["options"])

            edit.add_click(configure)
            panel.children.append(edit)
        if not found:
            panel.children.append(self.ui.create_text_block(t("community_manager_empty"), wrap=True))
        viewer = ScrollViewer()
        viewer.padding = Thickness(40, 24, 40, 80)
        viewer.content = panel
        self.app._content_area.content = viewer
