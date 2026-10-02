"""
App preferences - storing UI settings like language, theme, etc.

Stored in JSON in the app data directory, separate from YASB config.
"""

import json
import os

from core.constants import APP_DATA_DIR, DEFAULT_SETTINGS, SETTINGS_PATH
from core.file_io import atomic_write_text
from core.logger import error

_preferences = None


class Preferences:
    """Simple key-value storage for app settings (not YASB config)."""

    def __init__(self):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        self._settings_path = SETTINGS_PATH
        self._settings = DEFAULT_SETTINGS.copy()
        self._load()

    def _load(self) -> None:
        try:
            if self._settings_path.exists():
                with open(self._settings_path, encoding="utf-8") as f:
                    saved = json.load(f)
                    self._settings = {**DEFAULT_SETTINGS, **(saved if isinstance(saved, dict) else {})}
        except Exception as e:
            error(f"Error loading app settings: {e}")
            self._settings = DEFAULT_SETTINGS.copy()

    def _save(self) -> None:
        try:
            atomic_write_text(self._settings_path, json.dumps(self._settings, indent=2, ensure_ascii=False))
        except Exception as e:
            error(f"Error saving app settings: {e}")

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def set(self, key: str, value) -> None:
        self._settings[key] = value
        self._save()


def get_preferences() -> Preferences:
    """Get the preferences instance (creates if needed)."""
    global _preferences
    if _preferences is None:
        _preferences = Preferences()
    return _preferences


def editor_options():
    """Shared Monaco options for CSS and widget YAML editors."""
    prefs = get_preferences()
    tab_size = prefs.get("editor_tab_size", 2)
    return {
        "wordWrap": prefs.get("editor_word_wrap", "on"),
        "minimap": {"enabled": bool(prefs.get("editor_minimap", False))},
        "lineNumbers": prefs.get("editor_line_numbers", "on"),
        "tabSize": tab_size if tab_size in (2, 4, 8) else 2,
        "insertSpaces": True,
        "detectIndentation": False,
        "renderWhitespace": prefs.get("editor_render_whitespace", "selection"),
        "bracketPairColorization": {"enabled": bool(prefs.get("editor_bracket_colors", True))},
    }
