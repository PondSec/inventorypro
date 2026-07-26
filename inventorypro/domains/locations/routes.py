"""Location presentation and API routes.

The handlers receive their legacy collaborators during application setup.  This
keeps route contracts stable while allowing the domain to evolve independently
of the compatibility module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, render_template, request, session

from inventorypro.web.blueprints import stable_route

from .repository import LocationRepository
from .service import (
    LocationAlreadyExistsError,
    LocationInUseError,
    LocationNotFoundError,
    LocationService,
)
from .validators import LocationValidationError


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
    service = LocationService(LocationRepository(), log_activity)

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
            try:
                service.create(db, request.get_json())
            except LocationValidationError as error:
                return jsonify({"error": str(error)}), 400
            except LocationAlreadyExistsError:
                return jsonify({"error": "Standort existiert bereits"}), 400
            return jsonify({"status": "created"}), 201

        if not (user_can("locations.view") or user_can("locations.manage")):
            return jsonify({"error": "Keine Berechtigung"}), 403
        return jsonify(service.list_locations(db))

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
            try:
                service.update(db, location_id, request.get_json())
            except LocationValidationError as error:
                return jsonify({"error": str(error)}), 400
            except LocationNotFoundError:
                return jsonify({"error": "Standort nicht gefunden"}), 404
            return jsonify({"status": "updated"}), 200

        if not user_can("locations.manage"):
            return jsonify({"error": "Keine Berechtigung"}), 403
        try:
            service.delete(db, location_id)
        except LocationNotFoundError:
            return jsonify({"error": "Standort nicht gefunden"}), 404
        except LocationInUseError as error:
            return jsonify(
                {
                    "error": (
                        f"Standort „{error.location_name}“ wird noch verwendet. "
                        "Ordne Geräte und Asset-Zuweisungen vor dem Löschen einem "
                        "anderen Standort zu."
                    ),
                    "code": "location_in_use",
                    "references": {
                        "devices": error.devices,
                        "asset_assignments": error.assignments,
                    },
                }
            ), 409
        return jsonify({"status": "deleted"}), 200

    return blueprint
