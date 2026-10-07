"""Explicit selection plus Apply; selecting a preset alone never changes a draft."""

from core.localization import t
from ui.controls import UIFactory


def create_preset_picker(presets, apply_value):
    ui = UIFactory()
    panel = ui.create_stack_panel(spacing=4)
    combo = ui.create_combobox("", [t("preset_select"), *(item["name"] for item in presets)], t("preset_select"))
    button = ui.create_button(t("preset_apply"))
    button.is_enabled = False
    combo.add_selection_changed(lambda s, e: setattr(button, "is_enabled", combo.selected_index > 0))

    def apply(sender, args):
        index = combo.selected_index - 1
        if 0 <= index < len(presets):
            apply_value(presets[index])

    button.add_click(apply)
    panel.children.append(combo)
    panel.children.append(button)
    return panel
