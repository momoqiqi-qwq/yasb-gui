"""Pinned community executable and independently written companion scripts."""

import base64
import copy
import hashlib
import os
import re
import subprocess
from pathlib import Path

from core.constants import APP_BASE_PATH, APP_DATA_DIR
from core.localization import t
from core.yasb_schema import make_defaults, widget_schemas

EXTENSIONS_DIR = APP_BASE_PATH / "app" / "extensions"
DEVICE_SHA256 = "0e85bd331a3f847eef7280282a6267de58a107b96bb50b4387302d6a3d74652d"
SPECS = {
    "community_device": ("device", "https://github.com/Hyacinthe-primus/Project_MochaGlass"),
    "community_screenshot_full": ("screenshot_full", "https://github.com/Lerakei-0/Personnal-YASB-Scripts"),
    "community_screenshot_region": ("screenshot_region", "https://github.com/Lerakei-0/Personnal-YASB-Scripts"),
    "community_protonvpn": ("protonvpn", "https://github.com/Lerakei-0/Personnal-YASB-Scripts"),
}


def community_templates():
    return [
        {
            "id": key,
            "community_kind": kind,
            "name": t(key),
            "description": t(key + "_desc"),
            "category": t("community_category"),
            "type_path": "yasb.custom.CustomWidget",
            "defaults": {},
            "doc_link": url,
        }
        for key, (kind, url) in SPECS.items()
    ]


def installed_asset(relative):
    """Install a content-addressed copy, leaving files referenced by old configs intact."""
    source = EXTENSIONS_DIR / relative
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if relative == "vendor/device_status.exe" and digest != DEVICE_SHA256:
        raise ValueError(t("community_checksum_error"))
    destination = Path(APP_DATA_DIR) / "extensions" / digest / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError(t("community_checksum_error"))
    else:
        # The shared atomic writer handles text; these assets can contain PE bytes.
        import tempfile

        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        try:
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    if relative == "vendor/device_status.exe":
        license_file = destination.parent / "MochaGlass-LICENSE.md"
        atomic_text = (EXTENSIONS_DIR / "vendor/MochaGlass-LICENSE.md").read_text(encoding="utf-8")
        # Always retain upstream notice beside the installed executable.
        from core.file_io import atomic_write_text

        atomic_write_text(license_file, atomic_text)
    return destination


def powershell_command(script, *arguments):
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        raise ValueError(t("community_powershell_missing"))
    return subprocess.list2cmdline(
        [
            str(powershell),
            "-NoProfile",
            "-STA",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *map(str, arguments),
        ]
    )


def find_protonvpn():
    candidates = []
    for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if root:
            candidates.extend((Path(root) / "Proton/VPN").glob("v*/ProtonVPN.Client.exe"))
    return str(max(candidates, key=lambda p: p.stat().st_mtime)) if candidates else ""


def build_community_options(kind, executable="", output_directory="", interval=5, toggle_tray=False):
    options = make_defaults(widget_schemas()["yasb.custom.CustomWidget"])
    options.update(class_name="community-widget", label_alt="{data}")
    options["exec_options"].update(
        run_once=True, run_cmd=None, return_format="string", encoding="utf-8", use_shell=False
    )
    if kind == "device":
        if not 5 <= int(interval) <= 3600:
            raise ValueError(t("community_interval_error"))
        path = Path(executable) if executable else installed_asset("vendor/device_status.exe")
        if not path.is_file() or path.suffix.lower() != ".exe":
            raise ValueError(t("community_executable_missing"))
        options.update(
            label="USB {data[compact]}",
            label_alt="{data[count]} " + t("community_connected"),
            tooltip=True,
            tooltip_label="{data[tooltip]}",
            label_placeholder=t("template_loading"),
        )
        # CustomWidget splits polling commands on spaces before spawning them.
        # An encoded command keeps paths containing spaces/unicode in one argument.
        escaped_path = str(path.resolve()).replace("'", "''")
        code = "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); & '" + escaped_path + "'"
        encoded = base64.b64encode(code.encode("utf-16-le")).decode("ascii")
        options["exec_options"].update(
            run_cmd="powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand " + encoded,
            run_once=False,
            run_interval=int(interval) * 1000,
            return_format="json",
            use_shell=False,
        )
    elif kind in ("screenshot_full", "screenshot_region"):
        folder = output_directory or str(Path.home() / "Pictures/YASB_Screenshots")
        if kind == "screenshot_full" and not Path(folder).is_absolute():
            raise ValueError(t("community_folder_error"))
        options.update(
            label=t("community_capture"),
            label_alt=t("community_capture"),
            tooltip=True,
            tooltip_label=t(
                "community_screenshot_full_desc" if kind == "screenshot_full" else "community_screenshot_region_desc"
            ),
        )
        options["callbacks"]["on_left"] = "exec " + powershell_command(
            installed_asset("screenshot.ps1"),
            "-Mode",
            "Full" if kind == "screenshot_full" else "Region",
            "-OutputDirectory",
            str(Path(folder).resolve()),
        )
    elif kind == "protonvpn":
        path = Path(executable)
        if not path.is_file() or path.suffix.lower() != ".exe":
            raise ValueError(t("community_executable_missing"))
        options.update(label="VPN", label_alt="Proton VPN", tooltip=True, tooltip_label=t("community_protonvpn_desc"))
        options["callbacks"]["on_left"] = "exec " + powershell_command(
            installed_asset("protonvpn.ps1"),
            "-Executable",
            path.resolve(),
            "-Mode",
            "ToggleTray" if toggle_tray else "Open",
        )
    else:
        raise ValueError(kind)
    return options


