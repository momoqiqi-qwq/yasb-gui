"""Disk fingerprints, bounded diffs and checked access to configuration snapshots."""

import difflib
import hashlib
from pathlib import Path

from core.localization import t


def fingerprint(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


class ExternalFileChange(OSError):
    def __init__(self, filename):
        super().__init__(t("history_external_changed", file=filename))
        self.filename = filename


def snapshot_path(manager, name):
    root = manager.backup_directory.resolve()
    path = root / name
    if Path(name).name != name or path.resolve().parent != root or path.is_symlink() or not path.is_file():
        raise ValueError(t("history_invalid_snapshot"))
    if not any(name.startswith(file + ".") for file in ("config.yaml", "styles.css")) or not name.endswith(".bak"):
        raise ValueError(t("history_invalid_snapshot"))
    return path


def list_snapshots(manager):
    result = []
    if not manager.backup_directory.exists():
        return result
    for path in sorted(manager.backup_directory.glob("*.bak"), reverse=True):
        try:
            checked = snapshot_path(manager, path.name)
            result.append(
                {
                    "name": path.name,
                    "size": checked.stat().st_size,
                    "file": "config.yaml" if path.name.startswith("config.yaml.") else "styles.css",
                }
            )
        except ValueError:
            continue
    return sorted(result, key=lambda row: row["name"].split(".", 2)[-1], reverse=True)


def unified_diff(before, after, before_name="disk", after_name="backup"):
    lines = list(
        difflib.unified_diff(
            before.splitlines(), after.splitlines(), fromfile=before_name, tofile=after_name, lineterm=""
        )
    )
    return "\n".join(lines[:2000]) or t("history_no_difference")


def restore_snapshot(manager, name, expected_disk, expected_snapshot):
    """Reject changes since preview and preserve current content regardless of backup preferences."""
    path = snapshot_path(manager, name)
    filename = "config.yaml" if name.startswith("config.yaml.") else "styles.css"
    target = Path(manager.config_path if filename == "config.yaml" else manager.styles_path)
    if fingerprint(target) != expected_disk:
        raise ExternalFileChange(filename)
    if fingerprint(path) != expected_snapshot:
        raise ValueError(t("history_snapshot_changed"))
    content = path.read_text(encoding="utf-8")
    if filename == "config.yaml":
        from core.advanced_config import parse_mapping

        mapping = parse_mapping(content)
        if not isinstance(mapping.get("bars", {}), dict) or not isinstance(mapping.get("widgets", {}), dict):
            raise ValueError(t("history_invalid_snapshot"))
    manager._write_with_backup(target, content, approved={filename: expected_disk}, force_backup=True)
    return filename
