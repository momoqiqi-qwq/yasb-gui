"""Validated widget actions shared by single-item and batch UI commands."""

from copy import deepcopy

POSITIONS = ("left", "center", "right")


def _independent_copy(value):
    """Preserve round-trip YAML while letting copies receive their own anchors."""
    result = deepcopy(value)
    seen = set()

    def clear_anchors(item):
        if id(item) in seen:
            return
        seen.add(id(item))
        if hasattr(item, "yaml_set_anchor"):
            item.yaml_set_anchor(None)
        if isinstance(item, dict):
            for key, child in item.items():
                clear_anchors(key)
                clear_anchors(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                clear_anchors(child)

    clear_anchors(result)
    return result


def _validated_context(config_manager, bar_name, widget_names, allow_no_bar=False):
    config = config_manager.config
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a mapping")
    widgets, bars = config.get("widgets", {}), config.get("bars", {})
    if not isinstance(widgets, dict) or not isinstance(bars, dict):
        raise ValueError("Widgets and bars must be mappings")
    if allow_no_bar and bar_name is None:
        bar, positions = None, {}
    else:
        if not isinstance(bar_name, str) or bar_name not in bars or not isinstance(bars[bar_name], dict):
            raise ValueError("Select an existing bar")
        bar = bars[bar_name]
        positions = bar.get("widgets", {})
    if not isinstance(positions, dict):
        raise ValueError("Bar widgets must be a mapping")
    for position, names in positions.items():
        if position not in POSITIONS or not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ValueError("Bar widget positions must contain lists of names")
    if not isinstance(widget_names, (list, tuple)):
        raise ValueError("Widget selection must be a list of names")
    names = []
    seen = set()
    for name in widget_names:
        if not isinstance(name, str) or not name or name not in widgets or not isinstance(widgets[name], dict):
            raise ValueError(f"Unknown or invalid widget: {name}")
        if name not in seen:
            names.append(name)
            seen.add(name)
    return widgets, bar, positions, names


def _reference_index(positions, names):
    references = {name: [] for name in names}
    for position in POSITIONS:
        for index, name in enumerate(positions.get(position, [])):
            if name in references:
                references[name].append((position, index))
    return references


def apply_widget_action(
    config_manager, bar_name, widget_names, action, position=None, *, source_position=None
) -> list[str]:
    """Apply a batch once, after validating every input and preparing all copies.

    Duplicate returns new names; move/disable return selected names whose bar
    references changed. Other bars and the source widget settings stay intact.
    A source_position limits a single-item command to its first reference in
    that position; batch commands omit it and act on every selected reference.
    Invalid inputs raise ValueError before any configuration changes are made.
    """
    if action not in ("duplicate", "disable", "move"):
        raise ValueError("Unknown widget action")
    if action == "move" and position not in POSITIONS:
        raise ValueError("Select a valid widget position")
    if action != "move" and position is not None:
        raise ValueError("This action does not accept a target position")
    widgets, bar, original, names = _validated_context(
        config_manager, bar_name, widget_names, allow_no_bar=action == "duplicate"
    )
    if source_position is not None:
        if source_position not in POSITIONS or len(names) != 1 or names[0] not in original.get(source_position, []):
            raise ValueError("Select an existing widget reference")
        if action == "move" and source_position == position:
            return []
    if not names:
        return []

    updated = _independent_copy(original)
    # A YAML alias may share a list between positions; an action must address
    # each position independently rather than mutate the alias twice.
    for key, values in original.items():
        updated[key] = _independent_copy(values)
    selected = set(names)
    copies = {}
    renamed = {}
    if action == "duplicate":
        existing = set(widgets)
        for name in names:
            counter = 1
            while (new_name := f"{name}_{counter}") in existing:
                counter += 1
            existing.add(new_name)
            renamed[name] = new_name
            copies[new_name] = _independent_copy(widgets[name])
        if source_position is not None:
            values = updated[source_position]
            values.insert(values.index(names[0]) + 1, renamed[names[0]])
        else:
            for values in updated.values():
                for index in range(len(values) - 1, -1, -1):
                    if values[index] in renamed:
                        values.insert(index + 1, renamed[values[index]])
        changed = list(copies)
    else:
        if source_position is not None:
            updated[source_position].remove(names[0])
            if action == "move":
                target = updated.setdefault(position, [])
                if names[0] not in target:
                    target.append(names[0])
        else:
            for values in updated.values():
                for index in range(len(values) - 1, -1, -1):
                    if values[index] in selected:
                        del values[index]
            if action == "move":
                updated.setdefault(position, []).extend(names)
        before = _reference_index(original, names)
        after = _reference_index(updated, names)
        changed = [name for name in names if before[name] != after[name]]
        if not changed:
            return []

    replacement_bar = None
    if updated != original:
        # Whole bars can be YAML aliases as well. Copy the selected bar so the
        # operation cannot silently change another monitor's configuration.
        replacement_bar = _independent_copy(bar)
        replacement_bar["widgets"] = updated

    # All validation and potentially failing deep copies precede this commit.
    if updated != original:
        config_manager.config["bars"][bar_name] = replacement_bar
    widgets.update(copies)
    return changed
