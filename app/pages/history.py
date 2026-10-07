"""Preview and restore automatic snapshots for the active configuration directory."""

import os
from pathlib import Path

from core.file_history import fingerprint, list_snapshots, restore_snapshot, snapshot_path, unified_diff
from core.localization import t
from core.ui_errors import display_error
from ui.controls import UIFactory
from winui3.microsoft.ui.xaml import Thickness
from winui3.microsoft.ui.xaml.controls import ContentDialogButton, ScrollViewer, TextBox


class HistoryPage:
    def __init__(self, app):
        self.app = app
        self.manager = app._config_manager
        self.ui = UIFactory()

    def show(self):
        panel = self.ui.create_stack_panel(spacing=12)
        panel.children.append(self.ui.create_page_title(t("history_title")))
        panel.children.append(self.ui.create_text_block(t("history_hint"), wrap=True))
        panel.children.append(self.ui.create_text_block(self.manager.config_path, wrap=True, secondary=True))
        refresh = self.ui.create_button(t("history_refresh"))
        refresh.add_click(lambda s, e: self.show())
        panel.children.append(refresh)
        entries = list_snapshots(self.manager)
        if not entries:
            panel.children.append(self.ui.create_text_block(t("history_empty"), wrap=True))
        for entry in entries:
            button = self.ui.create_button(f"{entry['name']}  ·  {entry['size']} B")
            button.add_click(lambda s, e, item=entry: self.preview(item))
            panel.children.append(button)
        folder = self.ui.create_button(t("settings_open_backups"))

        def open_folder(sender, args):
            self.manager.backup_directory.mkdir(parents=True, exist_ok=True)
            os.startfile(str(self.manager.backup_directory))

        folder.add_click(open_folder)
        panel.children.append(folder)
        viewer = ScrollViewer()
        viewer.padding = Thickness(40, 24, 40, 80)
        viewer.content = panel
        self.app._content_area.content = viewer

    def preview(self, entry):
        try:
            source = snapshot_path(self.manager, entry["name"])
            target = Path(self.manager.config_path if entry["file"] == "config.yaml" else self.manager.styles_path)
            disk_version, backup_version = fingerprint(target), fingerprint(source)
            before = target.read_text(encoding="utf-8") if target.exists() else ""
            after = source.read_text(encoding="utf-8")
            dialog = self.app.create_dialog(
                '<ContentDialog xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
                f'Title="{self.ui.escape_xml(t("history_preview"))}" '
                f'PrimaryButtonText="{self.ui.escape_xml(t("history_restore"))}" '
                f'CloseButtonText="{self.ui.escape_xml(t("common_cancel"))}" DefaultButton="Close"/>'
            )
            body = self.ui.create_stack_panel()
            body.children.append(self.ui.create_text_block(entry["name"], wrap=True))
            body.children.append(self.ui.create_text_block(t("history_restore_hint"), wrap=True))
            text = TextBox()
            text.is_read_only = True
            text.accepts_return = True
            text.text = unified_diff(before, after, entry["file"] + " (disk)", entry["name"])
            viewer = ScrollViewer()
            viewer.max_height = 300
            viewer.content = text
            body.children.append(viewer)
            status = self.ui.create_text_block("", wrap=True)
            body.children.append(status)
            dialog.content = body

            def closing(sender, args):
                if args.result != ContentDialogButton.PRIMARY:
                    return
                try:
                    dirty = self.app._unsaved_config if entry["file"] == "config.yaml" else self.app._unsaved_styles
                    if dirty or self.app._saving:
                        raise ValueError(t("history_unsaved"))
                    filename = restore_snapshot(self.manager, entry["name"], disk_version, backup_version)
                    self.app._reload_disk_file(filename)
                except Exception as exc:
                    args.cancel = True
                    status.text = display_error(exc)

            dialog.add_closing(closing)
            dialog.add_closed(lambda s, e: self.show() if e.result == ContentDialogButton.PRIMARY else None)
            dialog.show_async()
        except Exception as exc:
            self.app._show_save_error(display_error(exc))
