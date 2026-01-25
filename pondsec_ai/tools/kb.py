"""Knowledge base tools for PondSec AI."""
from .. import context
from ..registry import agent_tool


@agent_tool(
    "kb.search",
    schema={"query": "str", "limit": "int"},
    required=["query"],
    requires_perm="knowledge.view",
    is_write=False,
)
def kb_search(ctx, tool_input):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    if not (access["is_superuser"] or "knowledge.view" in access["permissions"] or "knowledge.manage" in access["permissions"]):
        return {"error": "forbidden"}
    query = tool_input.get("query", "")
    limit = min(int(tool_input.get("limit") or 10), 50)
    rows = db.execute(
        '''
        SELECT id, title, summary, created_at
        FROM knowledge_entries
        WHERE title LIKE ? OR summary LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (f"%{query}%", f"%{query}%", limit),
    ).fetchall()
    return {"results": [dict(row) for row in rows]}
