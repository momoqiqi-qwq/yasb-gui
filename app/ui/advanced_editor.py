"""Reusable advanced YAML settings panel with explicit staged application."""

from core.advanced_config import dump_mapping, parse_mapping
from core.localization import t
from core.ui_errors import display_error
from ui.controls import UIFactory
from winui3.microsoft.ui.xaml.controls import ContentDialogButton


def create_advanced_editor(app, title, description, get_data, apply_data, refresh, schema_node=None):
    ui = UIFactory()
    expander = ui.create_expander(title, description)
    expander.horizontal_alignment = 3
    panel = ui.create_stack_panel()
    panel.children.append(ui.create_text_block(t("advanced_hint"), wrap=True))
    button = ui.create_button(t("advanced_open"))

    def open_editor(sender, args):
        dialog = app.create_dialog(
            '<ContentDialog xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
            f'Title="{ui.escape_xml(title)}" PrimaryButtonText="{ui.escape_xml(t("advanced_apply"))}" '
            f'CloseButtonText="{ui.escape_xml(t("common_cancel"))}" DefaultButton="Primary"/>'
        )
        content = ui.create_stack_panel()
        content.min_width = 480
        editor = ui.create_textbox_multiline("", dump_mapping(get_data()))
        editor.max_height = 480
        status = ui.create_text_block("", wrap=True)
        content.children.append(editor)
        content.children.append(status)
        dialog.content = content

        def closing(sender, args):
            if args.result != ContentDialogButton.PRIMARY:
                return
            try:
                apply_data(parse_mapping(editor.text))
            except Exception as exc:
                args.cancel = True
                status.text = t("advanced_error", error=display_error(exc))
                return
            app.mark_unsaved()

        def closed(sender, args):
            if args.result == ContentDialogButton.PRIMARY:
                refresh()

        dialog.add_closing(closing)
        dialog.add_closed(closed)
        dialog.show_async()

    button.add_click(open_editor)
    panel.children.append(button)
    if schema_node:
        from ui.schema_editor import show_schema_editor

        form_button = ui.create_button(t("widgets_form_editor"))
        form_button.add_click(lambda s, e: show_schema_editor(app, title, schema_node, get_data(), apply_data, refresh))
        panel.children.append(form_button)
    expander.content = panel
    return expander
