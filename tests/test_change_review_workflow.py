import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app


class ChangeReviewWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        inventory_app.DATABASE = str(temp_path / "test_inventory.db")
        inventory_app.UPLOADS_DIR = temp_path / "uploads"
        inventory_app.APP_INSTANCE_PATH = temp_path / "instance"
        inventory_app.RUNTIME_CONFIG_PATH = temp_path / "runtime_config.json"
        inventory_app.RUNTIME_SETTINGS_CACHE = {
            "host": "127.0.0.1",
            "port": 0,
            "debug": False,
        }

        with contextlib.redirect_stdout(io.StringIO()):
            inventory_app.init_db()

        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            password_hash = inventory_app.generate_password_hash("secret1234")
            cursor = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("review_admin", password_hash),
            )
            inventory_app.assign_user_role(db, cursor.lastrowid, "Admin")
            self.change_category_id = db.execute(
                "SELECT id FROM ticket_categories WHERE name = 'Change'"
            ).fetchone()["id"]
            self.review_category_id = db.execute(
                "SELECT id FROM ticket_categories WHERE name = 'Review'"
            ).fetchone()["id"]
            db.commit()

        self.client = inventory_app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "review_admin"
            session["mfa_verified"] = True

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_change(self, title="Geprüfter Change"):
        response = self.client.post(
            "/api/tickets",
            json={
                "title": title,
                "description": "Umsetzung mit verpflichtender Abnahme.",
                "category_id": self.change_category_id,
                "priority": "high",
                "assignee": "review_admin",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def update_status(self, ticket_id, category_id, status):
        detail = self.client.get(f"/api/tickets/{ticket_id}").get_json()
        return self.client.put(
            f"/api/tickets/{ticket_id}",
            json={
                "title": detail["title"],
                "description": detail["description"],
                "category_id": category_id,
                "priority": detail["priority"],
                "status": status,
            },
        )

    def test_review_category_is_seeded(self):
        self.assertIsInstance(self.review_category_id, int)

    def test_change_creation_creates_linked_review(self):
        payload = self.create_change()
        self.assertIsInstance(payload["review_ticket_id"], int)

        change = self.client.get(f"/api/tickets/{payload['id']}").get_json()
        review = self.client.get(f"/api/tickets/{payload['review_ticket_id']}").get_json()

        self.assertEqual(change["review_relation"]["role"], "change")
        self.assertEqual(
            change["review_relation"]["review_ticket_id"],
            payload["review_ticket_id"],
        )
        self.assertEqual(review["review_relation"]["role"], "review")
        self.assertEqual(review["review_relation"]["change_ticket_id"], payload["id"])
        self.assertEqual(review["category_name"], "Review")
        self.assertEqual(review["assignee"], "review_admin")
        self.assertEqual(review["created_by"], "System")

    def test_manual_review_requires_unlinked_change(self):
        missing_change = self.client.post(
            "/api/tickets",
            json={
                "title": "Review ohne Bezug",
                "description": "Dieser Request ist unvollständig.",
                "category_id": self.review_category_id,
            },
        )
        self.assertEqual(missing_change.status_code, 400)
        self.assertIn(
            "change_ticket_id",
            missing_change.get_json()["field_errors"],
        )

        change = self.create_change()
        duplicate_review = self.client.post(
            "/api/tickets",
            json={
                "title": "Zweites Review",
                "description": "Ein zweites Review ist nicht zulässig.",
                "category_id": self.review_category_id,
                "change_ticket_id": change["id"],
            },
        )
        self.assertEqual(duplicate_review.status_code, 400)
        self.assertIn("bereits", duplicate_review.get_json()["field_errors"]["change_ticket_id"])

    def test_change_cannot_close_before_review(self):
        payload = self.create_change()
        blocked = self.update_status(payload["id"], self.change_category_id, "resolved")

        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["code"], "change_review_required")
        self.assertEqual(
            blocked.get_json()["review_ticket_id"],
            payload["review_ticket_id"],
        )

        approved = self.update_status(
            payload["review_ticket_id"],
            self.review_category_id,
            "resolved",
        )
        self.assertEqual(approved.status_code, 200)

        closed = self.update_status(payload["id"], self.change_category_id, "resolved")
        self.assertEqual(closed.status_code, 200)

    def test_bulk_close_respects_review_gate(self):
        payload = self.create_change("Bulk-Change")
        blocked = self.client.patch(
            "/api/tickets/bulk",
            json={
                "ticket_ids": [payload["id"]],
                "changes": {"status": "closed"},
            },
        )

        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["code"], "change_review_required")
        self.assertEqual(
            blocked.get_json()["blocked"][0]["change_ticket_id"],
            payload["id"],
        )

    def test_linked_tickets_cannot_be_deleted_or_reclassified(self):
        payload = self.create_change()
        delete_response = self.client.delete(
            f"/api/tickets/{payload['review_ticket_id']}"
        )
        self.assertEqual(delete_response.status_code, 409)
        self.assertEqual(
            delete_response.get_json()["code"],
            "ticket_review_relation_locked",
        )

        detail = self.client.get(f"/api/tickets/{payload['id']}").get_json()
        reclassify_response = self.client.put(
            f"/api/tickets/{payload['id']}",
            json={
                "title": detail["title"],
                "description": detail["description"],
                "category_id": self.review_category_id,
                "priority": detail["priority"],
                "status": detail["status"],
                "change_ticket_id": payload["id"],
            },
        )
        self.assertEqual(reclassify_response.status_code, 409)
        self.assertEqual(
            reclassify_response.get_json()["code"],
            "ticket_review_relation_locked",
        )


if __name__ == "__main__":
    unittest.main()
