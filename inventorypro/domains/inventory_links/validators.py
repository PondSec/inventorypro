"""Validation and authorization rules for inventory-link connections."""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
from typing import Any


def normalize_inventory_link_base_url(base_url: str) -> str:
    if not base_url:
        raise ValueError("Base URL fehlt.")
    candidate = base_url.strip()
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Base URL muss mit http oder https beginnen.")
    if not parsed.netloc:
        raise ValueError("Base URL benötigt einen Host.")
    if parsed.username or parsed.password:
        raise ValueError("Base URL darf keine Zugangsdaten enthalten.")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL darf keine Query oder Fragmente enthalten.")
    path = (parsed.path or "").rstrip("/")
    if path == "/":
        path = ""
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def resolve_inventory_link_ips(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return []
    ips = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            ips.append(sockaddr[0])
    return list(dict.fromkeys(ips))


def inventory_links_allow_loopback() -> bool:
    return os.environ.get("INVENTORY_LINKS_ALLOW_LOOPBACK", "0").lower() in {"1", "true", "yes"}


def is_inventory_link_ip_blocked(ip_str: str, allow_private_network: bool) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if ip_obj.is_loopback and not inventory_links_allow_loopback():
        return True
    if ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_unspecified or ip_obj.is_reserved:
        return True
    if str(ip_obj) == "169.254.169.254":
        return True
    if ip_obj.is_private and not allow_private_network:
        return True
    return False


def validate_inventory_link_target(base_url: str, allow_private_network: bool) -> urllib.parse.SplitResult:
    normalized = normalize_inventory_link_base_url(base_url)
    parsed = urllib.parse.urlsplit(normalized)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Base URL Host konnte nicht gelesen werden.")
    resolved_ips = resolve_inventory_link_ips(hostname)
    if not resolved_ips:
        raise ValueError("Host konnte nicht aufgelöst werden.")
    for ip_str in resolved_ips:
        if is_inventory_link_ip_blocked(ip_str, allow_private_network):
            raise ValueError("Zieladresse ist nicht erlaubt.")
    return parsed


def is_inventory_link_private_ip(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if ip_obj.is_loopback:
        return inventory_links_allow_loopback()
    return (
        ip_obj.is_private
        and not ip_obj.is_link_local
        and not ip_obj.is_multicast
        and not ip_obj.is_unspecified
        and not ip_obj.is_reserved
    )


def normalize_inventory_link_connection_scope(scope: str | None) -> str:
    normalized = (scope or "internet").strip().lower()
    if normalized not in {"internet", "local"}:
        raise ValueError("Verbindungsart muss Internet oder lokales Netzwerk sein.")
    return normalized


def validate_inventory_link_configuration(
    base_url: str,
    connection_scope: str | None,
    verify_tls: bool,
    allow_private_network: bool,
) -> tuple[str, str, bool, bool]:
    """Validate an Internet or LAN inventory-link target on every request."""
    normalized = normalize_inventory_link_base_url(base_url)
    scope = normalize_inventory_link_connection_scope(connection_scope)
    parsed = urllib.parse.urlsplit(normalized)

    if scope == "internet":
        if parsed.scheme != "https":
            raise ValueError("Internet-Verbindungen benötigen HTTPS.")
        if not verify_tls:
            raise ValueError("Internet-Verbindungen müssen das TLS-Zertifikat prüfen.")
        if allow_private_network:
            raise ValueError("Internet-Verbindungen dürfen keine privaten Netzwerkziele zulassen.")
        validate_inventory_link_target(normalized, False)
        return normalized, scope, True, False

    if not allow_private_network:
        raise ValueError("Lokale Verbindungen benötigen die Freigabe für private Netzwerkziele.")
    validate_inventory_link_target(normalized, True)
    resolved_ips = resolve_inventory_link_ips(parsed.hostname)
    if not resolved_ips or any(not is_inventory_link_private_ip(ip_str) for ip_str in resolved_ips):
        raise ValueError("Lokale Verbindungen dürfen nur auf private LAN-Adressen zeigen.")
    return normalized, scope, bool(verify_tls), True


def can_manage_local_inventory_links(access: dict[str, Any]) -> bool:
    return bool(access.get("is_superuser") or "server_settings.manage" in access.get("permissions", set()))


def enforce_inventory_link_scope_access(access: dict[str, Any], connection_scope: str) -> str | None:
    if connection_scope == "local" and not can_manage_local_inventory_links(access):
        return "Lokale Inventory-Link-Verbindungen benötigen Administratorrechte."
    return None


def parse_inventory_link_login_secret(secret: str) -> tuple[str, str]:
    if not secret or ":" not in secret:
        raise ValueError("Login-Secret muss im Format Benutzername:Passwort vorliegen.")
    username, password = secret.split(":", 1)
    username = username.strip()
    if not username or not password:
        raise ValueError("Login-Secret muss Benutzername und Passwort enthalten.")
    return username, password
