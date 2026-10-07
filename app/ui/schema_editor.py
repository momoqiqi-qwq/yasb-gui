"""Version-aware form editor for every official widget option."""

import copy
import math
from io import StringIO

from core.advanced_config import yaml_parser
from core.command_presets import field_presets
from core.localization import t
from core.ui_errors import display_error
from core.yasb_schema import errors_for, field_label, make_defaults, resolve
from ui.command_presets import create_preset_picker
from ui.controls import UIFactory
from winui3.microsoft.ui.xaml.controls import ContentDialogButton, NumberBox, ScrollViewer, TextBox


def build_form(node, original):
    ui = UIFactory()
    state = copy.deepcopy(original)
    drafts = []

    def set_value(path, value):
        target = state
        for key in path[:-1]:
            if not isinstance(target.get(key), dict):
                target[key] = {}
            target = target[key]
        target[path[-1]] = value

    def remove_value(path):
        target = state
        for key in path[:-1]:
            target = target.get(key, {})
        target.pop(path[-1], None)

    def fields(schema_node, values, path=()):
        panel = ui.create_stack_panel()
        schema_node = resolve(schema_node)
        for key, raw in schema_node.get("properties", {}).items():
            spec = resolve(raw)
            full_path = (*path, key)
            label = f"{field_label(key)} ({key})"
            value = values.get(key, make_defaults(spec))
            if spec.get("type") == "object" and spec.get("properties"):
                group = ui.create_expander(label)
                group.content = fields(spec, value if isinstance(value, dict) else {}, full_path)
                panel.children.append(group)
                continue
            row = ui.create_stack_panel(spacing=4)
            row.children.append(ui.create_text_block(label, wrap=True))
            include = ui.create_toggle(t("schema_use_field"), key in values)
            row.children.append(include)
            if "enum" in spec and all(isinstance(v, str) for v in spec["enum"]):
                choices = spec["enum"]
                labels = [t("value_" + item) if t("value_" + item) != "value_" + item else item for item in choices]
                control = ui.create_combobox(
                    "", labels, labels[choices.index(value)] if value in choices else labels[0]
                )
                read = lambda c=control, options=choices: options[max(c.selected_index, 0)]
                event = control.add_selection_changed
            elif spec.get("type") == "boolean":
                control = ui.create_toggle("", bool(value))
                read = lambda c=control: c.is_on
                event = control.add_toggled
            elif spec.get("type") in ("integer", "number"):
                control = NumberBox()
                control.value = float(value or 0)
                control.small_change = 1
                read = lambda c=control, typ=spec["type"]: (
                    int(c.value) if typ == "integer" and c.value.is_integer() else c.value
                )
                event = control.add_value_changed
            elif spec.get("type") == "string":
                control = ui.create_textbox("", str(value or ""))
                control.width = 440
                read = lambda c=control: c.text
                event = control.add_text_changed
            else:
                control = TextBox()
                control.accepts_return = True
                control.text_wrapping = 1
                control.min_height = 70
                control.max_height = 180
                stream = StringIO()
                yaml_parser().dump(value, stream)
                control.text = stream.getvalue().removesuffix("...\n").rstrip()
                read = lambda c=control: yaml_parser().load(c.text)
                event = None
                row.children.append(ui.create_text_block(t("schema_yaml_value"), secondary=True, wrap=True))

            control.is_enabled = include.is_on
            drafts.append((full_path, control, include, read))

            def changed(sender, args, p=full_path, get=read, toggle=include, c=control):
                if toggle.is_on:
                    if isinstance(c, NumberBox) and not math.isfinite(c.value):
                        return
                    set_value(p, get())

            if event:
                event(changed)

            def inclusion(sender, args, p=full_path, get=read, toggle=include, c=control, is_yaml=event is None):
                c.is_enabled = toggle.is_on
                if not toggle.is_on:
                    remove_value(p)
                elif not is_yaml:
                    set_value(p, get())

            include.add_toggled(inclusion)
            row.children.append(control)
            presets = field_presets(full_path, schema_node)
            if presets and isinstance(control, TextBox):

                def apply_preset(preset, c=control, toggle=include):
                    toggle.is_on = True
                    c.text = preset["value"]

                picker = create_preset_picker(presets, apply_preset)
                row.children.append(picker)
            panel.children.append(row)
        return panel

    panel = fields(node, original)

    def collect():
        for path, control, include, read in drafts:
            if include.is_on:
                if isinstance(control, NumberBox) and not math.isfinite(control.value):
                    raise ValueError(t("error_positive", field=".".join(path)))
                set_value(path, read())
        return state

    return panel, collect


def show_schema_editor(app, title, node, original, apply_data, refresh):
    ui = UIFactory()
    dialog = app.create_dialog(
        '<ContentDialog xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
        f'Title="{ui.escape_xml(title)}" PrimaryButtonText="{ui.escape_xml(t("advanced_apply"))}" '
        f'CloseButtonText="{ui.escape_xml(t("common_cancel"))}" DefaultButton="Primary"/>'
    )
    panel, collect = build_form(node, original)
    body = ui.create_stack_panel()
    body.min_width = 480
    body.children.append(ui.create_text_block(t("schema_form_hint"), wrap=True))
    viewer = ScrollViewer()
    viewer.max_height = 470
    viewer.content = panel
    body.children.append(viewer)
    status = ui.create_text_block("", wrap=True)
    body.children.append(status)
    dialog.content = body

    def closing(sender, args):
        if args.result != ContentDialogButton.PRIMARY:
            return
        try:
            data = collect()
            issues = errors_for(data, node)
            if issues:
                raise ValueError("\n".join(issues[:8]))
            apply_data(data)
            app.mark_unsaved()
        except Exception as exc:
            args.cancel = True
            status.text = t("advanced_error", error=display_error(exc))

    dialog.add_closing(closing)
    dialog.add_closed(lambda s, e: refresh() if e.result == ContentDialogButton.PRIMARY else None)
    dialog.show_async()
