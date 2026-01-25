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
