"""Audit logging for PondSec AI."""
from datetime import datetime
import json

from . import context


def log_tool_decision(db, *, user_id, action_id, tool_name, decision, reason, payload=None):
    db.execute(
        '''
        INSERT INTO agent_audit
            (created_at, user_id, agent_action_id, tool_name, decision, reason, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            datetime.utcnow().isoformat(),
            user_id,
            action_id,
            tool_name,
            decision,
            reason,
            json.dumps(payload or {}),
        ),
    )
    db.commit()


def log_action_step(db, *, action_id, step_index, tool_name, tool_input, status, output=None, error=None):
    db.execute(
        '''
        INSERT INTO agent_action_steps
            (action_id, step_index, tool_name, tool_input_json, tool_output_json, status, error)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            action_id,
            step_index,
            tool_name,
            json.dumps(tool_input or {}),
            json.dumps(output or {}),
            status,
            error,
        ),
    )
    db.commit()
