"""UI injection helpers for PondSec AI."""
from flask import request


def _infer_ui_context():
    endpoint = request.endpoint or ""
    page = endpoint.replace("_page", "")
    return {
        "page": page or request.path,
        "path": request.path,
    }


def register_ui_inject(app):
    @app.context_processor
    def pondsec_ai_context():
        return {
            "pondsec_ai_ui_context": _infer_ui_context(),
        }
