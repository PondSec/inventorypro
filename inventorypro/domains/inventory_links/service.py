"""Session and diagnostic services for inventory-link connections."""

from __future__ import annotations

import base64
import http.cookiejar
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import request

from inventorypro.domains.inventory_links.validators import (
    parse_inventory_link_login_secret,
    validate_inventory_link_configuration,
)


class InventoryLinkConnectionError(RuntimeError):
    """Raised when a linked inventory instance cannot be reached."""


class InventoryLinkNoRedirect(urllib.request.HTTPRedirectHandler):
    """Expose redirect responses to the proxy instead of following them."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


class InventoryLinkSessionService:
    """Use existing application caches to authenticate and diagnose linked instances."""

    def __init__(
        self,
        *,
        login_session_cache: Any,
        login_ttl_seconds: int,
        proxy_timeout_seconds: int,
        allow_private_network_default: bool,
    ) -> None:
        self._login_session_cache = login_session_cache
        self._login_ttl_seconds = login_ttl_seconds
        self._proxy_timeout_seconds = proxy_timeout_seconds
        self._allow_private_network_default = allow_private_network_default

    @staticmethod
    def extract_cookie_header(cookie_jar: http.cookiejar.CookieJar) -> tuple[str | None, int | None]:
        cookies = []
        expiry_candidates = []
        for cookie in cookie_jar:
            cookies.append(f"{cookie.name}={cookie.value}")
            if cookie.expires:
                expiry_candidates.append(cookie.expires)
        if not cookies:
            return None, None
        expires_at = min(expiry_candidates) if expiry_candidates else None
        return "; ".join(cookies), expires_at

    def get_cached_cookie(self, link: Any, user_id: int) -> str | None:
        cache_key = f"{user_id}:{link['id']}"
        cached = self._login_session_cache.get(cache_key)
        if not cached:
            return None
        if cached["expires_at"] is None or cached["expires_at"] > time.time():
            return cached["cookie"]
        self._login_session_cache.pop(cache_key, None)
        return None

    @staticmethod
    def build_ssl_context(verify_tls: bool) -> ssl.SSLContext:
        if verify_tls:
            return ssl.create_default_context()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def login(self, base_url: str, verify_tls: bool, secret: str) -> tuple[str | None, int | None]:
        username, password = parse_inventory_link_login_secret(secret)
        login_url = urllib.parse.urljoin(f"{base_url.rstrip('/')}/", "login")
        payload = urllib.parse.urlencode({"username": username, "password": password}).encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html",
            "User-Agent": "InventoryPro-Link/1.0",
        }
        cookie_jar = http.cookiejar.CookieJar()
        handlers = [
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(cookie_jar),
        ]
        if base_url.startswith("https://"):
            handlers.append(urllib.request.HTTPSHandler(context=self.build_ssl_context(verify_tls)))
        opener = urllib.request.build_opener(*handlers)
        login_request = urllib.request.Request(login_url, data=payload, headers=headers, method="POST")
        try:
            opener.open(login_request, timeout=self._proxy_timeout_seconds).read(1024)
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise ValueError("Login fehlgeschlagen. Prüfe Benutzername/Passwort.") from error
            raise InventoryLinkConnectionError(f"Login fehlgeschlagen (HTTP {error.code}).") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
            reason = getattr(error, "reason", error)
            raise InventoryLinkConnectionError(f"Login-Verbindung fehlgeschlagen: {reason}") from error
        return self.extract_cookie_header(cookie_jar)

    def get_login_cookie(self, link: Any, secret: str, user_id: int) -> str:
        cached_cookie = self.get_cached_cookie(link, user_id)
        if cached_cookie:
            return cached_cookie
        cache_key = f"{user_id}:{link['id']}"
        cookie_header, expires_at = self.login(link["base_url"], bool(link["verify_tls"]), secret)
        if not cookie_header:
            raise ValueError("Login fehlgeschlagen. Prüfe Benutzername/Passwort.")
        self._login_session_cache.set(
            cache_key,
            {"cookie": cookie_header, "expires_at": expires_at or (time.time() + self._login_ttl_seconds)},
            self._login_ttl_seconds,
        )
        return cookie_header

    @staticmethod
    def build_target_url(base_url: str, subpath: str, query_string: bytes | str) -> str:
        base = base_url.rstrip("/")
        target = f"{base}/{subpath}" if subpath else f"{base}/"
        if query_string:
            query = query_string.decode("utf-8") if isinstance(query_string, (bytes, bytearray)) else str(query_string)
            target = f"{target}?{query}"
        return target

    def build_request_headers(self, auth_mode: str, secret: str, link: Any = None, user_id: int | None = None) -> dict[str, str]:
        headers = {}
        for key, value in request.headers.items():
            if key.lower() in {
                "host", "origin", "referer", "cookie", "authorization", "proxy-authorization",
                "content-length", "accept-encoding",
            }:
                continue
            headers[key] = value
        if auth_mode == "apiKey":
            headers["X-API-Key"] = secret
        elif auth_mode == "bearerToken":
            headers["Authorization"] = f"Bearer {secret}"
        elif auth_mode == "basic":
            encoded = base64.b64encode(secret.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded}"
        elif auth_mode == "login" and link and user_id:
            cookie_header = self.get_login_cookie(link, secret, user_id) if secret else self.get_cached_cookie(link, user_id)
            if cookie_header:
                headers["Cookie"] = cookie_header
        return headers

    def build_static_headers(self, auth_mode: str, secret: str, base_url: str | None = None, verify_tls: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if auth_mode == "apiKey":
            headers["X-API-Key"] = secret
        elif auth_mode == "bearerToken":
            headers["Authorization"] = f"Bearer {secret}"
        elif auth_mode == "basic":
            encoded = base64.b64encode(secret.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded}"
        elif auth_mode == "login" and base_url and secret:
            cookie_header, _ = self.login(base_url, verify_tls, secret)
            if cookie_header:
                headers["Cookie"] = cookie_header
        return headers

    def perform_test(self, config: dict[str, Any]) -> dict[str, Any]:
        base_url = config.get("base_url") or ""
        auth_mode = config.get("auth_mode") or "apiKey"
        secret = config.get("secret") or ""
        verify_tls = bool(config.get("verify_tls", True))
        allow_private_network = bool(config.get("allow_private_network", self._allow_private_network_default))
        connection_scope = config.get("connection_scope") or "internet"
        try:
            validate_inventory_link_configuration(base_url, connection_scope, verify_tls, allow_private_network)
        except ValueError as error:
            return {"status": "down", "error": str(error)}
        try:
            headers = self.build_static_headers(auth_mode, secret, base_url=base_url, verify_tls=verify_tls)
        except ValueError as error:
            return {"status": "unauthorized", "error": str(error)}
        except InventoryLinkConnectionError as error:
            return {"status": "down", "error": str(error)}
        last_error = None
        for path in ("/api/health/summary", "/"):
            target_url = f"{base_url.rstrip('/')}{path}"
            request_object = urllib.request.Request(target_url, headers=headers, method="GET")
            handlers = [urllib.request.ProxyHandler({}), InventoryLinkNoRedirect()]
            if base_url.startswith("https://"):
                handlers.append(urllib.request.HTTPSHandler(context=self.build_ssl_context(verify_tls)))
            opener = urllib.request.build_opener(*handlers)
            try:
                response = opener.open(request_object, timeout=self._proxy_timeout_seconds)
                payload = response.read(4096)
                info = {"statusCode": response.getcode()}
                if "application/json" in response.headers.get("Content-Type", ""):
                    try:
                        info.update(json.loads(payload.decode("utf-8")))
                    except json.JSONDecodeError:
                        pass
                return {"status": "ok", "message": "Verbindung erfolgreich.", "info": info}
            except urllib.error.HTTPError as error:
                if error.code in {401, 403}:
                    return {"status": "unauthorized", "error": "Nicht autorisiert."}
                last_error = f"HTTP {error.code}"
            except ssl.SSLError as error:
                return {"status": "down", "error": f"TLS-Fehler: {str(error)}"}
            except urllib.error.URLError as error:
                last_error = str(error.reason)
        return {"status": "down", "error": last_error or "Verbindung fehlgeschlagen."}
