"""Rules tools for PondSec AI."""
from datetime import datetime
import json

from .. import context
from ..registry import agent_tool


@agent_tool(
    "rules.create",
    schema={"name": "str", "spec_json": "dict"},
    required=["name", "spec_json"],
    requires_perm="ai.manage",
    is_write=True,
)
def rules_create(ctx, tool_input):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    if not (access["is_superuser"] or "ai.manage" in access["permissions"]):
        return {"error": "forbidden"}
    db.execute(
        '''
        INSERT INTO agent_rules (name, enabled, spec_json, created_at)
        VALUES (?, 0, ?, ?)
        ''',
        (
            tool_input.get("name"),
            json.dumps(tool_input.get("spec_json") or {}),
            datetime.utcnow().isoformat(),
        ),
    )
    db.commit()
    return {"status": "created"}
