import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

import app as inventory_app


class LiveServerThread(threading.Thread):
    def __init__(self, host, port):
        super().__init__(daemon=True)
        self.server = make_server(host, port, inventory_app.app)

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


class MobileInteractionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(cls.temp_dir.name)
        inventory_app.DATABASE = str(temp_path / "test_inventory.db")
        inventory_app.UPLOADS_DIR = temp_path / "uploads"
        inventory_app.APP_INSTANCE_PATH = temp_path / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = temp_path / "runtime_config.json"
        inventory_app.RUNTIME_SETTINGS_CACHE = {
            "host": "127.0.0.1",
            "port": 0,
            "debug": False,
        }

        with inventory_app.app.app_context():
            inventory_app.init_db()
            db = inventory_app.get_db()
            password_hash = inventory_app.generate_password_hash("secret1234")
            cursor = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("tester", password_hash),
            )
            inventory_app.assign_user_role(db, cursor.lastrowid, "Admin")

            db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("viewer", password_hash),
            )

            category_id = db.execute(
                "INSERT INTO categories (name, icon, fields) VALUES (?, ?, ?)",
                ("Laptops", "cpu", "[]"),
            ).lastrowid
            location_id = db.execute("SELECT id FROM locations LIMIT 1").fetchone()["id"]
            db.execute(
                "INSERT INTO devices (name, category_id, serial_number, location_id, specs) VALUES (?, ?, ?, ?, ?)",
                ("Test Gerät", category_id, "SN-001", location_id, "{}"),
            )
            db.execute(
                "INSERT INTO assets (name, notes, specs) VALUES (?, ?, ?)",
                ("Test Asset", "Für mobile Tests", "{}"),
            )
            ticket_category_id = db.execute("SELECT id FROM ticket_categories LIMIT 1").fetchone()["id"]
            db.execute(
                """
                INSERT INTO tickets (title, description, category_id, priority, status, created_by, requester_name, requester_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Mobiler Test",
                    "Ticket für UI-Tests",
                    ticket_category_id,
                    "normal",
                    "open",
                    "tester",
                    "Tester",
                    "tester@example.com",
                ),
            )
            db.execute(
                "INSERT INTO services (name, description, owner) VALUES (?, ?, ?)",
                ("Core API", "Service für Health-Ansicht", "tester"),
            )
            db.commit()

        socket_handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_handle.bind(("127.0.0.1", 0))
        _, port = socket_handle.getsockname()
        socket_handle.close()
        cls.base_url = f"http://127.0.0.1:{port}"

        cls.server_thread = LiveServerThread("127.0.0.1", port)
        cls.server_thread.start()
        time.sleep(0.2)

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.firefox.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server_thread.shutdown()
        cls.temp_dir.cleanup()

    def login(self, page):
        page.goto(f"{self.base_url}/login")
        page.fill('input[name="username"]', "tester")
        page.fill('input[name="password"]', "secret1234")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.base_url}/")

    def open_modal_and_close(self, page, open_selector, container_selector, panel_selector, close_selector):
        page.click(open_selector)
        page.wait_for_selector(panel_selector, state="visible")
        page.wait_for_function(
            "selector => { const modal = document.querySelector(selector); return modal && modal.contains(document.activeElement); }",
            arg=panel_selector,
        )
        focus_in_modal = page.evaluate(
            "selector => { const modal = document.querySelector(selector); return modal && modal.contains(document.activeElement); }",
            panel_selector,
        )
        self.assertTrue(focus_in_modal)
        self.assertTrue(page.evaluate("document.body.classList.contains('modal-open')"))

        page.click(close_selector)
        page.wait_for_selector(panel_selector, state="hidden")

        page.click(open_selector)
        page.wait_for_selector(panel_selector, state="visible")
        page.keyboard.press("Escape")
        page.wait_for_selector(panel_selector, state="hidden")

        page.click(open_selector)
        page.wait_for_selector(panel_selector, state="visible")
        page.click(container_selector, position={"x": 5, "y": 5})
        page.wait_for_selector(panel_selector, state="hidden")

    def assert_table_labels(self, page, table_selector):
        rows = page.locator(f"{table_selector} tbody tr")
        if rows.count() == 0:
            return
        cells = rows.first.locator("td")
        for index in range(cells.count()):
            label = cells.nth(index).get_attribute("data-label")
            self.assertTrue(label)

    def test_mobile_modals_and_action_menus(self):
        for width in (320, 390):
            with self.subTest(viewport=width):
                context = self.browser.new_context(viewport={"width": width, "height": 900})
                page = context.new_page()
                page.on("dialog", lambda dialog: dialog.accept())
                self.login(page)

                self.open_modal_and_close(
                    page,
                    "[data-testid='open-device-modal']",
                    "[data-testid='device-modal-container']",
                    "[data-testid='device-modal']",
                    "[data-testid='device-modal-close']",
                )

                page.click("[data-testid='dashboard-action-menu-toggle']")
                page.wait_for_selector("[data-testid='dashboard-action-menu']", state="visible")
                page.click("text=Kategorie anlegen")
                page.keyboard.press("Escape")

                page.goto(f"{self.base_url}/tickets")
                self.open_modal_and_close(
                    page,
                    "[data-testid='open-ticket-modal']",
                    "[data-testid='ticket-modal-container']",
                    "[data-testid='ticket-modal']",
                    "[data-testid='ticket-modal-close']",
                )

                page.goto(f"{self.base_url}/knowledge")
                self.open_modal_and_close(
                    page,
                    "[data-testid='open-entry-modal']",
                    "[data-testid='entry-modal-container']",
                    "[data-testid='entry-modal']",
                    "[data-testid='entry-modal-close']",
                )
                page.locator(".space-y-3.max-h-\\[520px\\] button").first.click()
                page.click("[data-testid='knowledge-action-menu-toggle']")
                page.wait_for_selector("[data-testid='knowledge-action-menu']", state="visible")
                page.click("text=Löschen")

                page.goto(f"{self.base_url}/roadmap")
                self.open_modal_and_close(
                    page,
                    "[data-testid='open-roadmap-modal']",
                    "[data-testid='roadmap-modal-container']",
                    "[data-testid='roadmap-modal']",
                    "[data-testid='roadmap-modal-close']",
                )

                page.goto(f"{self.base_url}/users")
                page.click("[data-testid='admin-roles-tab']")
                page.wait_for_selector("[data-testid='edit-role-button']")
                self.open_modal_and_close(
                    page,
                    "[data-testid='edit-role-button']",
                    "[data-testid='role-modal-container']",
                    "[data-testid='role-modal']",
                    "[data-testid='role-modal-close']",
                )
                page.click("[data-testid='admin-users-tab']")
                page.click("[data-testid='user-action-menu-toggle']")
                page.wait_for_selector("[data-testid='user-action-menu']", state="visible")
                page.click("text=Passwort reset")
                page.keyboard.press("Escape")

                page.goto(f"{self.base_url}/locations")
                page.wait_for_selector("[data-testid='location-action-menu-toggle']")
                page.click("[data-testid='location-action-menu-toggle']")
                page.wait_for_selector("[data-testid='location-action-menu']", state="visible")
                page.click("text=Löschen")
                page.keyboard.press("Escape")

                context.close()

    def test_mobile_drawer_navigation(self):
        context = self.browser.new_context(viewport={"width": 390, "height": 900})
        page = context.new_page()
        self.login(page)

        page.click("[data-sidebar-toggle]")
        page.wait_for_timeout(100)
        self.assertTrue(page.evaluate("document.body.classList.contains('sidebar-open')"))
        focus_in_sidebar = page.evaluate(
            "() => { const sidebar = document.querySelector('.app-sidebar'); return sidebar && sidebar.contains(document.activeElement); }"
        )
        self.assertTrue(focus_in_sidebar)
        page.keyboard.press("Shift+Tab")
        focus_trapped = page.evaluate(
            "() => { const sidebar = document.querySelector('.app-sidebar'); return sidebar && sidebar.contains(document.activeElement); }"
        )
        self.assertTrue(focus_trapped)
        page.keyboard.press("Escape")
        self.assertTrue(page.evaluate("document.body.classList.contains('sidebar-collapsed')"))

        page.click("[data-sidebar-toggle]")
        page.click("text=Ticketsystem")
        page.wait_for_url(f"{self.base_url}/tickets")

        queue_trigger = page.get_by_role("button", name="Ticket-Queue auswählen")
        self.assertTrue(queue_trigger.is_visible())
        queue_trigger.click()
        queue_dialog = page.get_by_role("dialog", name="Ticket-Queue auswählen")
        self.assertTrue(queue_dialog.is_visible())
        queue_dialog.get_by_role("button", name="Alle offenen Tickets").click()
        page.wait_for_timeout(100)
        self.assertIn("queue=all-open", page.url)

        filter_trigger = page.get_by_role("button", name="Ticketliste filtern")
        self.assertTrue(filter_trigger.is_visible())
        filter_trigger.click()
        self.assertTrue(page.get_by_role("dialog", name="Erweiterte Filter").is_visible())
        page.keyboard.press("Escape")
        self.assertTrue(filter_trigger.evaluate("element => element === document.activeElement"))

        page.locator("[data-ticket-index]").first.click()
        page.wait_for_selector(".sd-detail", state="visible")
        page.get_by_role("button", name="Ticketdetail schließen").click()
        page.wait_for_selector(".sd-detail", state="hidden")
        self.assertFalse(page.evaluate("document.documentElement.classList.contains('sd-detail-open')"))

        page.get_by_role("link", name="Wissen").click()
        page.wait_for_url(f"{self.base_url}/knowledge")
        page.click("[data-sidebar-toggle]")
        page.get_by_role("link", name="Benutzer & Rollen").click()
        page.wait_for_url(f"{self.base_url}/users")

        context.close()

    def test_responsive_tables_have_labels(self):
        context = self.browser.new_context(viewport={"width": 320, "height": 900})
        page = context.new_page()
        self.login(page)

        page.goto(f"{self.base_url}/")
        self.assert_table_labels(page, "table.responsive-table")

        page.goto(f"{self.base_url}/users")
        self.assert_table_labels(page, "table.responsive-table")

        page.goto(f"{self.base_url}/health")
        self.assert_table_labels(page, "table.responsive-table")

        page.goto(f"{self.base_url}/stats")
        self.assert_table_labels(page, "table.responsive-table")

        page.goto(f"{self.base_url}/settings")
        page.evaluate(
            """
            () => fetch('/api/customize', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ layoutPrefs: { sidebarWidth: 260 } })
            })
            """
        )
        page.wait_for_timeout(200)
        self.assert_table_labels(page, "table.responsive-table")

        context.close()

    def test_mobile_asset_picker_actions_do_not_overlap(self):
        context = self.browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        self.login(page)

        page.goto(f"{self.base_url}/tickets?queue=all-open")
        page.locator("[data-ticket-index]").first.click()
        page.wait_for_selector(".sd-detail", state="visible")
        page.get_by_role("button", name="Assets verknüpfen").click()

        asset_search = page.get_by_role("searchbox", name="Assets durchsuchen")
        asset_search.wait_for(state="visible")
        self.assertTrue(asset_search.is_visible())
        search_box = asset_search.bounding_box()
        self.assertIsNotNone(search_box)
        self.assertGreater(search_box["width"], 200)
        self.assertLessEqual(search_box["x"] + search_box["width"], 390)

        cancel_button = page.get_by_role("button", name="Abbrechen")
        apply_button = page.get_by_role("button", name="Übernehmen")
        cancel_box = cancel_button.bounding_box()
        apply_box = apply_button.bounding_box()
        self.assertIsNotNone(cancel_box)
        self.assertIsNotNone(apply_box)
        self.assertLessEqual(cancel_box["x"] + cancel_box["width"], apply_box["x"])
        self.assertLessEqual(apply_box["x"] + apply_box["width"], 390)

        page.get_by_role("button", name="Schließen", exact=True).click()
        page.wait_for_selector(".sd-asset-modal", state="hidden")
        page.get_by_role("button", name="Ticketdetail schließen").click()
        page.wait_for_selector(".sd-detail", state="hidden")
        self.assertFalse(page.evaluate("document.documentElement.classList.contains('sd-detail-open')"))

        context.close()


if __name__ == "__main__":
    unittest.main()
