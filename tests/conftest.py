import pytest

import app as inventory_app


@pytest.fixture(autouse=True)
def enable_flask_test_mode():
    """Keep legacy workflow tests focused on their domain behaviour.

    CSRF enforcement is enabled in production and covered explicitly in the
    security test module with this flag temporarily disabled.
    """
    previous_value = inventory_app.app.config.get("TESTING", False)
    inventory_app.app.config["TESTING"] = True
    yield
    inventory_app.app.config["TESTING"] = previous_value
