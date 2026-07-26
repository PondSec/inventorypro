"""Protected white-label customization routes."""

from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any

from flask import Blueprint, jsonify, request

from inventorypro.web.blueprints import stable_route


def build_customization_blueprint(
    *,
    get_db: Callable[[], Any],
    get_current_user_id: Callable[[Any], int | None],
    get_customization_record: Callable[[Any, int], Any],
    default_customization: Any,
    migrate_customization: Callable[[Any], dict[str, Any]],
    deep_merge: Callable[[Any, Any], Any],
    validate_customization: Callable[[Any], tuple[bool, list[str]]],
    save_customization: Callable[[Any, int, dict[str, Any], str], int],
    current_actor: Callable[[], str],
    log_activity: Callable[..., None],
    user_can: Callable[[str], bool],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Blueprint:
    """Create customization routes without changing Flask endpoint contracts."""
    blueprint = Blueprint("customization", __name__)

    def latest_revision_id(database: Any, customization_id: int) -> int | None:
        revision = database.execute(
            """
            SELECT id FROM ui_customization_revisions
            WHERE customization_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (customization_id,),
        ).fetchone()
        return revision["id"] if revision else None

    @stable_route(blueprint, "/api/customize", methods=["GET", "PUT", "PATCH"])
    @login_required
    def customize_settings():
        database = get_db()
        user_id = get_current_user_id(database)
        if not user_id:
            return jsonify({"error": "Benutzer nicht gefunden."}), 401

        record = get_customization_record(database, user_id)
        existing = json.loads(record["customization_json"]) if record else None

        if request.method == "GET":
            customization = migrate_customization(existing or default_customization)
            return jsonify({
                "customization": customization,
                "updated_at": record["updated_at"] if record else None,
                "revision_id": latest_revision_id(database, record["id"]) if record else None,
            })

        if not user_can("server_settings.manage"):
            return jsonify({"error": "Keine Berechtigung"}), 403
        payload = request.get_json() or {}
        merged = deep_merge(existing or default_customization, payload) if request.method == "PATCH" else payload
        customization = migrate_customization(merged)
        valid, errors = validate_customization(customization)
        if not valid:
            return jsonify({"error": "Ungültige Customize-Daten.", "details": errors}), 400

        customization_id = save_customization(database, user_id, customization, current_actor())
        updated_at = database.execute(
            "SELECT updated_at FROM ui_customization WHERE id = ?",
            (customization_id,),
        ).fetchone()
        log_activity(database, "update", "ui_customization", entity_id=customization_id)
        return jsonify({
            "customization": customization,
            "updated_at": updated_at["updated_at"] if updated_at else None,
            "revision_id": latest_revision_id(database, customization_id),
        })

    @stable_route(blueprint, "/api/customize/history", methods=["GET"])
    @login_required
    def customize_history():
        if not user_can("server_settings.manage"):
            return jsonify({"error": "Keine Berechtigung"}), 403
        database = get_db()
        user_id = get_current_user_id(database)
        if not user_id:
            return jsonify({"revisions": []})
        record = get_customization_record(database, user_id)
        if not record:
            return jsonify({"revisions": []})
        rows = database.execute(
            """
            SELECT id, created_at, created_by, diff_json
            FROM ui_customization_revisions
            WHERE customization_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (record["id"],),
        ).fetchall()
        revisions = [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "created_by": row["created_by"],
                "diff": json.loads(row["diff_json"]) if row["diff_json"] else [],
            }
            for row in rows
        ]
        return jsonify({"revisions": revisions})

    @stable_route(blueprint, "/api/customize/rollback/<int:revision_id>", methods=["POST"])
    @login_required
    def customize_rollback(revision_id: int):
        if not user_can("server_settings.manage"):
            return jsonify({"error": "Keine Berechtigung"}), 403
        database = get_db()
        user_id = get_current_user_id(database)
        if not user_id:
            return jsonify({"error": "Benutzer nicht gefunden."}), 401

        record = get_customization_record(database, user_id)
        if not record:
            return jsonify({"error": "Keine Customize-Konfiguration vorhanden."}), 404
        revision = database.execute(
            """
            SELECT revision_json FROM ui_customization_revisions
            WHERE id = ? AND customization_id = ?
            """,
            (revision_id, record["id"]),
        ).fetchone()
        if not revision:
            return jsonify({"error": "Revision nicht gefunden."}), 404

        customization = migrate_customization(json.loads(revision["revision_json"]))
        customization_id = save_customization(database, user_id, customization, current_actor())
        updated_at = database.execute(
            "SELECT updated_at FROM ui_customization WHERE id = ?",
            (customization_id,),
        ).fetchone()
        log_activity(database, "rollback", "ui_customization", entity_id=customization_id)
        return jsonify({
            "customization": customization,
            "updated_at": updated_at["updated_at"] if updated_at else None,
            "revision_id": latest_revision_id(database, customization_id),
        })

    return blueprint
