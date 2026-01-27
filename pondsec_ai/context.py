"""Shared app context references for PondSec AI."""
import re

get_db = None
get_user_access = None
user_can = None
ensure_ticket_access = None
log_activity = None
login_required = None
require_permission = None
require_permissions = None
app = None


def parse_entity_refs(message):
    if not message:
        return {}
    patterns = {
        "ticket_id": r"\b(?:ticket|Ticket)\s*#?\s*(\d+)\b",
        "asset_id": r"\b(?:asset|gerät|geraet|device)\s*#?\s*(\d+)\b",
        "kb_id": r"\b(?:kb|knowledge\s*base|wissensbasis)\s*#?\s*(\d+)\b",
    }
    refs = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, message)
        if match:
            refs[key] = int(match.group(1))
    return refs


def normalize_context(raw_context):
    if not raw_context:
        return {"type": "unknown"}
    if isinstance(raw_context, dict):
        if "type" in raw_context:
            ctx_type = (raw_context.get("type") or "unknown").lower()
            ctx_id = raw_context.get("id") or raw_context.get("entity_id")
        else:
            ctx_type = (raw_context.get("entity") or "unknown").lower()
            ctx_id = raw_context.get("entity_id") or raw_context.get("id")
        try:
            ctx_id = int(ctx_id) if ctx_id is not None else None
        except (TypeError, ValueError):
            ctx_id = None
        return {"type": ctx_type, "id": ctx_id}
    if isinstance(raw_context, str):
        match = re.search(r"\b(?:ticket|Ticket)\s*#?\s*(\d+)\b", raw_context)
        if match:
            return {"type": "ticket", "id": int(match.group(1))}
        if "ticket" in raw_context.lower():
            return {"type": "tickets", "id": None}
    return {"type": "unknown"}


def init(
    *,
    get_db,
    get_user_access,
    user_can,
    ensure_ticket_access,
    log_activity,
    login_required,
    require_permission,
    require_permissions,
    app,
):
    globals()["get_db"] = get_db
    globals()["get_user_access"] = get_user_access
    globals()["user_can"] = user_can
    globals()["ensure_ticket_access"] = ensure_ticket_access
    globals()["log_activity"] = log_activity
    globals()["login_required"] = login_required
    globals()["require_permission"] = require_permission
    globals()["require_permissions"] = require_permissions
    globals()["app"] = app
