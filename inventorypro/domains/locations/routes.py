"""Location presentation and API routes.

The handlers receive their legacy collaborators during application setup.  This
keeps route contracts stable while allowing the domain to evolve independently
of the compatibility module.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, render_template, request, session

from inventorypro.web.blueprints import stable_route


def build_locations_blueprint(
    *,
    get_db: Callable[[], Any],
    get_user_access: Callable[[Any], dict[str, Any]],
    log_activity: Callable[..., None],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    require_permissions: Callable[..., Callable[[Callable[..., Any]], Callable[..., Any]]],
    user_can: Callable[[str], bool],
) -> Blueprint:
    """Create the location domain blueprint with stable public endpoints."""
    blueprint = Blueprint("locations", __name__)

    @stable_route(blueprint, "/locations")
    @login_required
    @require_permissions("locations.view", "locations.manage")
    def locations_page():
        access = get_user_access(get_db())
        return render_template(
            "locations.html",
            username=session.get("username"),
            permissions=sorted(access["permissions"]),
            is_superuser=access["is_superuser"],
        )

    @stable_route(blueprint, "/api/locations", methods=["GET", "POST"])
    @login_required
    def manage_locations():
        db = get_db()
        if request.method == "POST":
            if not user_can("locations.manage"):
                return jsonify({"error": "Keine Berechtigung"}), 403
            data = request.get_json()
            name = (data.get("name") or "").strip()
            description = (data.get("description") or "").strip()
            if not name:
                return jsonify({"error": "Name ist erforderlich"}), 400
            try:
                db.execute(
                    """
                    INSERT INTO locations (name, description)
                    VALUES (?, ?)
                    """,
                    (name, description),
                )
                log_activity(db, "create", "location", details={"name": name})
                db.commit()
                return jsonify({"status": "created"}), 201
            except sqlite3.IntegrityError:
                return jsonify({"error": "Standort existiert bereits"}), 400

        if not (user_can("locations.view") or user_can("locations.manage")):
            return jsonify({"error": "Keine Berechtigung"}), 403
        locations = db.execute("SELECT * FROM locations ORDER BY name").fetchall()
        return jsonify([dict(row) for row in locations])

    @stable_route(
        blueprint,
        "/api/locations/<int:location_id>",
        methods=["PUT", "DELETE"],
    )
    @login_required
    def update_location(location_id: int):
        db = get_db()
        if request.method == "PUT":
            if not user_can("locations.manage"):
                return jsonify({"error": "Keine Berechtigung"}), 403
            data = request.get_json()
            name = (data.get("name") or "").strip()
            description = (data.get("description") or "").strip()
            if not name:
                return jsonify({"error": "Name ist erforderlich"}), 400
            result = db.execute(
                """
                UPDATE locations
                SET name = ?, description = ?
                WHERE id = ?
                """,
                (name, description, location_id),
            )
            if result.rowcount == 0:
                return jsonify({"error": "Standort nicht gefunden"}), 404
            log_activity(db, "update", "location", location_id, {"name": name})
            db.commit()
            return jsonify({"status": "updated"}), 200

        if not user_can("locations.manage"):
            return jsonify({"error": "Keine Berechtigung"}), 403
        location = db.execute(
            "SELECT id, name FROM locations WHERE id = ?", (location_id,)
        ).fetchone()
        if not location:
            return jsonify({"error": "Standort nicht gefunden"}), 404
        device_count = db.execute(
            "SELECT COUNT(*) FROM devices WHERE location_id = ?", (location_id,)
        ).fetchone()[0]
        assignment_count = db.execute(
            "SELECT COUNT(*) FROM asset_assignments WHERE location_id = ?",
            (location_id,),
        ).fetchone()[0]
        if device_count or assignment_count:
            return jsonify(
                {
                    "error": (
                        f"Standort „{location['name']}“ wird noch verwendet. "
                        "Ordne Geräte und Asset-Zuweisungen vor dem Löschen einem "
                        "anderen Standort zu."
                    ),
                    "code": "location_in_use",
                    "references": {
                        "devices": device_count,
                        "asset_assignments": assignment_count,
                    },
                }
            ), 409
        result = db.execute("DELETE FROM locations WHERE id = ?", (location_id,))
        if result.rowcount == 0:
            return jsonify({"error": "Standort nicht gefunden"}), 404
        log_activity(db, "delete", "location", location_id)
        db.commit()
        return jsonify({"status": "deleted"}), 200

    return blueprint
