"""Validation for white-label customization payloads."""

from __future__ import annotations

import base64
import re
from typing import Any


def validate_customization(data: Any, *, max_image_bytes: int) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["Customization muss ein Objekt sein."]
    if not isinstance(data.get("schemaVersion"), int):
        errors.append("schemaVersion fehlt oder ist ungültig.")
    for key in ("baseTokens", "componentOverrides", "layoutPrefs", "featurePrefs", "branding", "navigation"):
        if key not in data:
            errors.append(f"{key} fehlt.")
    branding = data.get("branding")
    if isinstance(branding, dict):
        image_keys = ("logoDataUrl", "logoLightDataUrl", "logoDarkDataUrl", "faviconDataUrl", "authBackgroundDataUrl")
        for key in ("name", "tagline", *image_keys):
            if not isinstance(branding.get(key), str):
                errors.append(f"branding.{key} muss ein Textwert sein.")
        for key in image_keys:
            value = branding.get(key)
            if not isinstance(value, str) or not value:
                continue
            match = re.fullmatch(r"data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/]+={0,2})", value)
            if not match:
                errors.append(f"branding.{key} muss ein PNG-, JPEG-, WebP- oder GIF-Data-URL sein.")
                continue
            try:
                image_bytes = base64.b64decode(match.group(2), validate=True)
            except ValueError:
                errors.append(f"branding.{key} enthält ungültige Base64-Daten.")
                continue
            if len(image_bytes) > max_image_bytes:
                errors.append(f"branding.{key} überschreitet die Größenbegrenzung von 2 MB.")
    elif branding is not None:
        errors.append("branding muss ein Objekt sein.")
    navigation = data.get("navigation")
    if not isinstance(navigation, dict):
        errors.append("navigation muss ein Objekt sein.")
    else:
        groups = navigation.get("groups")
        items = navigation.get("items")
        if not isinstance(groups, dict):
            errors.append("navigation.groups muss ein Objekt sein.")
        else:
            for group_key, label in groups.items():
                if not isinstance(group_key, str) or not isinstance(label, str) or not label.strip() or len(label) > 80:
                    errors.append("navigation.groups enthält eine ungültige Gruppenbezeichnung.")
                    break
        if not isinstance(items, dict):
            errors.append("navigation.items muss ein Objekt sein.")
        else:
            for item_key, item in items.items():
                if not isinstance(item_key, str) or not isinstance(item, dict):
                    errors.append("navigation.items enthält einen ungültigen Navigationseintrag.")
                    break
                label = item.get("label")
                visible = item.get("visible")
                order = item.get("order")
                if not isinstance(label, str) or not label.strip() or len(label) > 80:
                    errors.append(f"navigation.items.{item_key}.label ist ungültig.")
                    break
                if not isinstance(visible, bool):
                    errors.append(f"navigation.items.{item_key}.visible muss wahr oder falsch sein.")
                    break
                if not isinstance(order, int) or not 0 <= order <= 999:
                    errors.append(f"navigation.items.{item_key}.order muss zwischen 0 und 999 liegen.")
                    break
    return len(errors) == 0, errors
