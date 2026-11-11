"""Incident lifecycle helpers for health-monitoring results."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any


HEALTH_STATUSES = frozenset({"OK", "WARN", "CRIT", "UNKNOWN"})
DEFAULT_INCIDENT_OPEN_MINUTES = 0
DEFAULT_INCIDENT_CLOSE_MINUTES = 5
INCIDENT_PRIORITY = "high"
INCIDENT_REQUESTER = "System Health"


def normalize_health_status(status: Any) -> str:
    """Return a supported health status without leaking malformed values."""
    return status if status in HEALTH_STATUSES else "UNKNOWN"


def get_health_incident_ticket_category(db: Any) -> Any:
    """Return the dedicated Incident category, creating it when absent."""
    category = db.execute(
        """
        SELECT id, name, sla_hours
        FROM ticket_categories
        WHERE LOWER(name) = 'incident'
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if category:
        return category
    cursor = db.execute(
        """
        INSERT INTO ticket_categories (name, description, color, sla_hours, is_default)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Incident", "Automatisch erstellte System-Incidents", "#dc2626", 24, 0),
    )
    return db.execute(
        "SELECT id, name, sla_hours FROM ticket_categories WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()


def create_health_incident_ticket(db: Any, incident_id: int) -> int:
    """Create and link one high-priority ticket for an open health incident."""
    incident = db.execute(
        """
        SELECT i.*, d.name, d.slug, d.category
        FROM health_incidents i
        JOIN health_check_definitions d ON d.id = i.check_id
        WHERE i.id = ?
        """,
        (incident_id,),
    ).fetchone()
    if not incident:
        raise ValueError("Health-Incident nicht gefunden.")
    if incident["ticket_id"]:
        return incident["ticket_id"]

    category = get_health_incident_ticket_category(db)
    sla_hours = max(1, int(category["sla_hours"] or 24))
    opened_at = datetime.strptime(incident["opened_at"], "%Y-%m-%d %H:%M:%S")
    due_date = (opened_at + timedelta(hours=sla_hours)).strftime("%Y-%m-%d")
    description = (
        "Automatisch aus dem Health-Monitoring erstellt.\n"
        f"Check: {incident['name']} ({incident['slug'] or incident['check_id']})\n"
        f"Kategorie: {incident['category'] or '-'}\n"
        f"Status: {incident['last_status']}\n"
        f"Eröffnet: {incident['opened_at']} UTC\n"
        f"SLA: {sla_hours} Stunden\n"
        f"Details: {incident['summary'] or '-'}"
    )
    cursor = db.execute(
        """
        INSERT INTO tickets (
            title, description, category_id, priority, status, requester_name,
            created_by, due_date, escalation_level, tags
        )
        VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
        """,
        (
            f"Health-Incident: {incident['name']}",
            description,
            category["id"],
            INCIDENT_PRIORITY,
            INCIDENT_REQUESTER,
            INCIDENT_REQUESTER,
            due_date,
            1,
            json.dumps(["health", "incident", "automatic"]),
        ),
    )
    ticket_id = cursor.lastrowid
    db.execute(
        "UPDATE health_incidents SET ticket_id = ? WHERE id = ?",
        (ticket_id, incident_id),
    )
    db.execute(
        """
        INSERT INTO activity_log (username, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            INCIDENT_REQUESTER,
            "create",
            "ticket",
            ticket_id,
            json.dumps({"source": "health_incident", "incident_id": incident_id}),
        ),
    )
    return ticket_id


def record_health_incident(
    db: Any,
    check_id: int,
    summary: str,
    observed_at: str,
    status: str,
) -> int:
    """Open an incident once per check and ensure it owns a ticket."""
    try:
        cursor = db.execute(
            """
            INSERT INTO health_incidents (
                check_id, status, summary, opened_at, last_status, last_observed_at
            )
            VALUES (?, 'open', ?, ?, ?, ?)
            """,
            (check_id, summary, observed_at, status, observed_at),
        )
    except sqlite3.IntegrityError:
        active_incident = db.execute(
            "SELECT id, ticket_id FROM health_incidents WHERE check_id = ? AND status = 'open'",
            (check_id,),
        ).fetchone()
        if active_incident:
            if not active_incident["ticket_id"]:
                create_health_incident_ticket(db, active_incident["id"])
            return active_incident["id"]
        raise
    incident_id = cursor.lastrowid
    create_health_incident_ticket(db, incident_id)
    return incident_id


