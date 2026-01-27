"""Asset tools for PondSec AI."""
from .. import context
from ..registry import agent_tool


@agent_tool(
    "asset.search",
    schema={"query": "str", "limit": "int"},
    required=["query"],
    requires_perm="assets.view",
    is_write=False,
)
def asset_search(ctx, tool_input):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    if not (access["is_superuser"] or "assets.view" in access["permissions"] or "assets.manage" in access["permissions"]):
        return {"error": "forbidden"}
    query = tool_input.get("query", "")
    limit = min(int(tool_input.get("limit") or 10), 50)
    rows = db.execute(
        '''
        SELECT id, name, notes, created_at
        FROM assets
        WHERE name LIKE ? OR notes LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (f"%{query}%", f"%{query}%", limit),
    ).fetchall()
    return {"results": [dict(row) for row in rows]}
