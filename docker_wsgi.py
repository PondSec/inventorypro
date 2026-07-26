import app as inventory_app
from inventorypro.factory import create_app

inventory_app.init_db()

with inventory_app.app.app_context():
    settings_row = inventory_app.get_server_settings(inventory_app.get_db())
    settings, _ = inventory_app.serialize_server_settings(settings_row)
    runtime = inventory_app.load_runtime_settings()
    if not runtime or runtime == inventory_app.DEFAULT_SERVER_SETTINGS["server"]:
        runtime = settings["server"]
        inventory_app.store_runtime_settings(runtime)
    inventory_app.store_update_policy(settings["updates"])
    inventory_app.RUNTIME_SETTINGS_CACHE = runtime
    inventory_app.schedule_backup_jobs(settings)
    inventory_app.schedule_health_jobs()

application = create_app()
