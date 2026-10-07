"""Stable PNG icons; generated assets never reference a frozen extraction cache."""

import ctypes
import hashlib
import os
import shutil
import subprocess
import tempfile
from ctypes import wintypes
from pathlib import Path

BUNDLE = Path(__file__).parent / "button_icons"


def bundled_icon(name="terminal"):
    path = BUNDLE / f"{name}.png"
    if not path.is_file():
        raise FileNotFoundError(f"Missing button icon: {path}")
    return path.as_posix()


def glyph_font(text):
    """Reject missing glyphs rather than silently producing a fallback rectangle."""
    if not text or len(text) > 8 or any(ord(char) > 0xFFFF for char in text):
        raise ValueError("Please choose an image for this icon")
    gdi = ctypes.windll.gdi32
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
    gdi.CreateFontW.restype = wintypes.HANDLE
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.GetGlyphIndicesW.argtypes = [
        wintypes.HDC,
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.POINTER(wintypes.WORD),
        wintypes.DWORD,
    ]
    gdi.GetGlyphIndicesW.restype = wintypes.DWORD
    gdi.GetTextFaceW.argtypes = [wintypes.HDC, ctypes.c_int, wintypes.LPWSTR]
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    # Nerd Font's typographic family differs from its legacy GDI name on some builds.
    families = [
        "JetBrainsMono Nerd Font",
        "JetBrainsMono NF",
        "Segoe Fluent Icons",
        "Segoe MDL2 Assets",
        "Segoe UI Symbol",
        "Segoe UI",
    ]
    dc = gdi.CreateCompatibleDC(None)
    if not dc:
        raise OSError("CreateCompatibleDC failed")
    try:
        for family in families:
            font = gdi.CreateFontW(-48, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 4, 0, family)
            if not font:
                continue
            previous = gdi.SelectObject(dc, font)
            try:
                actual = ctypes.create_unicode_buffer(128)
                gdi.GetTextFaceW(dc, len(actual), actual)
                indices = (wintypes.WORD * len(text))()
                status = gdi.GetGlyphIndicesW(dc, text, len(text), indices, 1)
                if actual.value.casefold() == family.casefold() and status != 0xFFFFFFFF and 0xFFFF not in indices:
                    return family
            finally:
                gdi.SelectObject(dc, previous)
                gdi.DeleteObject(font)
    finally:
        gdi.DeleteDC(dc)
    raise ValueError("No installed font contains this icon; please choose an image")


def _renderer():
    from core.community_widgets import EXTENSIONS_DIR

    return EXTENSIONS_DIR / "button-icon.ps1"


def render_glyph(text, directory):
    family = glyph_font(text)
    digest = hashlib.sha256(("v1\0" + family + "\0" + text).encode()).hexdigest()[:24]
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"glyph-{digest}.png"
    if target.is_file():
        return target.as_posix()
    fd, temporary = tempfile.mkstemp(dir=directory, suffix=".png")
    os.close(fd)
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(_renderer()),
                "-Text",
                text,
                "-FontFamily",
                family,
                "-OutputFile",
                temporary,
            ],
            capture_output=True,
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode or Path(temporary).read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Could not render this icon; please choose an image")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target.as_posix()


def persistent_icon(value, config_directory):
    directory = Path(config_directory) / "icons/yasb-gui"
    source = Path(value)
    if source.is_file():
        if not source.resolve().is_relative_to(BUNDLE.resolve()):
            return value  # Keep explicitly chosen user image paths.
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()[:24]
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{source.stem}-{digest}.png"
        if target.exists() and target.read_bytes() != data:
            raise ValueError("Generated icon was modified; choose an image to retain that customization")
        if not target.exists():
            shutil.copyfile(source, target)
        return target.as_posix()
    if source.suffix.lower() in (".png", ".ico", ".jpg", ".jpeg", ".bmp"):
        raise ValueError(f"Icon image does not exist: {value}")
    return render_glyph(value, directory)
