"""Manual backup API routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from flask import Blueprint, jsonify, request

from inventorypro.web.blueprints import stable_route

from .repository import BackupRunRepository
from .service import BackupService


def build_backups_blueprint(
    *,
    get_db: Callable[[], Any],
    load_settings: Callable[[Any], Mapping[str, Any]],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    require_permission: Callable[[str], Callable[[Callable[..., Any]], Callable[..., Any]]],
    run_backup_job: Callable[[Any, Mapping[str, Any], bool], dict[str, Any]],
) -> Blueprint:
    """Create manual backup routes with their legacy endpoint contracts."""
    blueprint = Blueprint("backups", __name__)
    service = BackupService(BackupRunRepository(), load_settings, run_backup_job)

    @stable_route(blueprint, "/api/backups/run", methods=["POST"])
    @login_required
    @require_permission("server_settings.manage")
    def run_backup():
        return jsonify(service.run(get_db(), request.get_json()))

    @stable_route(blueprint, "/api/backups/list", methods=["GET"])
    @login_required
    @require_permission("server_settings.manage")
    def list_backups():
        return jsonify({"backups": service.list_recent(get_db())})

    return blueprint
