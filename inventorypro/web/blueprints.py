"""Blueprint helpers for incrementally extracting legacy Flask routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint


def stable_route(
    blueprint: Blueprint,
    rule: str,
    *,
    endpoint: str | None = None,
    **options: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a blueprint-owned route under its established endpoint name.

    Flask normally prefixes a blueprint endpoint with its blueprint name.  The
    compatibility application historically exposes unprefixed endpoint names
    through ``url_for``.  During incremental extraction this helper preserves
    those contracts while still keeping each route owned by a blueprint.
    """

    def decorator(view_function: Callable[..., Any]) -> Callable[..., Any]:
        route_endpoint = endpoint or view_function.__name__

        def register_route(state: Any) -> None:
            state.app.add_url_rule(
                rule,
                endpoint=route_endpoint,
                view_func=view_function,
                **options,
            )

        blueprint.record(register_route)
        return view_function

    return decorator
