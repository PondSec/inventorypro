"""Compatibility application factory used during the modular-monolith extraction."""

from __future__ import annotations

from collections.abc import Mapping


def create_app(config: Mapping[str, object] | None = None):
    """Return the Flask application while preserving legacy route contracts.

    Route registration remains in the compatibility module until each domain is
    moved to a blueprint. New infrastructure is intentionally consumed through
    this entry point so callers no longer depend on WSGI module globals.
    """
    import app as legacy_application

    flask_application = legacy_application.app
    if config:
        flask_application.config.update(config)
    return flask_application
