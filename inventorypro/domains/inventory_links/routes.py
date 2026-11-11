"""Protected inventory-link and proxy routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
import ssl
import time
import urllib.error
import urllib.request
import uuid

from flask import Blueprint, Response, jsonify, redirect, render_template, request, session, url_for

from inventorypro.web.blueprints import stable_route


def build_inventory_links_blueprint(
    *,
    get_db: Callable[[], Any],
    get_user_access: Callable[[Any], dict[str, Any]],
    get_inventory_link: Callable[[Any, int, str], Any],
    list_inventory_links: Callable[[Any, int], list[dict[str, Any]]],
    serialize_inventory_link: Callable[[Any], dict[str, Any]],
    validate_inventory_link_configuration: Callable[..., tuple[str, str, bool, bool]],
    enforce_inventory_link_scope_access: Callable[[dict[str, Any], str], str | None],
    parse_inventory_link_login_secret: Callable[[str], tuple[str, str]],
    encrypt_inventory_link_secret: Callable[[str], str],
    decrypt_inventory_link_secret: Callable[[str], str],
    perform_inventory_link_test: Callable[[dict[str, Any]], dict[str, Any]],
    update_inventory_link_health: Callable[[Any, str, str], None],
    get_cached_inventory_link_cookie: Callable[[Any, int], str | None],
    login_inventory_link_session: Callable[[str, bool, str], tuple[str | None, float | None]],
    connection_error: type[Exception],
    build_inventory_link_target_url: Callable[[str, str, bytes], str],
    build_inventory_link_request_headers: Callable[..., dict[str, str]],
    build_inventory_link_ssl_context: Callable[[bool], ssl.SSLContext],
    no_redirect_handler: type[Any],
    filter_inventory_link_response_headers: Callable[[Any, str, str], dict[str, str]],
    should_rewrite_inventory_link_response: Callable[[str], bool],
    rewrite_inventory_link_text_content: Callable[[bytes, str, str, str], bytes],
    stream_inventory_link_response: Callable[[Any], Any],
    should_rate_limit_inventory_proxy: Callable[[int], bool],
    login_session_cache: Any,
    login_ttl_seconds: int,
    proxy_timeout_seconds: int,
    allow_private_network_default: bool,
    log_activity: Callable[..., None],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Blueprint:
    """Create stable inventory-link endpoints without owning shared runtime state."""
    blueprint = Blueprint("inventory_links", __name__)

    @stable_route(blueprint, "/inventory-links/<link_id>/portal")
    @login_required
    def inventory_link_portal(link_id: str):
        access = get_user_access(get_db())
        database = get_db()
        user = access.get("user")
        if not user:
            return redirect(url_for("login"))
        link = get_inventory_link(database, user["id"], link_id)
        if not link:
            return ("Link nicht gefunden.", 404)
        return render_template(
            "inventory_link_portal.html",
            username=session.get("username"),
            permissions=sorted(access["permissions"]),
            is_superuser=access["is_superuser"],
            link=serialize_inventory_link(link),
            active_link_id=link_id,
        )

    @stable_route(blueprint, "/api/inventory-links", methods=["GET", "POST"])
    @login_required
    def inventory_links_api():
        database = get_db()
        access = get_user_access(database)
        user = access.get("user")
        if not user:
            return jsonify({"error": "Nicht angemeldet"}), 401

        if request.method == "GET":
            return jsonify(list_inventory_links(database, user["id"]))

        data = request.get_json() or {}
        display_name = (data.get("displayName") or "").strip()
        base_url = (data.get("baseUrl") or "").strip()
        auth_mode = data.get("authMode") or "apiKey"
        verify_tls = bool(data.get("verifyTls", True))
        allow_private_network = bool(data.get("allowPrivateNetwork", allow_private_network_default))
        connection_scope = data.get("connectionScope") or "internet"
        secret = data.get("secret") or ""

        if not display_name:
            return jsonify({"error": "Display-Name ist erforderlich."}), 400
        if auth_mode not in {"apiKey", "bearerToken", "basic", "login", "none"}:
            return jsonify({"error": "Ungültiger Auth-Modus."}), 400
        if auth_mode not in {"none", "login"} and not secret:
            return jsonify({"error": "Secret ist erforderlich."}), 400
        if auth_mode == "login" and secret:
            try:
                parse_inventory_link_login_secret(secret)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400

        try:
            normalized, connection_scope, verify_tls, allow_private_network = validate_inventory_link_configuration(
                base_url, connection_scope, verify_tls, allow_private_network
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        scope_error = enforce_inventory_link_scope_access(access, connection_scope)
        if scope_error:
            return jsonify({"error": scope_error}), 403

        try:
            secret_encrypted = encrypt_inventory_link_secret(secret) if secret else ""
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        link_id = str(uuid.uuid4())
        database.execute(
            """
            INSERT INTO inventory_links (
                id, user_id, display_name, base_url, verify_tls, auth_mode, secret_encrypted,
                allow_private_network, connection_scope, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                link_id, user["id"], display_name, normalized, 1 if verify_tls else 0,
                auth_mode, secret_encrypted, 1 if allow_private_network else 0, connection_scope,
            ),
        )
        log_activity(database, "create", "inventory_link", details={"link_id": link_id, "display_name": display_name})
        database.commit()
        link_row = get_inventory_link(database, user["id"], link_id)
        return jsonify(serialize_inventory_link(link_row)), 201

    @stable_route(blueprint, "/api/inventory-links/test", methods=["POST"])
    @login_required
    def inventory_links_test_draft():
        database = get_db()
        access = get_user_access(database)
        user = access.get("user")
        if not user:
            return jsonify({"error": "Nicht angemeldet"}), 401
        data = request.get_json() or {}
        base_url = (data.get("baseUrl") or "").strip()
        auth_mode = data.get("authMode") or "apiKey"
        verify_tls = bool(data.get("verifyTls", True))
        allow_private_network = bool(data.get("allowPrivateNetwork", allow_private_network_default))
        connection_scope = data.get("connectionScope") or "internet"
        secret = data.get("secret") or ""
        if auth_mode not in {"apiKey", "bearerToken", "basic", "login", "none"}:
            return jsonify({"error": "Ungültiger Auth-Modus."}), 400
        try:
            normalized, connection_scope, verify_tls, allow_private_network = validate_inventory_link_configuration(
                base_url, connection_scope, verify_tls, allow_private_network
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        scope_error = enforce_inventory_link_scope_access(access, connection_scope)
        if scope_error:
            return jsonify({"error": scope_error}), 403
        result = perform_inventory_link_test({
            "base_url": normalized,
            "verify_tls": verify_tls,
            "auth_mode": auth_mode,
            "secret": secret,
            "allow_private_network": allow_private_network,
            "connection_scope": connection_scope,
        })
        return jsonify(result), 200

    @stable_route(blueprint, "/api/inventory-links/<link_id>", methods=["PATCH", "DELETE"])
    @login_required
    def inventory_link_detail_api(link_id: str):
        database = get_db()
        access = get_user_access(database)
        user = access.get("user")
        if not user:
            return jsonify({"error": "Nicht angemeldet"}), 401
        link = get_inventory_link(database, user["id"], link_id)
        if not link:
            return jsonify({"error": "Link nicht gefunden."}), 404

        if request.method == "DELETE":
            database.execute("DELETE FROM inventory_links WHERE id = ? AND user_id = ?", (link_id, user["id"]))
            log_activity(database, "delete", "inventory_link", details={"link_id": link_id})
            database.commit()
            return jsonify({"status": "deleted"}), 200

        data = request.get_json() or {}
        display_name = (data.get("displayName") or link["display_name"]).strip()
        base_url = (data.get("baseUrl") or link["base_url"]).strip()
        auth_mode = data.get("authMode") or link["auth_mode"]
        verify_tls = bool(data.get("verifyTls", bool(link["verify_tls"])))
        allow_private_network = bool(data.get("allowPrivateNetwork", bool(link["allow_private_network"])))
        connection_scope = data.get("connectionScope") or (link["connection_scope"] or "internet")
        secret = data.get("secret")

        if not display_name:
            return jsonify({"error": "Display-Name ist erforderlich."}), 400
        if auth_mode not in {"apiKey", "bearerToken", "basic", "login", "none"}:
            return jsonify({"error": "Ungültiger Auth-Modus."}), 400
        if auth_mode == "login" and secret is None and link["secret_encrypted"]:
            try:
                existing_secret = decrypt_inventory_link_secret(link["secret_encrypted"] or "")
                parse_inventory_link_login_secret(existing_secret)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        elif auth_mode == "login" and secret:
            try:
                parse_inventory_link_login_secret(secret)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400

        try:
            normalized, connection_scope, verify_tls, allow_private_network = validate_inventory_link_configuration(
                base_url, connection_scope, verify_tls, allow_private_network
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        scope_error = enforce_inventory_link_scope_access(access, connection_scope)
        if scope_error:
            return jsonify({"error": scope_error}), 403

        secret_encrypted = link["secret_encrypted"]
        if secret is not None:
            if auth_mode not in {"none", "login"} and not secret and not secret_encrypted:
                return jsonify({"error": "Secret ist erforderlich."}), 400
            if secret:
                try:
                    secret_encrypted = encrypt_inventory_link_secret(secret)
                except ValueError as error:
                    return jsonify({"error": str(error)}), 400
            elif auth_mode == "none":
                secret_encrypted = ""

        database.execute(
            """
            UPDATE inventory_links
            SET display_name = ?, base_url = ?, verify_tls = ?, auth_mode = ?, secret_encrypted = ?,
                allow_private_network = ?, connection_scope = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                display_name, normalized, 1 if verify_tls else 0, auth_mode, secret_encrypted,
                1 if allow_private_network else 0, connection_scope, link_id, user["id"],
            ),
        )
        log_activity(database, "update", "inventory_link", details={"link_id": link_id})
        database.commit()
        updated = get_inventory_link(database, user["id"], link_id)
        return jsonify(serialize_inventory_link(updated)), 200

    @stable_route(blueprint, "/api/inventory-links/<link_id>/test", methods=["POST"])
    @login_required
    def inventory_link_test_api(link_id: str):
        database = get_db()
        access = get_user_access(database)
        user = access.get("user")
        if not user:
            return jsonify({"error": "Nicht angemeldet"}), 401
        link = get_inventory_link(database, user["id"], link_id)
        if not link:
            return jsonify({"error": "Link nicht gefunden."}), 404
        secret = ""
        if link["auth_mode"] != "none":
            try:
                secret = decrypt_inventory_link_secret(link["secret_encrypted"] or "")
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        result = perform_inventory_link_test({
            "base_url": link["base_url"],
            "verify_tls": bool(link["verify_tls"]),
            "auth_mode": link["auth_mode"],
            "secret": secret,
            "allow_private_network": bool(link["allow_private_network"]),
            "connection_scope": link["connection_scope"] or "internet",
        })
        update_inventory_link_health(database, link_id, result.get("status"))
        database.commit()
        return jsonify(result), 200

    @stable_route(blueprint, "/api/inventory-links/<link_id>/auth/status", methods=["GET"])
    @login_required
    def inventory_link_auth_status(link_id: str):
        database = get_db()
        access = get_user_access(database)
        user = access.get("user")
        if not user:
            return jsonify({"error": "Nicht angemeldet"}), 401
        link = get_inventory_link(database, user["id"], link_id)
        if not link:
            return jsonify({"error": "Link nicht gefunden."}), 404
        if link["auth_mode"] != "login":
            return jsonify({"authenticated": True}), 200
        cached_cookie = get_cached_inventory_link_cookie(link, user["id"])
        return jsonify({"authenticated": bool(cached_cookie)}), 200

    @stable_route(blueprint, "/api/inventory-links/<link_id>/auth/login", methods=["POST"])
    @login_required
    def inventory_link_auth_login(link_id: str):
        database = get_db()
        access = get_user_access(database)
        user = access.get("user")
        if not user:
            return jsonify({"error": "Nicht angemeldet"}), 401
        link = get_inventory_link(database, user["id"], link_id)
        if not link:
            return jsonify({"error": "Link nicht gefunden."}), 404
        if link["auth_mode"] != "login":
            return jsonify({"error": "Dieser Link benötigt keine Login-Authentifizierung."}), 400
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify({"error": "Benutzername und Passwort erforderlich."}), 400
        try:
            validate_inventory_link_configuration(
                link["base_url"], link["connection_scope"] or "internet",
                bool(link["verify_tls"]), bool(link["allow_private_network"]),
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        scope_error = enforce_inventory_link_scope_access(access, link["connection_scope"] or "internet")
        if scope_error:
            return jsonify({"error": scope_error}), 403
        secret = f"{username}:{password}"
        try:
            cookie_header, expires_at = login_inventory_link_session(
                link["base_url"],
                bool(link["verify_tls"]),
                secret,
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 401
        except connection_error as error:
            return jsonify({"error": str(error)}), 502
        if not cookie_header:
            return jsonify({"error": "Login fehlgeschlagen. Prüfe Benutzername/Passwort."}), 401
        cache_key = f"{user['id']}:{link['id']}"
        login_session_cache.set(cache_key, {
            "cookie": cookie_header,
            "expires_at": expires_at or (time.time() + login_ttl_seconds),
        }, login_ttl_seconds)
        update_inventory_link_health(database, link_id, "ok")
        database.commit()
        return jsonify({"authenticated": True}), 200

    @stable_route(
        blueprint,
        "/api/inventory-links/<link_id>/proxy/",
        defaults={"subpath": ""},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    @stable_route(
        blueprint,
        "/api/inventory-links/<link_id>/proxy/<path:subpath>",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    @login_required
    def inventory_link_proxy(link_id: str, subpath: str):
        database = get_db()
        access = get_user_access(database)
        user = access.get("user")
        if not user:
            return jsonify({"error": "Nicht angemeldet"}), 401
        if should_rate_limit_inventory_proxy(user["id"]):
            return jsonify({"error": "Rate limit erreicht."}), 429
        link = get_inventory_link(database, user["id"], link_id)
        if not link:
            return jsonify({"error": "Link nicht gefunden."}), 404

        try:
            validate_inventory_link_configuration(
                link["base_url"], link["connection_scope"] or "internet",
                bool(link["verify_tls"]), bool(link["allow_private_network"]),
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        scope_error = enforce_inventory_link_scope_access(access, link["connection_scope"] or "internet")
        if scope_error:
            return jsonify({"error": scope_error}), 403

        if link["auth_mode"] != "none":
            try:
                secret = decrypt_inventory_link_secret(link["secret_encrypted"] or "")
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        else:
            secret = ""

        target_url = build_inventory_link_target_url(link["base_url"], subpath, request.query_string)
        try:
            headers = build_inventory_link_request_headers(link["auth_mode"], secret, link=link, user_id=user["id"])
        except ValueError as error:
            return jsonify({"error": str(error)}), 401
        except connection_error as error:
            return jsonify({"error": str(error)}), 502
        data = None
        if request.method not in {"GET", "HEAD"}:
            data = request.get_data()
        proxy_request = urllib.request.Request(
            target_url,
            data=data if data else None,
            headers=headers,
            method=request.method,
        )

        context = None
        if link["base_url"].startswith("https://"):
            context = build_inventory_link_ssl_context(bool(link["verify_tls"]))
        handlers = [urllib.request.ProxyHandler({}), no_redirect_handler()]
        if context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=context))
        opener = urllib.request.build_opener(*handlers)

        def perform_proxy_request(request_object: urllib.request.Request):
            try:
                return opener.open(request_object, timeout=proxy_timeout_seconds)
            except urllib.error.HTTPError as error:
                return error

        try:
            response = perform_proxy_request(proxy_request)
            if link["auth_mode"] == "login" and response.getcode() in {401, 403}:
                login_session_cache.pop(f"{user['id']}:{link['id']}", None)
                try:
                    headers = build_inventory_link_request_headers(
                        link["auth_mode"], secret, link=link, user_id=user["id"]
                    )
                except ValueError as error:
                    return jsonify({"error": str(error)}), 401
                except connection_error as error:
                    return jsonify({"error": str(error)}), 502
                proxy_request = urllib.request.Request(
                    target_url,
                    data=data if data else None,
                    headers=headers,
                    method=request.method,
                )
                response = perform_proxy_request(proxy_request)
        except urllib.error.URLError as error:
            return jsonify({"error": f"Proxy-Fehler: {error.reason}"}), 502
        except ssl.SSLError as error:
            return jsonify({"error": f"TLS-Fehler: {str(error)}"}), 502

        status_code = response.getcode()
        response_headers = filter_inventory_link_response_headers(response.headers, link_id, link["base_url"])
        log_activity(database, "proxy", "inventory_link", details={"link_id": link_id, "method": request.method, "path": subpath})
        database.commit()
        content_type = response.headers.get("Content-Type", "")
        if request.method != "HEAD" and should_rewrite_inventory_link_response(content_type):
            body = response.read()
            rewritten = rewrite_inventory_link_text_content(body, content_type, link_id, link["base_url"])
            return Response(rewritten, status=status_code, headers=response_headers)
        return Response(stream_inventory_link_response(response), status=status_code, headers=response_headers)

    return blueprint
