"""Validation and normalization for signed automatic-update policies."""

from __future__ import annotations

import re
from typing import Any, Mapping


MAINTENANCE_WINDOW_PATTERN = re.compile(
    r"^(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)(?::(?P<second>[0-5]\d))?$"
)
MIN_CHECK_INTERVAL_MINUTES = 15
MAX_CHECK_INTERVAL_MINUTES = 1440


def normalize_maintenance_window(value: Any) -> str | None:
    """Normalize a minute-precise local maintenance time to ``HH:MM``."""
    candidate = str(value or "").strip()
    match = MAINTENANCE_WINDOW_PATTERN.fullmatch(candidate)
    if not match or match.group("second") not in {None, "00"}:
        return None
    return f"{int(match.group('hour')):02d}:{match.group('minute')}"


def normalize_update_settings(
    updates: Mapping[str, Any],
    default_updates: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return normalized update settings and field-level validation errors."""
    normalized = dict(updates)
    errors: dict[str, str] = {}
    auto_update_enabled = bool(updates.get("autoUpdateEnabled"))
    update_channel = str(updates.get("channel") or "").strip().lower()
    update_interval = updates.get("checkIntervalMinutes")
    update_window = normalize_maintenance_window(updates.get("maintenanceWindow"))

    if auto_update_enabled:
        if update_channel != "stable":
            errors["updates.channel"] = "Nur der signierte Stable-Kanal ist zulässig."
        try:
            update_interval = int(update_interval)
        except (TypeError, ValueError):
            errors["updates.checkIntervalMinutes"] = "Prüfintervall muss eine Zahl sein."
        else:
            if not MIN_CHECK_INTERVAL_MINUTES <= update_interval <= MAX_CHECK_INTERVAL_MINUTES:
                errors["updates.checkIntervalMinutes"] = (
                    "Prüfintervall muss zwischen 15 und 1440 Minuten liegen."
                )
        if not update_window:
            errors["updates.maintenanceWindow"] = (
                "Wartungsfenster muss eine gültige Uhrzeit sein "
                "(z. B. 09:00, 9:00 oder 09:00:00)."
            )
    else:
        update_channel = "stable"
        try:
            update_interval = int(update_interval)
        except (TypeError, ValueError):
            update_interval = default_updates["checkIntervalMinutes"]
        if not MIN_CHECK_INTERVAL_MINUTES <= update_interval <= MAX_CHECK_INTERVAL_MINUTES:
            update_interval = default_updates["checkIntervalMinutes"]
        if not update_window:
            update_window = default_updates["maintenanceWindow"]

    normalized["autoUpdateEnabled"] = auto_update_enabled
    normalized["channel"] = update_channel
    normalized["checkIntervalMinutes"] = update_interval
    normalized["maintenanceWindow"] = update_window
    return normalized, errors
