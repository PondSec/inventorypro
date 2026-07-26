"""Role, permission, and authorization policy helpers."""

from __future__ import annotations

from typing import Any


def empty_access() -> dict[str, Any]:
    """Return the canonical access payload for an anonymous or missing user."""
    return {
        "user": None,
        "roles": [],
        "permissions": set(),
        "is_superuser": False,
    }


def resolve_user_access(db: Any, username: str | None) -> dict[str, Any]:
    """Resolve a user's effective roles and permissions from persistent grants."""
    if not username:
        return empty_access()
    user = db.execute(
        "SELECT id, username, email, must_change_password FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not user:
        return empty_access()

    roles = db.execute(
        """
        SELECT r.id, r.name, r.is_superuser
        FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = ?
        ORDER BY r.name
        """,
        (user["id"],),
    ).fetchall()
    is_superuser = any(role["is_superuser"] for role in roles)
    if is_superuser:
        permission_rows = db.execute("SELECT key FROM permissions").fetchall()
    else:
        permission_rows = db.execute(
            """
            SELECT DISTINCT p.key
            FROM permissions p
            JOIN role_permissions rp ON rp.permission_id = p.id
            JOIN user_roles ur ON ur.role_id = rp.role_id
            WHERE ur.user_id = ?
            """,
            (user["id"],),
        ).fetchall()
    return {
        "user": dict(user),
        "roles": [dict(role) for role in roles],
        "permissions": {row["key"] for row in permission_rows},
        "is_superuser": bool(is_superuser),
    }


def assign_user_role(db: Any, user_id: int, role_name: str) -> None:
    """Assign an existing named role without duplicating the relationship."""
    role = db.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
    if not role:
        return
    db.execute(
        """
        INSERT OR IGNORE INTO user_roles (user_id, role_id)
        VALUES (?, ?)
        """,
        (user_id, role["id"]),
    )


def ensure_default_roles(db: Any, default_role_name: str) -> None:
    """Assign the configured default role to every user without a role."""
    default_role = db.execute(
        "SELECT id FROM roles WHERE name = ?", (default_role_name,)
    ).fetchone()
    if not default_role:
        return
    users_without_role = db.execute(
        """
        SELECT u.id FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        WHERE ur.user_id IS NULL
        """
    ).fetchall()
    for user in users_without_role:
        db.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            VALUES (?, ?)
            """,
            (user["id"], default_role["id"]),
        )


def normalize_identifier_list(
    value: Any,
    invalid_message: str,
) -> tuple[list[int] | None, str | None]:
    """Normalize HTML form and JSON identifier lists without coercing malformed IDs."""
    if value is None:
        return [], None
    if not isinstance(value, list):
        return None, invalid_message

    identifiers: list[int] = []
    seen_identifiers: set[int] = set()
    for raw_identifier in value:
        if isinstance(raw_identifier, bool):
            return None, invalid_message
        if isinstance(raw_identifier, int):
            identifier = raw_identifier
        elif isinstance(raw_identifier, str) and raw_identifier.strip().isdigit():
            identifier = int(raw_identifier.strip())
        else:
            return None, invalid_message
        if identifier < 1:
            return None, invalid_message
        if identifier not in seen_identifiers:
            identifiers.append(identifier)
            seen_identifiers.add(identifier)
    return identifiers, None


def get_roles_by_ids(
    db: Any,
    role_ids: list[int],
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Return requested roles with their permission keys or a validation error."""
    if not role_ids:
        return [], None
    placeholders = ", ".join("?" for _ in role_ids)
    rows = db.execute(
        f"""
        SELECT id, name, description, is_system, is_superuser
        FROM roles
        WHERE id IN ({placeholders})
        """,
        tuple(role_ids),
    ).fetchall()
    role_map = {row["id"]: dict(row) for row in rows}
    if len(role_map) != len(role_ids):
        return None, "Eine oder mehrere Rollen existieren nicht."

    permission_rows = db.execute(
        f"""
        SELECT rp.role_id, p.key
        FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE rp.role_id IN ({placeholders})
        """,
        tuple(role_ids),
    ).fetchall()
    for role in role_map.values():
        role["permission_keys"] = set()
    for row in permission_rows:
        role_map[row["role_id"]]["permission_keys"].add(row["key"])
    return [role_map[role_id] for role_id in role_ids], None


def get_permission_keys_by_ids(
    db: Any,
    permission_ids: list[int],
) -> tuple[set[str] | None, str | None]:
    """Return permission keys for requested IDs or reject unknown IDs."""
    if not permission_ids:
        return set(), None
    placeholders = ", ".join("?" for _ in permission_ids)
    rows = db.execute(
        f"SELECT id, key FROM permissions WHERE id IN ({placeholders})",
        tuple(permission_ids),
    ).fetchall()
    permission_map = {row["id"]: row["key"] for row in rows}
    if len(permission_map) != len(permission_ids):
        return None, "Eine oder mehrere Berechtigungen existieren nicht."
    return {permission_map[permission_id] for permission_id in permission_ids}, None


def can_assign_roles(access: dict[str, Any], roles: list[dict[str, Any]]) -> bool:
    """Allow role assignment only when it cannot increase the actor's authority."""
    if access.get("is_superuser"):
        return True
    actor_permissions = set(access.get("permissions") or set())
    return all(
        not role.get("is_superuser")
        and set(role.get("permission_keys") or set()).issubset(actor_permissions)
        for role in roles
    )


def can_manage_role_permissions(
    access: dict[str, Any],
    role: dict[str, Any] | None,
    permission_keys: set[str],
) -> bool:
    """Prevent delegated role managers from changing protected or broader roles."""
    if access.get("is_superuser"):
        return True
    if role and (role.get("is_system") or role.get("is_superuser")):
        return False
    return permission_keys.issubset(set(access.get("permissions") or set()))
