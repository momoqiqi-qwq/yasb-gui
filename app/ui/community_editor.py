"""Configure companion integrations without editing shell command strings."""

from pathlib import Path

from core.community_widgets import build_community_options, find_protonvpn, pick_executable, update_integration_options
from core.localization import t
from core.ui_errors import display_error
from core.yasb_schema import validate_options
from ui.controls import UIFactory
from winui3.microsoft.ui.xaml.controls import CheckBox, ContentDialogButton, TextBox


def show_community_editor(app, template, apply, refresh, settings=None, original=None):
    ui = UIFactory()
    kind = template["community_kind"]
    settings = settings or {}
    dialog = app.create_dialog(
        '<ContentDialog xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
        f'Title="{ui.escape_xml(template["name"])}" '
        f'PrimaryButtonText="{ui.escape_xml(t("advanced_apply"))}" '
        f'CloseButtonText="{ui.escape_xml(t("common_cancel"))}" DefaultButton="Primary"/>'
    )
    body = ui.create_stack_panel(spacing=10)
    body.min_width = 440
    body.children.append(ui.create_text_block(template["description"], wrap=True))
    body.children.append(ui.create_text_block(t("community_execution_hint"), wrap=True, secondary=True))
    executable = TextBox()
    interval = TextBox()
    output = TextBox()
    toggle = CheckBox()
    if kind in ("device", "protonvpn"):
        executable.header = ui.create_text_block(t("community_executable"))
        executable.placeholder_text = t("community_device_default") if kind == "device" else "ProtonVPN.Client.exe"
        executable.text = settings.get("executable", find_protonvpn() if kind == "protonvpn" else "")
        body.children.append(executable)
        browse = ui.create_button(t("community_choose_executable"))

        def choose(sender, args):
            selected = pick_executable()
            if selected:
                executable.text = selected

        browse.add_click(choose)
        body.children.append(browse)
    if kind == "device":
        interval.header = ui.create_text_block(t("community_interval"))
        interval.text = str(settings.get("interval", 5))
        body.children.append(interval)
        body.children.append(ui.create_text_block(t("community_device_dependency"), wrap=True, secondary=True))
    elif kind == "screenshot_full":
        output.header = ui.create_text_block(t("community_output"))
        output.text = settings.get("output_directory", str(Path.home() / "Pictures/YASB_Screenshots"))
        body.children.append(output)
        body.children.append(ui.create_text_block(t("community_screenshot_dependency"), wrap=True, secondary=True))
    elif kind == "screenshot_region":
        body.children.append(ui.create_text_block(t("community_region_dependency"), wrap=True, secondary=True))
    else:
        toggle.content = ui.create_text_block(t("community_toggle_tray"), wrap=True)
        toggle.is_checked = settings.get("toggle_tray", False)
        body.children.append(toggle)
        body.children.append(ui.create_text_block(t("community_proton_dependency"), wrap=True, secondary=True))
    status = ui.create_text_block("", wrap=True)
    body.children.append(status)
    dialog.content = body

    def closing(sender, args):
        if args.result != ContentDialogButton.PRIMARY:
            return
        try:
            options = build_community_options(
                kind,
                executable=executable.text.strip(),
                output_directory=output.text.strip(),
                interval=int(interval.text) if kind == "device" else 5,
                toggle_tray=bool(toggle.is_checked),
            )
            if original is not None:
                options = update_integration_options(original, options, kind)
            validate_options(template["type_path"], options)
            apply(options)
            app.mark_unsaved()
        except Exception as exc:
            args.cancel = True
            status.text = display_error(exc)

    dialog.add_closing(closing)
    dialog.add_closed(lambda s, e: refresh() if e.result == ContentDialogButton.PRIMARY else None)
    dialog.show_async()
