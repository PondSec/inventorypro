"""Ticket workspace and administration page routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, Response, jsonify, render_template, session

from inventorypro.web.blueprints import stable_route


def build_ticket_pages_blueprint(
    *,
    ensure_ticket_access: Callable[[Any, dict[str, Any]], bool],
    fetch_ticket: Callable[[Any, int], Any],
    get_db: Callable[[], Any],
    get_user_access: Callable[[Any], dict[str, Any]],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    require_permissions: Callable[..., Callable[[Callable[..., Any]], Callable[..., Any]]],
) -> Blueprint:
    """Create ticket page handlers without changing their public contracts."""
    blueprint = Blueprint("ticket_pages", __name__)

    @stable_route(blueprint, "/tickets")
    @login_required
    @require_permissions("tickets.view_all", "tickets.view_own", "tickets.create")
    def tickets_page():
        access = get_user_access(get_db())
        return render_template(
            "tickets.html",
            username=session.get("username"),
            permissions=sorted(access["permissions"]),
            is_superuser=access["is_superuser"],
        )

    @stable_route(blueprint, "/tickets/<int:ticket_id>")
    @login_required
    @require_permissions("tickets.view_all", "tickets.view_own")
    def ticket_workspace_page(ticket_id: int):
        ticket = fetch_ticket(get_db(), ticket_id)
        access = get_user_access(get_db())
        if not ticket:
            return Response(
                "Ticket nicht gefunden",
                status=404,
                content_type="text/plain; charset=utf-8",
            )
        if not ensure_ticket_access(ticket, access):
            return jsonify({"error": "Keine Berechtigung"}), 403
        return render_template(
            "tickets.html",
            username=session.get("username"),
            permissions=sorted(access["permissions"]),
            is_superuser=access["is_superuser"],
            initial_ticket_id=ticket_id,
        )

    @stable_route(blueprint, "/admin/tickets")
    @stable_route(blueprint, "/admin/tickets/<section>")
    @login_required
    @require_permissions(
        "ticket_categories.manage",
        "ticket_alerts.manage",
        "notifications.manage",
    )
    def ticket_admin_page(section: str = "general"):
        access = get_user_access(get_db())
        return render_template(
            "ticket_admin.html",
            username=session.get("username"),
            permissions=sorted(access["permissions"]),
            is_superuser=access["is_superuser"],
            section=section,
        )

    return blueprint
