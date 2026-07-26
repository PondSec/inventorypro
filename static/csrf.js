(function () {
    "use strict";

    function csrfToken() {
        const prefix = "csrf_token=";
        const cookie = document.cookie.split(";").map((value) => value.trim())
            .find((value) => value.startsWith(prefix));
        return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : "";
    }

    function isUnsafeMethod(method) {
        return !["GET", "HEAD", "OPTIONS", "TRACE"].includes((method || "GET").toUpperCase());
    }

    function isSameOrigin(resource) {
        try {
            return new URL(resource, window.location.href).origin === window.location.origin;
        } catch (_error) {
            return false;
        }
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = function (resource, options) {
        const request = resource instanceof Request ? resource : null;
        const method = (options && options.method) || (request && request.method) || "GET";
        const target = request ? request.url : resource;
        if (!isUnsafeMethod(method) || !isSameOrigin(target)) {
            return originalFetch(resource, options);
        }
        const headers = new Headers((options && options.headers) || (request && request.headers) || undefined);
        const token = csrfToken();
        if (token && !headers.has("X-CSRF-Token")) {
            headers.set("X-CSRF-Token", token);
        }
        if (request && !options) {
            return originalFetch(new Request(request, { headers }));
        }
        return originalFetch(resource, { ...(options || {}), headers });
    };

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !isUnsafeMethod(form.method || "GET")) {
            return;
        }
        const token = csrfToken();
        if (!token || form.querySelector("input[name=csrf_token]")) {
            return;
        }
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "csrf_token";
        input.value = token;
        form.appendChild(input);
    }, true);
}());
