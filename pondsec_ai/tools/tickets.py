"""Ticket tools for PondSec AI."""
from datetime import datetime

from .. import context
from ..registry import agent_tool


def _create_ticket_comment(ctx, tool_input, *, internal_flag):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    ticket_id = int(tool_input.get("ticket_id"))
    body = (tool_input.get("body") or "").strip()
    if not body:
        return {"error": "body_required"}
    ticket = db.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        return {"error": "not_found"}
    if not context.ensure_ticket_access(dict(ticket), access):
        return {"error": "forbidden"}
    can_comment = access["is_superuser"] or "tickets.comment" in access["permissions"]
    can_comment_own = "tickets.comment_own" in access["permissions"]
    if not can_comment and not (can_comment_own and ticket["created_by"] == ctx.get("user", {}).get("username")):
        return {"error": "forbidden"}
    allow_internal = access["is_superuser"] or "tickets.comment_internal" in access["permissions"]
    is_internal = 1 if allow_internal and internal_flag else 0
    db.execute(
        '''
        INSERT INTO ticket_comments (ticket_id, author, body, is_internal)
        VALUES (?, ?, ?, ?)
        ''',
        (ticket_id, ctx.get("user", {}).get("username"), body, is_internal),
    )
    db.execute('UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (ticket_id,))
    context.log_activity(db, "comment", "ticket", ticket_id)
    db.commit()
    return {"status": "created", "ticket_id": ticket_id}


@agent_tool(
    "ticket.search",
    schema={"query": "str", "limit": "int"},
    required=["query"],
    requires_perm="tickets.view_all",
    is_write=False,
)
def ticket_search(ctx, tool_input):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    if not (access["is_superuser"] or "tickets.view_all" in access["permissions"] or "tickets.view_own" in access["permissions"]):
        return {"error": "forbidden"}
    query = tool_input.get("query", "")
    limit = min(int(tool_input.get("limit") or 10), 50)
    rows = db.execute(
        '''
        SELECT id, title, priority, status, created_at
        FROM tickets
        WHERE title LIKE ? OR description LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (f"%{query}%", f"%{query}%", limit),
    ).fetchall()
    return {"results": [dict(row) for row in rows]}


@agent_tool(
    "ticket.get",
    schema={"ticket_id": "int"},
    required=["ticket_id"],
    requires_perm="tickets.view_all",
    is_write=False,
)
def ticket_get(ctx, tool_input):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    ticket_id = int(tool_input.get("ticket_id"))
    ticket = db.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        return {"error": "not_found"}
    if not context.ensure_ticket_access(dict(ticket), access):
        return {"error": "forbidden"}
    return {"ticket": dict(ticket)}


@agent_tool(
    "ticket.comment",
    schema={"ticket_id": "int", "body": "str", "internal_note": "bool"},
    required=["ticket_id", "body"],
    requires_perm="tickets.comment",
    is_write=True,
)
def ticket_comment(ctx, tool_input):
    return _create_ticket_comment(ctx, tool_input, internal_flag=bool(tool_input.get("internal_note")))


@agent_tool(
    "ticket.add_comment",
    schema={"ticket_id": "int", "body": "str", "internal": "bool"},
    required=["ticket_id", "body"],
    requires_perm="tickets.comment",
    is_write=True,
)
def ticket_add_comment(ctx, tool_input):
    return _create_ticket_comment(ctx, tool_input, internal_flag=bool(tool_input.get("internal")))


@agent_tool(
    "ticket.escalate",
    schema={"ticket_id": "int", "level": "int"},
    required=["ticket_id", "level"],
    requires_perm="tickets.update",
    risk="med",
    is_write=True,
)
def ticket_escalate(ctx, tool_input):
    db = context.get_db()
    access = ctx.get("access") or context.get_user_access(db)
    if not (access["is_superuser"] or "tickets.update" in access["permissions"]):
        return {"error": "forbidden"}
    ticket_id = int(tool_input.get("ticket_id"))
    level = int(tool_input.get("level") or 1)
    ticket = db.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        return {"error": "not_found"}
    if not context.ensure_ticket_access(dict(ticket), access):
        return {"error": "forbidden"}
    db.execute(
        'UPDATE tickets SET escalation_level = ?, updated_at = ? WHERE id = ?',
        (level, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), ticket_id),
    )
    context.log_activity(db, "escalate", "ticket", ticket_id, {"level": level})
    db.commit()
    return {"status": "updated", "ticket_id": ticket_id, "level": level}
