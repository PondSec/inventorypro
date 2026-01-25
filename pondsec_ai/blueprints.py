"""Flask blueprint routes for PondSec AI."""
from flask import Blueprint, jsonify, render_template, request, session
from functools import wraps
import json

from . import context
from .db import get_agent_settings, update_agent_settings
from .policy import approve_action, reject_action
from .registry import TOOL_REGISTRY
from .runtime import AgentRuntime

ai_bp = Blueprint("pondsec_ai", __name__)


def login_required_proxy(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if context.login_required:
            return context.login_required(func)(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapped


@ai_bp.route("/ai/panel", methods=["GET"])
@login_required_proxy
def ai_panel():
    return render_template("pondsec_ai_drawer.html")


@ai_bp.route("/ai/chat", methods=["POST"])
@login_required_proxy
def ai_chat():
    db = context.get_db()
    access = context.get_user_access(db)
    if not (access["is_superuser"] or "ai.use" in access["permissions"]):
        return jsonify({"error": "Keine Berechtigung"}), 403
    payload = request.get_json() or {}
    message = (payload.get("message") or "").strip()
    ui_context = payload.get("ui_context") or {}
    context_payload = payload.get("context") or {}
    runtime = AgentRuntime(db)
    response = runtime.handle_user_prompt(
        {"access": access, "user": access.get("user"), "roles": access.get("roles")},
        {"ui_context": ui_context, "context": context_payload},
        message,
    )
    return jsonify(response)


@ai_bp.route("/ai/settings", methods=["GET", "POST"])
@login_required_proxy
def ai_settings():
    db = context.get_db()
    access = context.get_user_access(db)
    if request.method == "POST":
        if not (access["is_superuser"] or "ai.manage" in access["permissions"]):
            return jsonify({"error": "Keine Berechtigung"}), 403
        payload = request.get_json() or {}
        settings = {
            "enabled": bool(payload.get("enabled")),
            "mode": payload.get("mode") or "advisor",
            "budgets": payload.get("budgets") or {},
        }
        update_agent_settings(db, settings)
        tool_permissions = payload.get("tool_permissions") or []
        for entry in tool_permissions:
            db.execute(
                '''
                INSERT INTO agent_tool_permissions
                    (role_id, tool_name, allowed, risk_level, require_approval)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(role_id, tool_name) DO UPDATE SET
                    allowed = excluded.allowed,
                    risk_level = excluded.risk_level,
                    require_approval = excluded.require_approval
                ''',
                (
                    entry.get("role_id"),
                    entry.get("tool_name"),
                    1 if entry.get("allowed") else 0,
                    entry.get("risk_level", "low"),
                    1 if entry.get("require_approval") else 0,
                ),
            )
        db.commit()
        return jsonify({"status": "saved"})
    settings = get_agent_settings(db)
    roles = db.execute('SELECT id, name, is_superuser FROM roles ORDER BY name').fetchall()
    tools = db.execute('SELECT * FROM agent_tool_permissions ORDER BY tool_name').fetchall()
    tool_rows = [dict(row) for row in tools]
    existing_keys = {(row["role_id"], row["tool_name"]) for row in tool_rows}
    for tool_name, tool_def in TOOL_REGISTRY.items():
        key = (None, tool_name)
        if key not in existing_keys:
            tool_rows.append({
                "role_id": None,
                "tool_name": tool_name,
                "allowed": 0,
                "risk_level": tool_def.risk,
                "require_approval": 0,
            })
    return render_template(
        "ai_settings.html",
        username=session.get("username"),
        permissions=sorted(access["permissions"]),
        is_superuser=access["is_superuser"],
        settings=settings,
        roles=[dict(row) for row in roles],
        tool_permissions=sorted(tool_rows, key=lambda row: row["tool_name"]),
    )


@ai_bp.route("/ai/actions/<int:action_id>/approve", methods=["POST"])
@login_required_proxy
def ai_approve_action(action_id):
    db = context.get_db()
    access = context.get_user_access(db)
    if not (access["is_superuser"] or "ai.approve" in access["permissions"]):
        return jsonify({"error": "Keine Berechtigung"}), 403
    approve_action(db, action_id, access.get("user", {}).get("id"))
    runtime = AgentRuntime(db)
    result = runtime.execute_action(action_id, {"access": access, "user": access.get("user"), "roles": access.get("roles")})
    return jsonify(result)


@ai_bp.route("/ai/actions/<int:action_id>/reject", methods=["POST"])
@login_required_proxy
def ai_reject_action(action_id):
    db = context.get_db()
    access = context.get_user_access(db)
    if not (access["is_superuser"] or "ai.approve" in access["permissions"]):
        return jsonify({"error": "Keine Berechtigung"}), 403
    reject_action(db, action_id, access.get("user", {}).get("id"))
    return jsonify({"status": "rejected"})


@ai_bp.route("/ai/activity", methods=["GET"])
@login_required_proxy
def ai_activity():
    db = context.get_db()
    access = context.get_user_access(db)
    if not (access["is_superuser"] or "ai.use" in access["permissions"]):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute(
        '''
        SELECT * FROM agent_actions
        ORDER BY created_at DESC
        LIMIT 20
        '''
    ).fetchall()
    if request.args.get("format") == "json":
        return jsonify([dict(row) for row in rows])
    return render_template(
        "ai_activity.html",
        username=session.get("username"),
        permissions=sorted(access["permissions"]),
        is_superuser=access["is_superuser"],
        actions=[dict(row) for row in rows],
    )


@ai_bp.route("/ai/alerts", methods=["GET"])
@login_required_proxy
def ai_alerts():
    db = context.get_db()
    access = context.get_user_access(db)
    if not (access["is_superuser"] or "ai.use" in access["permissions"]):
        return jsonify({"error": "Keine Berechtigung"}), 403
    rows = db.execute(
        '''
        SELECT * FROM agent_alerts
        WHERE status = 'open'
        ORDER BY created_at DESC
        LIMIT 20
        '''
    ).fetchall()
    if request.args.get("format") == "json":
        return jsonify([dict(row) for row in rows])
    return render_template(
        "ai_alerts.html",
        username=session.get("username"),
        permissions=sorted(access["permissions"]),
        is_superuser=access["is_superuser"],
        alerts=[dict(row) for row in rows],
    )
