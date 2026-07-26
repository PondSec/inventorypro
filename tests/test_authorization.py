import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import app as inventory_app
from inventorypro.domains.authorization import service as authorization_service


class AuthorizationBoundaryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.previous_testing = inventory_app.app.config["TESTING"]
        inventory_app.app.config["TESTING"] = True
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
            self.admin_id = self.create_user(db, "admin-user", ["Admin"])
            self.delegated_role_id = self.create_role(
                db,
                "Delegierte Benutzerverwaltung",
                ["users.manage", "roles.assign"],
            )
            self.delegated_user_id = self.create_user(
                db,
                "delegated-user",
                ["Delegierte Benutzerverwaltung"],
            )
            self.role_manager_role_id = self.create_role(
                db,
                "Delegierte Rollenverwaltung",
                ["roles.manage"],
            )
            self.role_manager_user_id = self.create_user(
                db,
                "role-manager",
                ["Delegierte Rollenverwaltung"],
            )
            self.assignable_role_id = self.create_role(
                db,
                "Eingeschränkte Benutzerverwaltung",
                ["users.manage"],
            )
            self.target_user_id = self.create_user(db, "target-user", ["Kunde"])
            self.admin_role_id = db.execute(
                "SELECT id FROM roles WHERE name = ?", ("Admin",)
            ).fetchone()["id"]
            self.server_settings_permission_id = db.execute(
                "SELECT id FROM permissions WHERE key = ?", ("server_settings.manage",)
            ).fetchone()["id"]
            db.commit()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        inventory_app.app.config["TESTING"] = self.previous_testing
        self.temp_dir.cleanup()

    def create_role(self, db, name, permission_keys):
        role_id = db.execute(
            "INSERT INTO roles (name, description, is_system, is_superuser) VALUES (?, ?, 0, 0)",
            (name, name),
        ).lastrowid
        for permission_key in permission_keys:
            permission_id = db.execute(
                "SELECT id FROM permissions WHERE key = ?", (permission_key,)
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (role_id, permission_id),
            )
        return role_id

    def create_user(self, db, username, role_names):
        user_id = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, inventory_app.generate_password_hash("SecurePassword123!")),
        ).lastrowid
        for role_name in role_names:
            inventory_app.assign_user_role(db, user_id, role_name)
        return user_id

    def assume_identity(self, username):
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = username
            session["mfa_verified"] = True

    def assigned_role_ids(self, user_id):
        with inventory_app.app.app_context():
            return self.assigned_role_ids_from_db(inventory_app.get_db(), user_id)

    def assigned_role_ids_from_db(self, db, user_id):
        return {
            row["role_id"]
            for row in db.execute(
                "SELECT role_id FROM user_roles WHERE user_id = ?", (user_id,)
            ).fetchall()
        }

    def test_access_combines_role_permissions_and_is_cached_per_request(self):
        with inventory_app.app.test_request_context("/"):
            inventory_app.session["username"] = "delegated-user"
            access = inventory_app.get_user_access(inventory_app.get_db())

            self.assertEqual(access["user"]["id"], self.delegated_user_id)
            self.assertEqual(
                access["permissions"], {"users.manage", "roles.assign"}
            )
            self.assertFalse(access["is_superuser"])
            self.assertIs(access, inventory_app.get_user_access(inventory_app.get_db()))

    def test_delegated_user_can_assign_role_within_own_authority(self):
        self.assume_identity("delegated-user")

        response = self.client.put(
            f"/api/users/{self.target_user_id}/roles",
            json={"role_ids": [self.assignable_role_id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.assigned_role_ids(self.target_user_id), {self.assignable_role_id})

    def test_delegated_user_cannot_assign_superuser_role(self):
        self.assume_identity("delegated-user")
        before_role_ids = self.assigned_role_ids(self.target_user_id)

        response = self.client.put(
            f"/api/users/{self.target_user_id}/roles",
            json={"role_ids": [self.admin_role_id]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.assigned_role_ids(self.target_user_id), before_role_ids)

    def test_user_creation_applies_the_same_role_assignment_boundary(self):
        self.assume_identity("delegated-user")

        rejected = self.client.post(
            "/api/users",
            json={
                "username": "blocked-new-user",
                "password": "SecurePassword123!",
                "role_ids": [self.admin_role_id],
            },
        )
        self.assertEqual(rejected.status_code, 403)
        with inventory_app.app.app_context():
            missing_user = inventory_app.get_db().execute(
                "SELECT id FROM users WHERE username = ?", ("blocked-new-user",)
            ).fetchone()
        self.assertIsNone(missing_user)

        accepted = self.client.post(
            "/api/users",
            json={
                "username": "allowed-new-user",
                "password": "SecurePassword123!",
                "role_ids": [str(self.assignable_role_id)],
            },
        )
        self.assertEqual(accepted.status_code, 201)
        with inventory_app.app.app_context():
            created_user_id = inventory_app.get_db().execute(
                "SELECT id FROM users WHERE username = ?", ("allowed-new-user",)
            ).fetchone()["id"]
        self.assertEqual(
            self.assigned_role_ids(created_user_id),
            {self.assignable_role_id},
        )

    def test_invalid_role_ids_are_rejected_without_changing_assignments(self):
        self.assume_identity("admin-user")
        before_role_ids = self.assigned_role_ids(self.target_user_id)

        response = self.client.put(
            f"/api/users/{self.target_user_id}/roles",
            json={"role_ids": [999999]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.assigned_role_ids(self.target_user_id), before_role_ids)

    def test_delegated_role_manager_cannot_expand_role_permissions(self):
        self.assume_identity("role-manager")
        original = self.client.get("/api/roles")
        self.assertEqual(original.status_code, 200)
        role = next(
            entry
            for entry in original.get_json()
            if entry["id"] == self.assignable_role_id
        )

        response = self.client.put(
            f"/api/roles/{self.assignable_role_id}",
            json={
                "name": role["name"],
                "description": role["description"],
                "permission_ids": [self.server_settings_permission_id],
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_delegated_role_manager_cannot_create_role_with_broader_permissions(self):
        self.assume_identity("role-manager")

        response = self.client.post(
            "/api/roles",
            json={
                "name": "Unzulässige Erweiterung",
                "description": "darf nicht erstellt werden",
                "permission_ids": [str(self.server_settings_permission_id)],
            },
        )

        self.assertEqual(response.status_code, 403)
        with inventory_app.app.app_context():
            role = inventory_app.get_db().execute(
                "SELECT id FROM roles WHERE name = ?", ("Unzulässige Erweiterung",)
            ).fetchone()
        self.assertIsNone(role)

    def test_delegated_assignment_listing_excludes_unassignable_roles(self):
        self.assume_identity("delegated-user")

        response = self.client.get("/api/roles")

        self.assertEqual(response.status_code, 200)
        role_ids = {role["id"] for role in response.get_json()}
        self.assertIn(self.assignable_role_id, role_ids)
        self.assertNotIn(self.admin_role_id, role_ids)

    def test_service_normalizes_identifier_lists_without_coercing_invalid_values(self):
        invalid_message = "Ungültige Liste"

        self.assertEqual(
            authorization_service.normalize_identifier_list(None, invalid_message),
            ([], None),
        )
        self.assertEqual(
            authorization_service.normalize_identifier_list(["1", 2, "2"], invalid_message),
            ([1, 2], None),
        )
        for invalid_value in ("1", [True], [0], [-1], ["1.5"]):
            self.assertEqual(
                authorization_service.normalize_identifier_list(invalid_value, invalid_message),
                (None, invalid_message),
            )

    def test_service_validates_persistent_role_and_permission_identifiers(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            roles, roles_error = authorization_service.get_roles_by_ids(
                db,
                [self.assignable_role_id],
            )
            self.assertIsNone(roles_error)
            self.assertEqual(roles[0]["permission_keys"], {"users.manage"})
            self.assertEqual(
                authorization_service.get_roles_by_ids(db, []),
                ([], None),
            )
            self.assertEqual(
                authorization_service.get_roles_by_ids(db, [999999]),
                (None, "Eine oder mehrere Rollen existieren nicht."),
            )

            permission_keys, permissions_error = authorization_service.get_permission_keys_by_ids(
                db,
                [self.server_settings_permission_id],
            )
            self.assertIsNone(permissions_error)
            self.assertEqual(permission_keys, {"server_settings.manage"})
            self.assertEqual(
                authorization_service.get_permission_keys_by_ids(db, []),
                (set(), None),
            )
            self.assertEqual(
                authorization_service.get_permission_keys_by_ids(db, [999999]),
                (None, "Eine oder mehrere Berechtigungen existieren nicht."),
            )

    def test_service_resolves_missing_users_and_assigns_default_roles(self):
        with inventory_app.app.app_context():
            db = inventory_app.get_db()
            self.assertEqual(authorization_service.resolve_user_access(db, None), authorization_service.empty_access())
            self.assertEqual(
                authorization_service.resolve_user_access(db, "missing-user"),
                authorization_service.empty_access(),
            )
            admin_access = authorization_service.resolve_user_access(db, "admin-user")
            self.assertTrue(admin_access["is_superuser"])
            self.assertIn("server_settings.manage", admin_access["permissions"])

            unassigned_user_id = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("unassigned-user", "hash"),
            ).lastrowid
            authorization_service.assign_user_role(db, unassigned_user_id, "missing-role")
            self.assertEqual(self.assigned_role_ids_from_db(db, unassigned_user_id), set())
            authorization_service.ensure_default_roles(db, "missing-role")
            self.assertEqual(self.assigned_role_ids_from_db(db, unassigned_user_id), set())
            authorization_service.ensure_default_roles(db, "Kunde")
            self.assertEqual(
                self.assigned_role_ids_from_db(db, unassigned_user_id),
                {
                    db.execute(
                        "SELECT id FROM roles WHERE name = ?", ("Kunde",)
                    ).fetchone()["id"]
                },
            )

    def test_service_prevents_authority_escalation_for_delegated_managers(self):
        delegated_access = {
            "is_superuser": False,
            "permissions": {"users.manage", "roles.assign"},
        }
        superuser_access = {"is_superuser": True, "permissions": set()}
        limited_role = {"is_superuser": False, "permission_keys": {"users.manage"}}
        admin_role = {"is_superuser": True, "permission_keys": set()}

        self.assertTrue(authorization_service.can_assign_roles(delegated_access, [limited_role]))
        self.assertFalse(authorization_service.can_assign_roles(delegated_access, [admin_role]))
        self.assertTrue(authorization_service.can_assign_roles(superuser_access, [admin_role]))
        self.assertTrue(
            authorization_service.can_manage_role_permissions(
                delegated_access,
                None,
                {"users.manage"},
            )
        )
        self.assertFalse(
            authorization_service.can_manage_role_permissions(
                delegated_access,
                {"is_system": True, "is_superuser": False},
                {"users.manage"},
            )
        )
        self.assertFalse(
            authorization_service.can_manage_role_permissions(
                delegated_access,
                None,
                {"server_settings.manage"},
            )
        )
        self.assertTrue(
            authorization_service.can_manage_role_permissions(
                superuser_access,
                {"is_system": True, "is_superuser": True},
                {"server_settings.manage"},
            )
        )


if __name__ == "__main__":
    unittest.main()
