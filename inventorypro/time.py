"""UTC clock helpers that preserve legacy naive timestamp storage."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time without timezone metadata for legacy storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
