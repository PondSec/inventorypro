"""Database helpers and migrations for PondSec AI."""
from datetime import datetime
import json

from .registry import TOOL_REGISTRY


AGENT_TABLES = [
    "agent_settings",
    "agent_tool_permissions",
    "agent_actions",
    "agent_action_steps",
    "agent_approvals",
    "agent_events",
    "agent_alerts",
    "agent_audit",
    "agent_rules",
]


def migrate_agent_db(db):
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_settings (
            id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'advisor',
            budgets_json TEXT DEFAULT '{}',
            updated_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_tool_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NULL,
            tool_name TEXT NOT NULL,
            allowed INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'low',
            require_approval INTEGER DEFAULT 0,
            UNIQUE(role_id, tool_name)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            created_by_user_id INTEGER,
            context_json TEXT,
            plan_json TEXT,
            status TEXT,
            risk_level TEXT,
            summary_text TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_action_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER,
            step_index INTEGER,
            tool_name TEXT,
            tool_input_json TEXT,
            tool_output_json TEXT,
            status TEXT,
            error TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_action_steps_action_id ON agent_action_steps (action_id)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER,
            requested_by_user_id INTEGER,
            approved_by_user_id INTEGER NULL,
            status TEXT,
            created_at TEXT,
            resolved_at TEXT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            type TEXT,
            entity_type TEXT,
            entity_id TEXT,
            payload_json TEXT,
            processed_at TEXT NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_events_processed_at ON agent_events (processed_at)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            severity TEXT,
            title TEXT,
            body TEXT,
            entity_refs_json TEXT,
            status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            user_id INTEGER NULL,
            agent_action_id INTEGER NULL,
            tool_name TEXT,
            decision TEXT,
            reason TEXT,
            payload_json TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_audit_created_at ON agent_audit (created_at)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            enabled INTEGER DEFAULT 0,
            spec_json TEXT,
            created_at TEXT
        )
    ''')
    now = datetime.utcnow().isoformat()
    cursor.execute('''
        INSERT OR IGNORE INTO agent_settings (id, enabled, mode, budgets_json, updated_at)
        VALUES (1, 0, 'advisor', '{}', ?)
    ''', (now,))
    db.commit()


def seed_default_tool_permissions(db):
    tool_names = list(TOOL_REGISTRY.keys())
    if not tool_names:
        return
    existing = db.execute('SELECT COUNT(*) as count FROM agent_tool_permissions').fetchone()["count"]
    if existing:
        return
    roles = db.execute('SELECT id, is_superuser FROM roles').fetchall()
    superuser_roles = [row["id"] for row in roles if row["is_superuser"]]
    read_tools = [name for name, tool in TOOL_REGISTRY.items() if not tool.is_write]
    default_write_tools = {
        "ticket.add_comment",
        "alert.create",
    }
    now = datetime.utcnow().isoformat()
    for tool_name in read_tools:
        tool = TOOL_REGISTRY[tool_name]
        target_roles = superuser_roles or [None]
        for role_id in target_roles:
            db.execute(
                '''
                INSERT OR IGNORE INTO agent_tool_permissions
                    (role_id, tool_name, allowed, risk_level, require_approval)
                VALUES (?, ?, 1, ?, 0)
                ''',
                (role_id, tool_name, tool.risk)
            )
    for tool_name in default_write_tools:
        tool = TOOL_REGISTRY.get(tool_name)
        if not tool:
            continue
        target_roles = superuser_roles or [None]
        for role_id in target_roles:
            db.execute(
                '''
                INSERT OR IGNORE INTO agent_tool_permissions
                    (role_id, tool_name, allowed, risk_level, require_approval)
                VALUES (?, ?, 1, ?, 0)
                ''',
                (role_id, tool_name, tool.risk),
            )
    db.execute('UPDATE agent_settings SET updated_at = ? WHERE id = 1', (now,))
    db.commit()


def get_agent_settings(db):
    row = db.execute('SELECT * FROM agent_settings WHERE id = 1').fetchone()
    if not row:
        return {
            "enabled": False,
            "mode": "advisor",
            "budgets": {},
        }
    budgets = {}
    try:
        budgets = json.loads(row["budgets_json"] or "{}")
    except json.JSONDecodeError:
        budgets = {}
    return {
        "enabled": bool(row["enabled"]),
        "mode": row["mode"] or "advisor",
        "budgets": budgets,
        "updated_at": row["updated_at"],
    }


def update_agent_settings(db, settings):
    now = datetime.utcnow().isoformat()
    db.execute(
        '''
        UPDATE agent_settings
        SET enabled = ?, mode = ?, budgets_json = ?, updated_at = ?
        WHERE id = 1
        ''',
        (
            1 if settings.get("enabled") else 0,
            settings.get("mode", "advisor"),
            json.dumps(settings.get("budgets", {})),
            now,
        ),
    )
    db.commit()
