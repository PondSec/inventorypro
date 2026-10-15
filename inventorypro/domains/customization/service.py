"""Customization business helpers."""

from __future__ import annotations

import json
from typing import Any


def clone_customization(data: Any) -> Any:
    """Create a JSON-compatible deep copy of a customization payload."""
    return json.loads(json.dumps(data))


def deep_merge(base: Any, override: Any) -> Any:
    """Merge nested customization objects without mutating either input."""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override if override is not None else base
    merged = {**base}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def migrate_customization(data: Any, *, default_customization: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy customization payloads to the current schema."""
    if not isinstance(data, dict):
        return clone_customization(default_customization)

    if ("branding" in data or "formStyle" in data) and "baseTokens" not in data:
        migrated = clone_customization(default_customization)
        branding = data.get("branding", {})
        form_style = data.get("formStyle", {})
        migrated["branding"]["name"] = branding.get("name", migrated["branding"]["name"])
        migrated["branding"]["tagline"] = branding.get("tagline", migrated["branding"]["tagline"])
        migrated["branding"]["logoDataUrl"] = branding.get("logoDataUrl", migrated["branding"]["logoDataUrl"])
        migrated["branding"]["logoLightDataUrl"] = branding.get(
            "logoLightDataUrl", migrated["branding"]["logoLightDataUrl"]
        )
        migrated["branding"]["logoDarkDataUrl"] = branding.get(
            "logoDarkDataUrl", migrated["branding"]["logoDarkDataUrl"]
        )
        migrated["branding"]["faviconDataUrl"] = branding.get(
            "faviconDataUrl", migrated["branding"]["faviconDataUrl"]
        )
        migrated["branding"]["authBackgroundDataUrl"] = branding.get(
            "authBackgroundDataUrl", migrated["branding"]["authBackgroundDataUrl"]
        )
        migrated["baseTokens"]["colors"]["primary"] = branding.get(
            "primary", migrated["baseTokens"]["colors"]["primary"]
        )
        migrated["baseTokens"]["colors"]["accent"] = branding.get(
            "accent", migrated["baseTokens"]["colors"]["accent"]
        )
        migrated["baseTokens"]["colors"]["background"] = branding.get(
            "background", migrated["baseTokens"]["colors"]["background"]
        )
        migrated["baseTokens"]["spacing"]["radius"]["md"] = branding.get(
            "radius", migrated["baseTokens"]["spacing"]["radius"]["md"]
        )
        migrated["layoutPrefs"]["density"] = branding.get(
            "density", migrated["layoutPrefs"]["density"]
        )
        migrated["componentOverrides"]["button"]["primary"]["background"] = form_style.get(
            "buttonColor", migrated["componentOverrides"]["button"]["primary"]["background"]
        )
        migrated["componentOverrides"]["button"]["primary"]["text"] = form_style.get(
            "buttonText", migrated["componentOverrides"]["button"]["primary"]["text"]
        )
        migrated["componentOverrides"]["input"]["background"] = form_style.get(
            "inputBackground", migrated["componentOverrides"]["input"]["background"]
        )
        migrated["componentOverrides"]["input"]["border"] = form_style.get(
            "inputBorder", migrated["componentOverrides"]["input"]["border"]
        )
        migrated["layoutPrefs"]["formSpacing"] = form_style.get(
            "spacing", migrated["layoutPrefs"]["formSpacing"]
        )
        return migrated

    merged = deep_merge(clone_customization(default_customization), data)
    merged["schemaVersion"] = 1
    return merged


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
