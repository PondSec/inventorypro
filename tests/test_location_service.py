import sqlite3
from unittest import TestCase

from inventorypro.domains.locations.repository import LocationRepository
from inventorypro.domains.locations.service import (
    LocationAlreadyExistsError,
    LocationInUseError,
    LocationNotFoundError,
    LocationService,
)
from inventorypro.domains.locations.validators import (
    LocationValidationError,
    validate_location_input,
)


class LocationServiceTestCase(TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            );
            CREATE TABLE devices (id INTEGER PRIMARY KEY, location_id INTEGER);
            CREATE TABLE asset_assignments (id INTEGER PRIMARY KEY, location_id INTEGER);
            """
        )
        self.activity_calls = []

    def tearDown(self):
        self.connection.close()

    def _activity_logger(self, *args, **kwargs):
        self.activity_calls.append((args, kwargs))

    def test_validator_normalizes_text_and_rejects_missing_name(self):
        location = validate_location_input({"name": "  Büro  ", "description": " Nord "})
        self.assertEqual(location.name, "Büro")
        self.assertEqual(location.description, "Nord")
        with self.assertRaisesRegex(LocationValidationError, "Name ist erforderlich"):
            validate_location_input({"name": "  "})

    def test_create_list_and_duplicate_location(self):
        service = LocationService(LocationRepository(), self._activity_logger)
        service.create(self.connection, {"name": "Büro", "description": "Nord"})
        self.assertEqual(
            service.list_locations(self.connection),
            [{"id": 1, "name": "Büro", "description": "Nord"}],
        )
        self.assertEqual(self.activity_calls[0][0][1:3], ("create", "location"))
        with self.assertRaises(LocationAlreadyExistsError):
            service.create(self.connection, {"name": "Büro"})

    def test_update_reports_missing_locations_and_commits_changes(self):
        service = LocationService(LocationRepository(), self._activity_logger)
        service.create(self.connection, {"name": "Büro"})
        service.update(self.connection, 1, {"name": "Büro Süd", "description": "Etage 2"})
        self.assertEqual(service.list_locations(self.connection)[0]["name"], "Büro Süd")
        with self.assertRaises(LocationNotFoundError):
            service.update(self.connection, 99, {"name": "Fehlt"})

    def test_delete_handles_missing_referenced_and_unreferenced_locations(self):
        service = LocationService(LocationRepository(), self._activity_logger)
        with self.assertRaises(LocationNotFoundError):
            service.delete(self.connection, 99)

        service.create(self.connection, {"name": "Verwendet"})
        self.connection.execute("INSERT INTO devices (id, location_id) VALUES (1, 1)")
        self.connection.execute("INSERT INTO asset_assignments (id, location_id) VALUES (1, 1)")
        self.connection.commit()
        with self.assertRaises(LocationInUseError) as raised:
            service.delete(self.connection, 1)
        self.assertEqual((raised.exception.devices, raised.exception.assignments), (1, 1))

        service.create(self.connection, {"name": "Leer"})
        service.delete(self.connection, 2)
        self.assertEqual([location["name"] for location in service.list_locations(self.connection)], ["Verwendet"])
