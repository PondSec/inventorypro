"""Customization business helpers."""

from __future__ import annotations

from typing import Any


def compute_customization_diff(old: Any, new: Any, path: str = "") -> list[dict[str, Any]]:
    """Return a stable, field-level diff for an auditable configuration revision."""
    changes: list[dict[str, Any]] = []
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            next_path = f"{path}.{key}" if path else key
            changes.extend(compute_customization_diff(old.get(key), new.get(key), next_path))
    elif old != new:
        changes.append({"path": path, "from": old, "to": new})
    return changes
