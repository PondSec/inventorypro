"""Profile routes for the data migration domain."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from flask import Blueprint, jsonify, request

from inventorypro.web.blueprints import stable_route

from .service import ImportProfileService, ImportProfileValidationError


def build_import_profiles_blueprint(
    *,
    get_db: Callable[[], Any],
    imports_enabled: Callable[[Any], bool],
    current_actor: Callable[[], str],
    log_activity: Callable[..., None],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    require_permission: Callable[[str], Callable[[Callable[..., Any]], Callable[..., Any]]],
) -> Blueprint:
    """Create protected profile-management routes without coupling to Flask globals."""
    blueprint = Blueprint("import_profiles", __name__)
    service = ImportProfileService()

    def reject_if_disabled(connection: Any):
        if not imports_enabled(connection):
            return jsonify({"error": "Import ist deaktiviert."}), 403
        return None

    @stable_route(blueprint, "/api/import/profiles", methods=["GET"])
    @login_required
    @require_permission("server_settings.manage")
    def list_import_profiles():
        connection = get_db()
        disabled = reject_if_disabled(connection)
        if disabled:
            return disabled
        try:
            return jsonify({"profiles": service.list(connection, request.args.get("entity"))})
        except ImportProfileValidationError as error:
            return jsonify({"error": str(error)}), 400

    @stable_route(blueprint, "/api/import/profiles", methods=["POST"])
    @login_required
    @require_permission("server_settings.manage")
    def create_import_profile():
        connection = get_db()
        disabled = reject_if_disabled(connection)
        if disabled:
            return disabled
        try:
            profile = service.create(connection, request.get_json(silent=True) or {}, current_actor())
            log_activity(
                connection,
                "import_profile_created",
                "import_profile",
                profile["id"],
                {"name": profile["name"], "entity": profile["entity"]},
            )
            connection.commit()
            return jsonify({"profile": profile}), 201
        except ImportProfileValidationError as error:
            return jsonify({"error": str(error)}), 400

    @stable_route(blueprint, "/api/import/profiles/<int:profile_id>", methods=["PUT"])
    @login_required
    @require_permission("server_settings.manage")
    def update_import_profile(profile_id: int):
        connection = get_db()
        disabled = reject_if_disabled(connection)
        if disabled:
            return disabled
        try:
            profile = service.update(connection, profile_id, request.get_json(silent=True) or {})
        except ImportProfileValidationError as error:
            return jsonify({"error": str(error)}), 400
        if not profile:
            return jsonify({"error": "Importprofil nicht gefunden."}), 404
        log_activity(
            connection,
            "import_profile_updated",
            "import_profile",
            profile["id"],
            {"name": profile["name"], "entity": profile["entity"]},
        )
        connection.commit()
        return jsonify({"profile": profile})

    @stable_route(blueprint, "/api/import/profiles/<int:profile_id>", methods=["DELETE"])
    @login_required
    @require_permission("server_settings.manage")
    def delete_import_profile(profile_id: int):
        connection = get_db()
        disabled = reject_if_disabled(connection)
        if disabled:
            return disabled
        if not service.delete(connection, profile_id):
            return jsonify({"error": "Importprofil nicht gefunden."}), 404
        log_activity(connection, "import_profile_deleted", "import_profile", profile_id, {})
        connection.commit()
        return jsonify({"status": "deleted"})

    return blueprint
