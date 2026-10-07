"""Dedicated application list editor; all changes remain drafts until Apply."""

import copy

from core.apps_editor import APPS_TYPE, application_entry, pick_files, update_app_list
from core.button_icons import bundled_icon
from core.command_presets import command_presets
from core.localization import t
from core.ui_errors import display_error
from core.yasb_schema import validate_options
from ui.command_presets import create_preset_picker
from ui.controls import UIFactory
from winui3.microsoft.ui.xaml.controls import ContentDialogButton, ScrollViewer, TextBox


def show_apps_editor(app, original, apply, refresh):
    ui = UIFactory()
    entries = copy.deepcopy(original.get("app_list", []))
    dialog = app.create_dialog(
        '<ContentDialog xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
        f'Title="{ui.escape_xml(t("apps_editor"))}" '
        f'PrimaryButtonText="{ui.escape_xml(t("advanced_apply"))}" '
        f'CloseButtonText="{ui.escape_xml(t("common_cancel"))}" DefaultButton="Primary"/>'
    )
    body = ui.create_stack_panel(spacing=8)
    body.min_width = 480
    body.children.append(ui.create_text_block(t("apps_hint"), wrap=True, secondary=True))
    browse = ui.create_button(t("apps_browse"))
    body.children.append(browse)
    rows = ui.create_stack_panel(spacing=12)
    viewer = ScrollViewer()
    viewer.max_height = 420
    viewer.content = rows
    body.children.append(viewer)
    status = ui.create_text_block("", wrap=True)
    body.children.append(status)
    dialog.content = body
    fields = []

    def collect_fields():
        for entry, key, field in fields:
            # Read controls directly: WinUI may defer TextChanged notifications.
            value = field.text
            if key != "name" or value or entry.get(key) is not None:
                entry[key] = value

    def render():
        collect_fields()
        fields.clear()
        rows.children.clear()
        if not entries:
            rows.children.append(ui.create_text_block(t("apps_empty"), wrap=True))
        for index, entry in enumerate(entries):
            row = ui.create_stack_panel(spacing=4)
            row.children.append(ui.create_text_block(f"{index + 1}. {entry.get('name') or t('apps_unnamed')}"))
            for key, label in (("name", "apps_name"), ("icon", "apps_icon"), ("launch", "apps_launch")):
                field = TextBox()
                field.header = ui.create_text_block(t(label))
                field.text = str(entry.get(key) or "")
                fields.append((entry, key, field))
                row.children.append(field)
            actions = ui.create_stack_panel(spacing=4, orientation="Horizontal")
            icon = ui.create_button(t("apps_choose_icon"))

            def choose_icon(s, e, item=entry):
                try:
                    collect_fields()
                    selected = pick_files(icons=True)
                    if selected:
                        item["icon"] = selected[0]
                        # Update the control too, before render collects the draft.
                        for current, key, field in fields:
                            if current is item and key == "icon":
                                field.text = selected[0]
                        render()
                except Exception as exc:
                    status.text = t("apps_operation_error", error=str(exc))

            icon.add_click(choose_icon)
            actions.children.append(icon)
            for delta, label in ((-1, "widgets_move_up"), (1, "widgets_move_down")):
                move = ui.create_button(t(label))
                move.is_enabled = 0 <= index + delta < len(entries)

                def reorder(s, e, i=index, d=delta):
                    entries[i], entries[i + d] = entries[i + d], entries[i]
                    render()

                move.add_click(reorder)
                actions.children.append(move)
            remove = ui.create_button(t("widgets_delete"))

            def delete(s, e, i=index):
                entries.pop(i)
                render()

            remove.add_click(delete)
            actions.children.append(remove)
            row.children.append(actions)
            rows.children.append(row)

    def choose(s, e):
        try:
            collect_fields()
            selected = [application_entry(path) for path in pick_files()]
            existing = {item.get("launch") for item in entries}
            for item in selected:
                if item["launch"] not in existing:
                    entries.append(item)
                    existing.add(item["launch"])
            render()
            status.text = ""
        except Exception as exc:
            status.text = t("apps_operation_error", error=str(exc))

    def add_preset(preset):
        collect_fields()
        entries.append({key: preset[key] for key in ("name", "icon", "launch")})
        render()

    presets = create_preset_picker(command_presets(), add_preset)
    body.children.insert_at(2, presets)

    manual = ui.create_button(t("apps_add_command"))

    def add_command(sender, args):
        collect_fields()
        entries.append({"name": t("apps_command_name"), "icon": bundled_icon(), "launch": ""})
        render()

    manual.add_click(add_command)
    body.children.insert_at(3, manual)

    def closing(s, args):
        if args.result != ContentDialogButton.PRIMARY:
            return
        try:
            collect_fields()
            if any(not item.get("icon", "").strip() or not item.get("launch", "").strip() for item in entries):
                raise ValueError(t("apps_required"))
            options = update_app_list(original, entries)
            validate_options(APPS_TYPE, options)
            apply(options)
            app.mark_unsaved()
        except Exception as exc:
            args.cancel = True
            status.text = display_error(exc)

    browse.add_click(choose)
    dialog.add_closing(closing)
    dialog.add_closed(lambda s, e: refresh() if e.result == ContentDialogButton.PRIMARY else None)
    render()
    dialog.show_async()
