"""Alert tools for PondSec AI."""
from datetime import datetime
import json

from .. import context
from ..registry import agent_tool


@agent_tool(
    "alert.create",
    schema={"severity": "str", "title": "str", "body": "str", "entity_refs": "list"},
    required=["severity", "title", "body"],
    requires_perm="ticket_alerts.manage",
    is_write=True,
)
def alert_create(ctx, tool_input):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    if not (access["is_superuser"] or "ticket_alerts.manage" in access["permissions"]):
        return {"error": "forbidden"}
    severity = tool_input.get("severity") or "info"
    title = tool_input.get("title") or "Alert"
    body = tool_input.get("body") or ""
    entity_refs = tool_input.get("entity_refs") or []
    db.execute(
        '''
        INSERT INTO agent_alerts (created_at, severity, title, body, entity_refs_json, status)
        VALUES (?, ?, ?, ?, ?, 'open')
        ''',
        (
            datetime.utcnow().isoformat(),
            severity,
            title,
            body,
            json.dumps(entity_refs),
        ),
    )
    db.commit()
    return {"status": "created"}
