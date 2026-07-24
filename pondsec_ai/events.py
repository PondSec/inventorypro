"""Event bus and processing for PondSec AI."""
from datetime import datetime
import json
import sqlite3

from apscheduler.schedulers.background import BackgroundScheduler

from .runtime import AgentRuntime
from . import context


_EVENT_SCHEDULER = None


def emit_event(db, event_type, entity_type, entity_id, payload):
    try:
        db.execute(
            '''
            INSERT INTO agent_events (created_at, type, entity_type, entity_id, payload_json)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                datetime.utcnow().isoformat(),
                event_type,
                entity_type,
                str(entity_id),
                json.dumps(payload or {}),
            ),
        )
        db.commit()
    except sqlite3.OperationalError as exc:
        if "agent_events" in str(exc):
            return
        raise


def process_events(limit=50):
    db = context.get_db()
    runtime = AgentRuntime(db)
    try:
        rows = db.execute(
            '''
            SELECT * FROM agent_events
            WHERE processed_at IS NULL
            ORDER BY created_at ASC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "agent_events" in str(exc):
            return
        raise
    for row in rows:
        runtime.handle_event(row)
        db.execute(
            'UPDATE agent_events SET processed_at = ? WHERE id = ?',
            (datetime.utcnow().isoformat(), row["id"]),
        )
    db.commit()


def start_event_processor(app):
    global _EVENT_SCHEDULER
    if _EVENT_SCHEDULER:
        return
    _EVENT_SCHEDULER = BackgroundScheduler()

    def _tick():
        with app.app_context():
            process_events()

    _EVENT_SCHEDULER.add_job(_tick, "interval", seconds=60, id="pondsec_ai_events")
    _EVENT_SCHEDULER.start()