def close_health_incident(db: Any, incident_id: int, observed_at: str) -> None:
    """Mark an incident closed after the configured healthy interval."""
    db.execute(
        """
        UPDATE health_incidents
        SET status = 'closed',
            closed_at = ?,
            last_status = 'OK',
            last_observed_at = ?
        WHERE id = ?
        """,
        (observed_at, observed_at, incident_id),
    )


def update_health_incident_state(
    db: Any,
    check_id: int,
    status: str,
    observed_at: str,
    config: dict[str, Any],
    reason: str = "",
) -> None:
    """Synchronize the open incident state with one health-check result."""
    status = normalize_health_status(status)
    incident_open_after_value = config.get("incident_open_after_minutes")
    incident_close_after_value = config.get("incident_close_after_minutes")
    incident_open_after = (
        int(incident_open_after_value)
        if incident_open_after_value is not None
        else DEFAULT_INCIDENT_OPEN_MINUTES
    )
    incident_close_after = (
        int(incident_close_after_value)
        if incident_close_after_value is not None
        else DEFAULT_INCIDENT_CLOSE_MINUTES
    )

    active_incident = db.execute(
        """
        SELECT id, status, opened_at, acknowledged_at, muted_until, ticket_id
        FROM health_incidents
        WHERE check_id = ? AND status = 'open'
        ORDER BY opened_at DESC
        LIMIT 1
        """,
        (check_id,),
    ).fetchone()

    if status != "OK":
        last_ok = db.execute(
            """
            SELECT observed_at
            FROM health_check_results
            WHERE check_id = ? AND status = 'OK'
            ORDER BY observed_at DESC
            LIMIT 1
            """,
            (check_id,),
        ).fetchone()
        if last_ok:
            last_ok_at = datetime.strptime(last_ok["observed_at"], "%Y-%m-%d %H:%M:%S")
            current_time = datetime.strptime(observed_at, "%Y-%m-%d %H:%M:%S")
            duration_minutes = (current_time - last_ok_at).total_seconds() / 60
        else:
            duration_minutes = incident_open_after + 1
        if duration_minutes >= incident_open_after and not active_incident:
            record_health_incident(
                db,
                check_id,
                f"{status}: {reason or 'Health-Check meldet einen nicht-OK-Zustand.'}",
                observed_at,
                status,
            )
        if active_incident:
            if not active_incident["ticket_id"]:
                create_health_incident_ticket(db, active_incident["id"])
            db.execute(
                """
                UPDATE health_incidents
                SET last_status = ?, last_observed_at = ?
                WHERE id = ?
                """,
                (status, observed_at, active_incident["id"]),
            )
        return

    if active_incident and status == "OK":
        last_non_ok = db.execute(
            """
            SELECT observed_at
            FROM health_check_results
            WHERE check_id = ? AND status != 'OK'
            ORDER BY observed_at DESC
            LIMIT 1
            """,
            (check_id,),
        ).fetchone()
        if last_non_ok:
            last_non_ok_at = datetime.strptime(last_non_ok["observed_at"], "%Y-%m-%d %H:%M:%S")
            current_time = datetime.strptime(observed_at, "%Y-%m-%d %H:%M:%S")
            duration_minutes = (current_time - last_non_ok_at).total_seconds() / 60
        else:
            duration_minutes = incident_close_after + 1
        if duration_minutes >= incident_close_after:
            close_health_incident(db, active_incident["id"], observed_at)
        else:
            db.execute(
                """
                UPDATE health_incidents
                SET last_status = ?, last_observed_at = ?
                WHERE id = ?
                """,
                (status, observed_at, active_incident["id"]),
            )
        return

    if active_incident:
        db.execute(
            """
            UPDATE health_incidents
            SET last_status = ?, last_observed_at = ?
            WHERE id = ?
            """,
            (status, observed_at, active_incident["id"]),
        )
