"""Session-bound CSRF token helpers for Flask request handlers."""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Mapping


CSRF_SESSION_KEY = "_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def get_csrf_token(session: Mapping[str, str]) -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def supplied_csrf_token(request) -> str:
    header = request.headers.get(CSRF_HEADER_NAME)
    if header:
        return header
    form_value = request.form.get("csrf_token")
    if form_value:
        return form_value
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return str(payload.get("csrfToken") or "")
    return ""


def validate_csrf_token(request, session: Mapping[str, str]) -> bool:
    expected = session.get(CSRF_SESSION_KEY)
    provided = supplied_csrf_token(request)
    return bool(expected and provided and hmac.compare_digest(expected, provided))
