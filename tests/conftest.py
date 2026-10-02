"""Keep preferences and automatic snapshots out of the user's profile during tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    from core import config_manager, preferences

    monkeypatch.setattr(preferences, "APP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(preferences, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(preferences, "_preferences", None)
    monkeypatch.setattr(config_manager, "APP_DATA_DIR", str(tmp_path))
