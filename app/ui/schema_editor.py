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
    array_bindings = []

    def get_value(path):
        """Read a value from the draft, including list indexes."""
        current = state
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                return None
        return current

    def set_value(path, value):
        target = state
        for key in path[:-1]:
            if isinstance(target, dict):
                if key not in target or not isinstance(target[key], (dict, list)):
                    target[key] = {} if not isinstance(key, int) else []
                target = target[key]
            elif isinstance(target, list) and isinstance(key, int):
                while len(target) <= key:
                    target.append({})
                target = target[key]
            else:
                return
        target[path[-1]] = value

    def remove_value(path):
        target = state
        for key in path[:-1]:
            if isinstance(target, dict):
                target = target.get(key, {})
            elif isinstance(target, list) and isinstance(key, int) and 0 <= key < len(target):
                target = target[key]
            else:
                return
        if isinstance(target, dict):
            target.pop(path[-1], None)
        elif isinstance(target, list) and isinstance(path[-1], int) and 0 <= path[-1] < len(target):
            target.pop(path[-1])

    def effective_spec(raw):
        """Resolve references and choose the non-null branch of a union."""
        spec = resolve(raw)
        choices = spec.get("anyOf", spec.get("oneOf"))
        if choices and not spec.get("type"):
            non_null = next((choice for choice in choices if choice.get("type") != "null"), choices[0])
            return resolve(non_null)
        return spec

    def scalar_editor(spec, value, label=""):
        """Create a scalar control and a reader for an array item."""
        raw_spec = resolve(spec)
        nullable = any(choice.get("type") == "null" for choice in raw_spec.get("anyOf", []))
        spec = effective_spec(raw_spec)
        preserve_null = nullable and value is None
        if "enum" in spec and all(isinstance(item, str) for item in spec["enum"]):
            choices = spec["enum"]
            selected = value if value in choices else choices[0]
            control = ui.create_combobox(label, choices, selected)
            return control, lambda c=control, options=choices: options[max(c.selected_index, 0)]
        if spec.get("type") == "boolean":
            control = ui.create_toggle(label, bool(value))
            return control, lambda c=control: c.is_on
        if spec.get("type") in ("integer", "number"):
            control = NumberBox()
            control.header = ui.create_text_block(label) if label else None
            control.value = float(value or 0)
            control.small_change = 1

            def read_number(c=control, typ=spec["type"]):
                return int(c.value) if typ == "integer" and c.value.is_integer() else c.value

            return control, read_number
        if spec.get("type") == "string":
            control = ui.create_textbox(label, "" if value is None else str(value))

            def read_text(c=control, is_nullable=nullable, keep_null=preserve_null):
                return None if is_nullable and keep_null and not c.text.strip() else c.text

            return control, read_text

        # Keep uncommon item types editable without losing YAML support.
        control = TextBox()
        control.header = ui.create_text_block(label) if label else None
        control.accepts_return = True
        control.text_wrapping = 1
        control.min_height = 70
        stream = StringIO()
        yaml_parser().dump(value, stream)
        control.text = stream.getvalue().removesuffix("...\n").rstrip()
        return control, lambda c=control: yaml_parser().load(c.text)

    def object_item_editor(item_spec, value):
        """Render the scalar fields of an object array item."""
        item_spec = effective_spec(item_spec)
        item_value = copy.deepcopy(value) if isinstance(value, dict) else {}
        panel = ui.create_stack_panel(spacing=4)
        readers = []
        for key, raw in item_spec.get("properties", {}).items():
            raw_spec = resolve(raw)
            spec = effective_spec(raw_spec)
            if key not in item_value and "default" not in raw_spec and key not in item_spec.get("required", []):
                continue
            field_value = item_value.get(key, make_defaults(raw_spec))
            label = f"{field_label(key)} ({key})"
            if spec.get("type") == "object" and spec.get("properties"):
                nested_panel, nested_reader = object_item_editor(spec, field_value)
                group = ui.create_expander(label)
                group.content = nested_panel
                panel.children.append(group)
                readers.append((key, nested_reader))
                continue
            if spec.get("type") == "array":
                # Nested arrays remain available as YAML, while the outer list
                # gets the add/remove/reorder controls users need most often.
                control = TextBox()
                control.header = ui.create_text_block(label)
                control.accepts_return = True
                control.text_wrapping = 1
                stream = StringIO()
                yaml_parser().dump(field_value, stream)
                control.text = stream.getvalue().removesuffix("...\n").rstrip()
                reader = lambda c=control: yaml_parser().load(c.text)
                panel.children.append(control)
                readers.append((key, reader))
                continue
            control, reader = scalar_editor(spec, field_value, label)
            panel.children.append(control)
            readers.append((key, reader))

        def read_item():
            result = copy.deepcopy(item_value)
            for key, reader in readers:
                result[key] = reader()
            return result

        return panel, read_item

    def array_editor(panel, spec, path):
        """Render an editable list with add, remove and reorder actions."""
        item_spec = effective_spec(spec.get("items", {}))
        binding = {"readers": []}
        array_bindings.append(binding)

        def sync():
            if binding.get("include") is not None and not binding["include"].is_on:
                remove_value(path)
                return []
            values = [reader() for reader in binding["readers"]]
            set_value(path, values)
            return values

        binding["sync"] = sync

        def render():
            values = get_value(path)
            if not isinstance(values, list):
                values = []
                set_value(path, values)
            panel.children.clear()
            actions = ui.create_stack_panel(spacing=4, orientation="Horizontal")
            add = ui.create_button(t("schema_add_item"))
            max_items = spec.get("maxItems")
            add.is_enabled = max_items is None or len(values) < max_items

            def append_item(sender, args):
                sync()
                values = get_value(path)
                if max_items is None or len(values) < max_items:
                    values.append(make_defaults(item_spec))
                    render()

            add.add_click(append_item)
            actions.children.append(add)
            panel.children.append(actions)
            if not values:
                panel.children.append(ui.create_text_block(t("schema_list_empty"), secondary=True))

            readers = []
            for index, value in enumerate(values):
                row = ui.create_stack_panel(spacing=4)
                if item_spec.get("type") == "object" and item_spec.get("properties"):
                    group, reader = object_item_editor(item_spec, value)
                    expander = ui.create_expander(t("schema_item", index=index + 1))
                    expander.content = group
                    row.children.append(expander)
                else:
                    control, reader = scalar_editor(item_spec, value, t("schema_item", index=index + 1))
                    row.children.append(control)
                readers.append(reader)

                item_actions = ui.create_stack_panel(spacing=4, orientation="Horizontal")
                move_up = ui.create_button(t("schema_move_up"))
                move_down = ui.create_button(t("schema_move_down"))
                remove = ui.create_button(t("schema_remove_item"))
                move_up.is_enabled = index > 0
                move_down.is_enabled = index < len(values) - 1
                min_items = spec.get("minItems", 0)
                remove.is_enabled = len(values) > min_items

                def reorder(sender, args, current=index, delta=0):
                    sync()
                    values = get_value(path)
                    target = current + delta
                    if 0 <= target < len(values):
                        values[current], values[target] = values[target], values[current]
                        render()

                def delete(sender, args, current=index):
                    sync()
                    values = get_value(path)
                    if len(values) > spec.get("minItems", 0):
                        values.pop(current)
                        render()

                move_up.add_click(lambda s, e: reorder(s, e, delta=-1))
                move_down.add_click(lambda s, e: reorder(s, e, delta=1))
                remove.add_click(delete)
                item_actions.children.append(move_up)
                item_actions.children.append(move_down)
                item_actions.children.append(remove)
                row.children.append(item_actions)
                panel.children.append(row)
            binding["readers"] = readers

        binding["render"] = render
        render()
        return binding

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
            if spec.get("type") == "array":
                list_panel = ui.create_stack_panel(spacing=4)
                binding = array_editor(list_panel, spec, full_path)
                binding["include"] = include
                list_panel.is_enabled = include.is_on

                def toggle_array(sender, args, p=full_path, toggle=include, editor=list_panel):
                    editor.is_enabled = toggle.is_on
                    if toggle.is_on:
                        if not isinstance(get_value(p), list):
                            set_value(p, copy.deepcopy(make_defaults(spec)))
                            binding["render"]()
                    else:
                        remove_value(p)

                include.add_toggled(toggle_array)
                row.children.append(list_panel)
                row.children.append(ui.create_text_block(t("schema_list_hint"), secondary=True, wrap=True))
                panel.children.append(row)
                continue
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
        for binding in array_bindings:
            binding["sync"]()
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
