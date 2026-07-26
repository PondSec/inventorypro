import sqlite3
from unittest import TestCase

from inventorypro.domains.backups.repository import BackupRunRepository
from inventorypro.domains.backups.service import BackupService


class BackupServiceTestCase(TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE backup_runs (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                backup_path TEXT,
                backup_size_bytes INTEGER,
                message TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.executemany(
            """
            INSERT INTO backup_runs (id, status, backup_path, backup_size_bytes, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "success", "/backups/new.db", 20, "completed", "2026-01-02T00:00:00Z"),
                (2, "failed", None, None, "failed", "2026-01-01T00:00:00Z"),
            ],
        )
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def test_repository_returns_the_public_backup_history_shape(self):
        history = BackupRunRepository().list_recent(self.connection)
        self.assertEqual([item["id"] for item in history], [1, 2])
        self.assertEqual(
            history[0],
            {
                "id": 1,
                "status": "success",
                "path": "/backups/new.db",
                "sizeBytes": 20,
                "message": "completed",
                "createdAt": "2026-01-02T00:00:00Z",
            },
        )

    def test_service_loads_settings_and_forwards_the_force_flag(self):
        calls = []

        def load_settings(connection):
            self.assertIs(connection, self.connection)
            return {"backup": {"enabled": True}}

        def run_backup(connection, settings, force):
            calls.append((connection, settings, force))
            return {"status": "success", "path": "/backups/new.db"}

        service = BackupService(BackupRunRepository(), load_settings, run_backup)
        self.assertEqual(
            service.run(self.connection, {"force": True}),
            {"status": "success", "path": "/backups/new.db"},
        )
        self.assertEqual(calls, [(self.connection, {"backup": {"enabled": True}}, True)])
        service.run(self.connection, None)
        self.assertFalse(calls[-1][2])
