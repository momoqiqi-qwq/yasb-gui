"""Application entries and native Explorer selection for the apps widget."""

import base64
import copy
import ctypes
from ctypes import wintypes
from pathlib import Path

from core.button_icons import bundled_icon
from core.localization import t
from core.win32_types import OFN_EXPLORER, OPENFILENAMEW

APPS_TYPE = "yasb.applications.ApplicationsWidget"


def parse_selection(raw):
    parts = raw.rstrip("\0").split("\0") if raw.rstrip("\0") else []
    if len(parts) < 2:
        return parts
    return [str(Path(parts[0]) / name) for name in parts[1:]]


def pick_files(*, icons=False):
    buffer = ctypes.create_unicode_buffer(65536)
    dialog = OPENFILENAMEW()
    dialog.lStructSize = ctypes.sizeof(dialog)
    ctypes.windll.user32.GetActiveWindow.restype = wintypes.HWND
    dialog.hwndOwner = ctypes.windll.user32.GetActiveWindow()
    dialog.lpstrFilter = (
        "Images (*.png;*.ico;*.jpg;*.jpeg;*.bmp)\0*.png;*.ico;*.jpg;*.jpeg;*.bmp\0\0"
        if icons
        else "Applications (*.exe;*.lnk;*.url)\0*.exe;*.lnk;*.url\0\0"
    )
    dialog.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    dialog.nMaxFile = len(buffer)
    dialog.lpstrTitle = t("apps_choose_icon" if icons else "apps_browse")
    # NOCHANGEDIR and NODEREFERENCELINKS preserve shortcut arguments and working directory.
    dialog.Flags = OFN_EXPLORER | 0x1000 | 0x800 | 0x8 | 0x100000
    if not icons:
        dialog.Flags |= 0x200  # ALLOWMULTISELECT
    api = ctypes.windll.comdlg32
    api.GetOpenFileNameW.argtypes = [ctypes.POINTER(OPENFILENAMEW)]
    api.GetOpenFileNameW.restype = wintypes.BOOL
    if not api.GetOpenFileNameW(ctypes.byref(dialog)):
        code = api.CommDlgExtendedError()
        if code:
            raise OSError(f"GetOpenFileNameW: 0x{code:04x}")
        return []
    return parse_selection(buffer[:])


def application_entry(filename):
    path = Path(filename)
    if path.suffix.lower() not in (".exe", ".lnk", ".url") or not path.is_file():
        raise ValueError(t("apps_invalid_file"))
    # YASB splits launch strings on whitespace. Encode the literal path to keep
    # spaces, apostrophes and shell metacharacters intact through that runtime.
    literal = str(path.resolve()).replace("'", "''")
    script = f"Start-Process -FilePath '{literal}'"
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return {
        "name": path.stem,
        "icon": bundled_icon("notepad"),
        "launch": f"powershell.exe -NoProfile -EncodedCommand {encoded}",
    }


def update_app_list(original, entries):
    result = copy.deepcopy(original)
    result["app_list"] = copy.deepcopy(entries)
    return result
