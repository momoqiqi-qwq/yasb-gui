"""Creation defaults preserve drafts, explicit customization and persistent assets."""

import copy
import re
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest
from core.application import ConfiguratorApp
from core.button_defaults import (
    APPS_CLASS,
    BEGIN,
    BUTTON_CLASS,
    CSS,
    ensure_button_css,
    image_label,
    prepare_button_options,
)
from core.button_icons import BUNDLE, bundled_icon, glyph_font, persistent_icon
from core.command_presets import command_button_templates, command_presets
from core.yasb_schema import make_defaults, validate_options, widget_schemas


@pytest.mark.parametrize("preset", command_button_templates(), ids=lambda preset: preset["id"])
def test_all_command_presets_have_persistent_icons_and_matching_style(preset, tmp_path):
    original = copy.deepcopy(preset["defaults"])
    options, styled = prepare_button_options(preset["type_path"], original, tmp_path)
    assert styled and BUTTON_CLASS in options["class_name"].split()
    validate_options(preset["type_path"], options)
    assert preset["defaults"] == original
    path = Path(re.search(r'src="([^"]+)"', options["label"])[1])
    assert path.is_relative_to(tmp_path) and path.exists()
    assert 'width="20" height="20"' in options["label"]
    assert not path.is_relative_to(BUNDLE)
    assert prepare_button_options(preset["type_path"], options, tmp_path) == (options, True)


def test_app_buttons_keep_commands_and_options(tmp_path):
    original = {
        "label": "",
        "class_name": "my-apps",
        "app_list": [{key: preset[key] for key in ("icon", "launch", "name")} for preset in command_presets()],
    }
    snapshot = copy.deepcopy(original)
    options, styled = prepare_button_options("yasb.applications.ApplicationsWidget", original, tmp_path)
    assert styled and options["class_name"] == f"my-apps {APPS_CLASS}"
    assert options["image_icon_size"] == 20
    assert original == snapshot
    for before, after in zip(original["app_list"], options["app_list"]):
        assert before["launch"] == after["launch"] and before["name"] == after["name"]
        assert Path(after["icon"]).is_file()
    validate_options("yasb.applications.ApplicationsWidget", options)


def test_existing_app_icons_and_explicit_size_are_preserved(tmp_path):
    previous = {"image_icon_size": 18, "app_list": [{"icon": "\uf269", "launch": "custom.exe"}]}
    options, styled = prepare_button_options("yasb.applications.ApplicationsWidget", previous, tmp_path, previous)
    assert styled and options["image_icon_size"] == 18
    assert options["app_list"] == previous["app_list"]
    assert not (tmp_path / "icons").exists()


def test_home_default_is_rasterized_and_boxed(tmp_path):
    name = "yasb.home.HomeWidget"
    original = make_defaults(widget_schemas()[name])
    options, styled = prepare_button_options(name, original, tmp_path)
    assert styled and "yasbgui-menu-icon" in options["label"] and "<img " in options["label"]
    validate_options(name, options)
    assert prepare_button_options(name, original, tmp_path, original) == (original, False)


@pytest.mark.parametrize("name", ["yasb.home.HomeWidget", "yasb.power_menu.PowerMenuWidget"])
def test_menu_buttons_with_text_labels_also_receive_frames(name, tmp_path):
    original = make_defaults(widget_schemas()[name])
    original["label"] = "打开菜单"
    options, styled = prepare_button_options(name, original, tmp_path)
    assert styled and options["label"] == original["label"]
    validate_options(name, options)


@pytest.mark.parametrize("label", ["文件管理器", "<span>中文名称</span>", "{data[message]}", "<span>{data}</span>"])
def test_text_and_dynamic_data_remain_text(label, tmp_path):
    assert image_label(label, tmp_path) == label
    assert not list(tmp_path.iterdir())


def test_custom_image_path_is_preserved(tmp_path):
    path = tmp_path / "custom.png"
    path.write_bytes(Path(bundled_icon()).read_bytes())
    assert persistent_icon(str(path), tmp_path) == str(path)
    assert not (tmp_path / "icons").exists()


def test_glyph_beside_plain_text_does_not_rasterize_the_text(tmp_path):
    result = image_label("\ue71a 启动菜单", tmp_path)
    assert "<img " in result and result.endswith(" 启动菜单")
    assert image_label("<span>\ue71a 启动菜单</span>", tmp_path) == "<span>\ue71a 启动菜单</span>"


def test_missing_image_and_unknown_glyph_are_not_silently_replaced(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        persistent_icon(str(tmp_path / "missing.png"), tmp_path)
    with pytest.raises(ValueError, match="choose an image"):
        glyph_font("\U0010ffff")


def test_assets_have_correct_png_dimensions():
    for path in BUNDLE.glob("*.png"):
        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == (48, 48)
    assert len(list(BUNDLE.glob("*.png"))) == 12


def test_generated_asset_tampering_is_not_overwritten(tmp_path):
    path = Path(persistent_icon(bundled_icon(), tmp_path))
    path.write_bytes(b"customized")
    with pytest.raises(ValueError, match="modified"):
        persistent_icon(bundled_icon(), tmp_path)
    assert path.read_bytes() == b"customized"


def test_style_block_is_idempotent_and_preserves_user_overrides():
    existing = ".yasbgui-button .widget-container {border-radius: 18px}"
    combined = ensure_button_css(existing)
    assert combined == CSS + "\n" + existing
    assert ensure_button_css(combined.replace("12px", "15px")) == combined.replace("12px", "15px")
    with pytest.raises(ValueError, match="incomplete"):
        ensure_button_css(BEGIN)


@pytest.mark.parametrize("ready", [False, True])
def test_styles_are_staged_without_writing_and_preserve_editor_undo(ready, tmp_path):
    path = tmp_path / "styles.css"
    path.write_text(".user {color: red}", encoding="utf-8")
    scripts, dirty = [], []
    page = SimpleNamespace(
        _draft_content=".draft {color: blue}",
        _pending_content=None,
        _editor_ready=ready,
        _webview=SimpleNamespace(execute_script_async=scripts.append),
    )
    app = SimpleNamespace(
        _styles_page=page,
        _config_manager=SimpleNamespace(load_styles=lambda: path.read_text()),
        mark_unsaved=lambda *args, **kwargs: dirty.append((args, kwargs)),
    )
    ConfiguratorApp.stage_button_styles(app)
    assert page._draft_content == CSS + "\n.draft {color: blue}"
    assert page._pending_content == page._draft_content
    assert path.read_text() == ".user {color: red}"
    assert len(dirty) == 1
    assert bool(scripts) == ready
    if ready:
        assert scripts[0].startswith("setFormattedContent(")
    ConfiguratorApp.stage_button_styles(app)
    assert len(dirty) == 1


def test_polling_information_widgets_do_not_become_buttons(tmp_path):
    options = {"label": "{data}", "callbacks": {"on_left": "toggle_label"}}
    assert prepare_button_options("yasb.custom.CustomWidget", options, tmp_path) == (options, False)