def pick_executable():
    import ctypes
    from ctypes import wintypes

    from core.win32_types import OFN_EXPLORER, OPENFILENAMEW

    buffer = ctypes.create_unicode_buffer(32768)
    dialog = OPENFILENAMEW()
    dialog.lStructSize = ctypes.sizeof(dialog)
    ctypes.windll.user32.GetActiveWindow.restype = wintypes.HWND
    dialog.hwndOwner = ctypes.windll.user32.GetActiveWindow()
    dialog.lpstrFilter = "Executable (*.exe)\0*.exe\0\0"
    dialog.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    dialog.nMaxFile = len(buffer)
    dialog.lpstrTitle = t("community_choose_executable")
    dialog.Flags = OFN_EXPLORER | 0x1000 | 0x800 | 0x8  # FILEMUSTEXIST, PATHMUSTEXIST, NOCHANGEDIR
    return buffer.value if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(dialog)) else None


def integration_settings(widget):
    """Recognize our commands by structure, never execute them to discover settings."""
    if widget.get("type") != "yasb.custom.CustomWidget":
        return None
    options = widget.get("options", {})
    execution = options.get("exec_options", {})
    command = execution.get("run_cmd") or ""
    if "-EncodedCommand " in command:
        try:
            decoded = base64.b64decode(command.rsplit(" ", 1)[-1], validate=True).decode("utf-16-le")
            match = re.search(r"& '((?:[^']|'')*)'$", decoded)
            if match and decoded.startswith("[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); & '"):
                return {
                    "kind": "device",
                    "executable": match[1].replace("''", "'"),
                    "interval": execution.get("run_interval", 5000) // 1000,
                }
        except ValueError, UnicodeError:
            pass
    callback = options.get("callbacks", {}).get("on_left", "")
    tokens = [part.strip('"') for part in re.findall(r'".+?"|[^ ]+', callback)]
    if "-File" not in tokens:
        return None

    def argument(key, fallback=""):
        index = tokens.index(key) + 1 if key in tokens else len(tokens)
        return tokens[index] if index < len(tokens) else fallback

    script = Path(argument("-File")).name.lower()
    mode = argument("-Mode")
    if script == "screenshot.ps1" and mode in ("Full", "Region"):
        return {
            "kind": "screenshot_full" if mode == "Full" else "screenshot_region",
            "output_directory": argument("-OutputDirectory"),
            "script": argument("-File"),
        }
    if script == "protonvpn.ps1" and mode in ("Open", "ToggleTray"):
        return {
            "kind": "protonvpn",
            "executable": argument("-Executable"),
            "toggle_tray": mode == "ToggleTray",
            "script": argument("-File"),
        }
    return None


def update_integration_options(original, generated, kind):
    """Keep labels, styles and user callbacks when changing only integration settings."""
    options = copy.deepcopy(original)
    if kind == "device":
        execution = options.setdefault("exec_options", {})
        for key in ("run_cmd", "run_once", "run_interval", "return_format", "encoding", "use_shell"):
            execution[key] = generated["exec_options"][key]
    else:
        options.setdefault("callbacks", {})["on_left"] = generated["callbacks"]["on_left"]
        options.setdefault("exec_options", {})["use_shell"] = False
    return options


def integration_health(settings):
    issues = []
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        issues.append(t("community_powershell_missing"))
    for key in ("executable", "script"):
        value = settings.get(key)
        if value and not Path(value).is_file():
            issues.append(t("community_missing_file", file=value))
    if settings.get("kind") == "device":
        path = Path(settings.get("executable", ""))
        if path.is_file() and path.name == "device_status.exe":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != DEVICE_SHA256:
                issues.append(t("community_checksum_error"))
    elif settings.get("kind") == "screenshot_full":
        folder = Path(settings.get("output_directory", ""))
        if not folder.is_absolute() or (folder.exists() and not folder.is_dir()):
            issues.append(t("community_folder_error"))
    return issues
