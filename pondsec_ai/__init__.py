"""PondSec AI integration entrypoint."""
from . import context
from .db import migrate_agent_db, seed_default_tool_permissions
from .blueprints import ai_bp
from .events import start_event_processor
from .ui_inject import register_ui_inject
from .tools import register_all_tools


def register_pondsec_ai(
    app,
    get_db,
    get_user_access,
    user_can,
    ensure_ticket_access,
    log_activity,
    login_required,
    require_permission,
    require_permissions,
):
    """Register PondSec AI components with the Flask app."""
    context.init(
        get_db=get_db,
        get_user_access=get_user_access,
        user_can=user_can,
        ensure_ticket_access=ensure_ticket_access,
        log_activity=log_activity,
        login_required=login_required,
        require_permission=require_permission,
        require_permissions=require_permissions,
        app=app,
    )
    register_all_tools()
    with app.app_context():
        db = get_db()
        migrate_agent_db(db)
        seed_default_tool_permissions(db)
    app.register_blueprint(ai_bp)
    register_ui_inject(app)
    start_event_processor(app)
    return app
