"""Policy engine for PondSec AI tool execution."""
from datetime import datetime, timedelta
import json

from .db import get_agent_settings
from .registry import ToolDefinition


class PolicyEngine:
    def __init__(self, db):
        self.db = db
        self.settings = get_agent_settings(db)

    def _load_tool_permission(self, role_ids, tool_name):
        if not role_ids:
            role_ids = []
        placeholders = ",".join(["?"] * len(role_ids))
        params = [tool_name]
        query = '''
            SELECT *
            FROM agent_tool_permissions
            WHERE tool_name = ?
        '''
        if role_ids:
            query += f" AND (role_id IN ({placeholders}) OR role_id IS NULL)"
            params.extend(role_ids)
        else:
            query += " AND role_id IS NULL"
        rows = self.db.execute(query, params).fetchall()
        if not rows:
            return None
        for row in rows:
            if row["allowed"]:
                return row
        return rows[0]

    def _check_budget(self, user_id, tool_def: ToolDefinition):
        budgets = self.settings.get("budgets", {}) or {}
        max_calls_per_hour = budgets.get("max_calls_per_hour")
        max_write_actions_per_day = budgets.get("max_write_actions_per_day")
        now = datetime.utcnow()
        if max_calls_per_hour:
            since = (now - timedelta(hours=1)).isoformat()
            row = self.db.execute(
                '''
                SELECT COUNT(*) as count
                FROM agent_audit
                WHERE user_id = ? AND created_at >= ? AND decision = 'allowed'
                ''',
                (user_id, since),
            ).fetchone()
            if row and row["count"] >= max_calls_per_hour:
                return False, "budget.max_calls_per_hour"
        if tool_def.is_write and max_write_actions_per_day:
            since = (now - timedelta(days=1)).isoformat()
            row = self.db.execute(
                '''
                SELECT COUNT(*) as count
                FROM agent_action_steps
                WHERE status = 'executed' AND step_index >= 0
                    AND action_id IN (
                        SELECT id FROM agent_actions
                        WHERE created_by_user_id = ? AND created_at >= ?
                    )
                ''',
                (user_id, since),
            ).fetchone()
            if row and row["count"] >= max_write_actions_per_day:
                return False, "budget.max_write_actions_per_day"
        return True, "ok"

    def evaluate(self, ctx, tool_def: ToolDefinition):
        if not self.settings.get("enabled"):
            return {
                "decision": "denied",
                "reason": "agent_disabled",
                "requires_approval": False,
                "propose_only": False,
            }
        user = ctx.get("user") or {}
        role_ids = [role["id"] for role in ctx.get("roles", [])]
        tool_permission = self._load_tool_permission(role_ids, tool_def.name)
        if tool_permission is None:
            if tool_def.is_write:
                return {
                    "decision": "denied",
                    "reason": "tool_not_allowed",
                    "requires_approval": False,
                    "propose_only": False,
                }
        elif not tool_permission["allowed"]:
            return {
                "decision": "denied",
                "reason": "tool_not_allowed",
                "requires_approval": False,
                "propose_only": False,
            }
        ok, budget_reason = self._check_budget(user.get("id"), tool_def)
        if not ok:
            return {
                "decision": "denied",
                "reason": budget_reason,
                "requires_approval": False,
                "propose_only": False,
            }
        mode = self.settings.get("mode", "advisor")
        requires_approval = False
        if tool_permission is not None and tool_permission["require_approval"]:
            requires_approval = True
        if tool_def.risk in {"med", "high"}:
            requires_approval = True
        if mode == "advisor" and tool_def.is_write:
            return {
                "decision": "allowed",
                "reason": "advisor_mode",
                "requires_approval": requires_approval,
                "propose_only": True,
            }
        if mode == "advisor" and not tool_def.is_write:
            return {
                "decision": "allowed",
                "reason": "advisor_mode",
                "requires_approval": False,
                "propose_only": False,
            }
        return {
            "decision": "allowed",
            "reason": "policy_ok",
            "requires_approval": requires_approval,
            "propose_only": False,
        }


def request_approval(db, action_id, user_id):
    now = datetime.utcnow().isoformat()
    existing = db.execute(
        'SELECT 1 FROM agent_approvals WHERE action_id = ? AND status = \"pending\"',
        (action_id,),
    ).fetchone()
    if not existing:
        db.execute(
            '''
            INSERT INTO agent_approvals
                (action_id, requested_by_user_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
            ''',
            (action_id, user_id, now),
        )
    db.commit()


def approve_action(db, action_id, approver_id):
    now = datetime.utcnow().isoformat()
    db.execute(
        '''
        UPDATE agent_approvals
        SET status = 'approved', approved_by_user_id = ?, resolved_at = ?
        WHERE action_id = ? AND status = 'pending'
        ''',
        (approver_id, now, action_id),
    )
    db.execute(
        '''
        UPDATE agent_actions
        SET status = 'approved'
        WHERE id = ?
        ''',
        (action_id,),
    )
    db.commit()


def reject_action(db, action_id, approver_id):
    now = datetime.utcnow().isoformat()
    db.execute(
        '''
        UPDATE agent_approvals
        SET status = 'rejected', approved_by_user_id = ?, resolved_at = ?
        WHERE action_id = ? AND status = 'pending'
        ''',
        (approver_id, now, action_id),
    )
    db.execute(
        '''
        UPDATE agent_actions
        SET status = 'denied'
        WHERE id = ?
        ''',
        (action_id,),
    )
    db.commit()
