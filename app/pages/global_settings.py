"""
Global settings page for YASB GUI.

Manages YASB behavior toggles and window manager integrations.
"""

import math

from core.advanced_config import replace_global
from core.localization import t
from core.logger import error
from core.yasb_schema import load_schema, profile
from ui.advanced_editor import create_advanced_editor
from ui.controls import UIFactory
from ui.loader import load_xaml
from winui3.microsoft.ui.xaml import FrameworkElement
from winui3.microsoft.ui.xaml.controls import Page, StackPanel
from winui3.microsoft.ui.xaml.markup import XamlReader


class GlobalSettingsPage:
    """Manages global settings."""

    def __init__(self, app):
        self._app = app
        self._config_manager = app._config_manager
        self._ui = UIFactory()

    def show(self):
        """Display global settings page."""
        try:
            self._app._loading = True

            page = XamlReader.load(load_xaml("pages/GlobalSettingsPage.xaml")).as_(Page)
            root = page.content.as_(FrameworkElement)
            main_panel = root.find_name("MainPanel").as_(StackPanel)

            # Page title
            main_panel.children.append(self._ui.create_page_title(t("global_title")))

            # === Behavior Section ===
            behavior_expander = self._ui.create_expander(t("global_behavior"), t("global_behavior_desc"))
            behavior_panel = self._ui.create_stack_panel(spacing=8)

            on_text = t("common_on")
            off_text = t("common_off")
            watch_stylesheet = self._ui.create_toggle(
                t("global_watch_stylesheet"),
                self._config_manager.get_global_setting("watch_stylesheet", True),
                on_text,
                off_text,
            )
            watch_config = self._ui.create_toggle(
                t("global_watch_config"),
                self._config_manager.get_global_setting("watch_config", True),
                on_text,
                off_text,
            )
            debug_mode = self._ui.create_toggle(
                t("global_debug_mode"), self._config_manager.get_global_setting("debug", False), on_text, off_text
            )
            update_check = self._ui.create_toggle(
                t("global_update_check"),
                self._config_manager.get_global_setting("update_check", True),
                on_text,
                off_text,
            )

            behavior_panel.children.append(watch_stylesheet)
            behavior_panel.children.append(watch_config)
            behavior_panel.children.append(debug_mode)
            behavior_panel.children.append(update_check)
            behavior_expander.content = behavior_panel
            main_panel.children.append(behavior_expander)

            for key, label, default in (
                ("show_systray", "global_show_systray", True),
                ("system_colors", "global_system_colors", False),
            ):
                control = self._ui.create_toggle(t(label), self._config_manager.get_global_setting(key, default))
                behavior_panel.children.append(control)

                def on_toggle(sender, args, setting=key, toggle=control):
                    if not self._app._loading:
                        self._config_manager.set_global_setting(setting, toggle.is_on)
                        self._app.mark_unsaved()

                control.add_toggled(on_toggle)

            tooltip_expander = self._ui.create_expander(t("global_tooltip"), t("global_tooltip_desc"))
            tooltip_panel = self._ui.create_stack_panel()
            tooltip = self._config_manager.config.get("tooltip", {})

            def update_tooltip(key, value, nested=False):
                if self._app._loading:
                    return
                data = self._config_manager.config.setdefault("tooltip", {})
                if nested:
                    data = data.setdefault("blur_effect", {})
                data[key] = value
                self._app.mark_unsaved()

            offset = self._ui.create_numberbox(t("global_tooltip_offset"), tooltip.get("offset", 5), 0, 100)
            offset.add_value_changed(
                lambda s, e: update_tooltip("offset", int(offset.value)) if math.isfinite(offset.value) else None
            )
            tooltip_panel.children.append(offset)
            blur = tooltip.get("blur_effect", {})
            for key, label in (
                ("enabled", "bars_enable_blur"),
                ("dark_mode", "bars_dark_mode"),
                ("round_corners", "bars_round_corners"),
            ):
                toggle = self._ui.create_toggle(t(label), blur.get(key, False))
                toggle.add_toggled(lambda s, e, k=key, c=toggle: update_tooltip(k, c.is_on, True))
                tooltip_panel.children.append(toggle)
            corner_options = ["normal", "small"]
            corners = self._ui.create_combobox(
                t("bars_round_corners_type"), corner_options, blur.get("round_corners_type", "normal")
            )
            corners.add_selection_changed(
                lambda s, e: (
                    update_tooltip("round_corners_type", corner_options[corners.selected_index], True)
                    if corners.selected_index >= 0
                    else None
                )
            )
            tooltip_panel.children.append(corners)
            border = self._ui.create_textbox(t("bars_border_color"), str(blur.get("border_color", "None")))
            border.add_text_changed(lambda s, e: update_tooltip("border_color", border.text, True))
            tooltip_panel.children.append(border)
            tooltip_expander.content = tooltip_panel
            main_panel.children.append(tooltip_expander)

            # === Komorebi Section ===
            komorebi_expander = self._ui.create_expander(t("global_komorebi"), t("global_komorebi_desc"))
            komorebi_panel = self._ui.create_stack_panel(spacing=8)

            komorebi = self._config_manager.get_komorebi_settings()
            komorebi_start = self._ui.create_textbox(t("global_komorebi_start"), komorebi.get("start_command", ""))
            komorebi_stop = self._ui.create_textbox(t("global_komorebi_stop"), komorebi.get("stop_command", ""))
            komorebi_reload = self._ui.create_textbox(t("global_komorebi_reload"), komorebi.get("reload_command", ""))

            komorebi_panel.children.append(komorebi_start)
            komorebi_panel.children.append(komorebi_stop)
            komorebi_panel.children.append(komorebi_reload)
            komorebi_expander.content = komorebi_panel
            main_panel.children.append(komorebi_expander)

            # === GlazeWM Section ===
            glazewm_expander = self._ui.create_expander(t("global_glazewm"), t("global_glazewm_desc"))
            glazewm_panel = self._ui.create_stack_panel(spacing=8)

            glazewm = self._config_manager.get_glazewm_settings()
            glazewm_start = self._ui.create_textbox(t("global_glazewm_start"), glazewm.get("start_command", ""))
            glazewm_stop = self._ui.create_textbox(t("global_glazewm_stop"), glazewm.get("stop_command", ""))
            glazewm_reload = self._ui.create_textbox(t("global_glazewm_reload"), glazewm.get("reload_command", ""))

            glazewm_panel.children.append(glazewm_start)
            glazewm_panel.children.append(glazewm_stop)
            glazewm_panel.children.append(glazewm_reload)
            glazewm_expander.content = glazewm_panel
            main_panel.children.append(glazewm_expander)

            # === Paths Section ===
            paths_expander = self._ui.create_expander(t("global_config_paths"), t("global_config_paths_desc"))
            paths_panel = self._ui.create_stack_panel(spacing=8)

            config_path_text = t("common_config_path", path=self._config_manager.config_path)
            styles_path_text = t("common_styles_path", path=self._config_manager.styles_path)

            config_path = self._ui.create_path_text(config_path_text)
            styles_path = self._ui.create_path_text(styles_path_text)

            paths_panel.children.append(config_path)
            paths_panel.children.append(styles_path)
            paths_expander.content = paths_panel
            main_panel.children.append(paths_expander)

            main_panel.children.append(
                create_advanced_editor(
                    self._app,
                    t("global_advanced"),
                    t("global_advanced_desc"),
                    lambda: {k: v for k, v in self._config_manager.config.items() if k not in ("bars", "widgets")},
                    lambda data: replace_global(self._config_manager.config, data),
                    self.show,
                    schema_node={
                        "type": "object",
                        "properties": {
                            k: v
                            for k, v in load_schema(profile())["properties"].items()
                            if k not in ("bars", "widgets")
                        },
                    },
                )
            )

            # Beta warning
            beta_info = self._ui.create_info_bar(
                message=t("global_beta_warning"),
                # severity="Warning",
                is_closable=False,
                margin="0,0,0,0",
                show_icon=True,
                action_uri="https://github.com/amnweb/yasb-gui/issues",
                action_text=t("global_beta_link"),
            )
            main_panel.children.append(beta_info)

            self._app._loading = False

            # Event handlers
            def save_global():
                if self._app._loading:
                    return
                self._config_manager.set_global_setting("watch_stylesheet", watch_stylesheet.is_on)
                self._config_manager.set_global_setting("watch_config", watch_config.is_on)
                self._config_manager.set_global_setting("debug", debug_mode.is_on)
                self._config_manager.set_global_setting("update_check", update_check.is_on)

                # Set or remove komorebi/glazewm based on content
                komorebi_data = {
                    **self._config_manager.get_komorebi_settings(),
                    "start_command": komorebi_start.text,
                    "stop_command": komorebi_stop.text,
                    "reload_command": komorebi_reload.text,
                }
                if any(v for v in komorebi_data.values()):
                    self._config_manager.set_komorebi_settings(komorebi_data)
                else:
                    self._config_manager.remove_setting("komorebi")

                glazewm_data = {
                    **self._config_manager.get_glazewm_settings(),
                    "start_command": glazewm_start.text,
                    "stop_command": glazewm_stop.text,
                    "reload_command": glazewm_reload.text,
                }
                if any(v for v in glazewm_data.values()):
                    self._config_manager.set_glazewm_settings(glazewm_data)
                else:
                    self._config_manager.remove_setting("glazewm")

                self._app.mark_unsaved()

            watch_stylesheet.add_toggled(lambda s, e: save_global())
            watch_config.add_toggled(lambda s, e: save_global())
            debug_mode.add_toggled(lambda s, e: save_global())
            update_check.add_toggled(lambda s, e: save_global())
            komorebi_start.add_text_changed(lambda s, e: save_global())
            komorebi_stop.add_text_changed(lambda s, e: save_global())
            komorebi_reload.add_text_changed(lambda s, e: save_global())
            glazewm_start.add_text_changed(lambda s, e: save_global())
            glazewm_stop.add_text_changed(lambda s, e: save_global())
            glazewm_reload.add_text_changed(lambda s, e: save_global())

            self._app._content_area.content = page
        except Exception as e:
            error(f"Global settings error: {e}", exc_info=True)
        finally:
            self._app._loading = False
