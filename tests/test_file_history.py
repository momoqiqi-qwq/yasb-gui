"""Conflict checks and restore safety with real temporary files."""

import os
from pathlib import Path

import pytest
from core import file_io
from core.config_manager import ConfigManager
from core.file_history import ExternalFileChange, fingerprint, list_snapshots, restore_snapshot
from core.preferences import get_preferences


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("YASB_CONFIG_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("# original\nbars: {}\nwidgets: {}\n", encoding="utf-8")
    (tmp_path / "styles.css").write_text("old css", encoding="utf-8")
    result = ConfigManager()
    result.load_config()
    result.load_styles()
    return result


@pytest.mark.parametrize("filename", ["config.yaml", "styles.css"])
def test_external_edits_do_not_get_overwritten(manager, filename):
    path = Path(manager.config_path if filename == "config.yaml" else manager.styles_path)
    path.write_text("outside edits", encoding="utf-8")
    ok = manager.save_config() if filename == "config.yaml" else manager.save_styles("GUI edits")
    assert not ok
    assert path.read_text() == "outside edits"
    assert manager.last_conflict == filename


def test_same_size_and_mtime_changes_are_detected(manager):
    path = Path(manager.styles_path)
    stat = path.stat()
    path.write_text("new css")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert "styles.css" in manager.external_changes(["styles.css"])


def test_approval_is_for_exact_reviewed_version(manager):
    path = Path(manager.styles_path)
    path.write_text("external v1")
    reviewed = {"styles.css": fingerprint(path)}
    path.write_text("external v2")
    assert not manager.save_styles("GUI", approved=reviewed)
    assert path.read_text() == "external v2"
    assert manager.save_styles("GUI", approved={"styles.css": fingerprint(path)})
    assert any(p.read_text() == "external v2" for p in manager.backup_directory.glob("styles.css.*.bak"))


def test_changes_during_backup_are_rechecked(manager, monkeypatch):
    from core import config_manager

    def edit_during_backup(source, target):
        Path(source).write_text("changed during backup")

    monkeypatch.setattr(config_manager.shutil, "copy2", edit_during_backup)
    assert not manager.save_styles("GUI")
    assert Path(manager.styles_path).read_text() == "changed during backup"


def test_deleted_file_requires_explicit_approval(manager):
    Path(manager.styles_path).unlink()
    assert not manager.save_styles("GUI")
    assert manager.save_styles("GUI", approved={"styles.css": None})


def test_restore_backs_up_even_if_automatic_backup_is_off(manager):
    assert manager.save_styles("new css")
    entry = next(row for row in list_snapshots(manager) if row["file"] == "styles.css")
    snapshot = manager.backup_directory / entry["name"]
    get_preferences().set("backup_before_save", False)
    restore_snapshot(manager, entry["name"], fingerprint(manager.styles_path), fingerprint(snapshot))
    assert Path(manager.styles_path).read_text() == "old css"
    assert any(p.read_text() == "new css" for p in manager.backup_directory.glob("styles.css.*.bak"))


def test_restore_rejects_disk_changes_after_preview(manager):
    assert manager.save_styles("new")
    entry = list_snapshots(manager)[0]
    version = fingerprint(manager.styles_path)
    source = manager.backup_directory / entry["name"]
    Path(manager.styles_path).write_text("outside")
    with pytest.raises(ExternalFileChange):
        restore_snapshot(manager, entry["name"], version, fingerprint(source))
    assert Path(manager.styles_path).read_text() == "outside"


def test_corrupt_yaml_snapshot_cannot_replace_valid_config(manager):
    manager.backup_directory.mkdir(parents=True)
    name = "config.yaml.20261003-000000.bak"
    snapshot = manager.backup_directory / name
    snapshot.write_text("bars: [broken", encoding="utf-8")
    before = Path(manager.config_path).read_bytes()
    with pytest.raises(Exception):
        restore_snapshot(manager, name, fingerprint(manager.config_path), fingerprint(snapshot))
    assert Path(manager.config_path).read_bytes() == before


def test_restore_failure_retains_disk_file_and_snapshot(manager, monkeypatch):
    manager.save_styles("new")
    entry = list_snapshots(manager)[0]
    source = manager.backup_directory / entry["name"]
    monkeypatch.setattr(file_io.os, "replace", lambda *args: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(PermissionError):
        restore_snapshot(manager, entry["name"], fingerprint(manager.styles_path), fingerprint(source))
    assert Path(manager.styles_path).read_text() == "new"
    assert source.exists()


def test_snapshot_changed_after_preview_is_rejected(manager):
    manager.save_styles("new")
    entry = list_snapshots(manager)[0]
    source = manager.backup_directory / entry["name"]
    version = fingerprint(source)
    source.write_text("modified backup")
    with pytest.raises(ValueError):
        restore_snapshot(manager, entry["name"], fingerprint(manager.styles_path), version)


def test_backup_listing_ignores_unrelated_files_and_traversal(manager, tmp_path):
    manager.save_styles("new")
    (manager.backup_directory / "other.bak").write_text("ignore")
    assert len(list_snapshots(manager)) == 1
    outside = tmp_path / "config.yaml.fake.bak"
    outside.write_text("outside")
    with pytest.raises(ValueError):
        restore_snapshot(manager, str(outside), fingerprint(manager.config_path), fingerprint(outside))
