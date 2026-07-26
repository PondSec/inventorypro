"""Business operations for locations."""

from __future__ import annotations

from collections.abc import Callable
import sqlite3
from typing import Any, Mapping

from .repository import LocationRepository
from .validators import LocationInput, validate_location_input


class LocationAlreadyExistsError(ValueError):
    """Raised when a location name is already present."""


class LocationNotFoundError(LookupError):
    """Raised when a location no longer exists."""


class LocationInUseError(ValueError):
    """Raised when a location is referenced by inventory data."""

    def __init__(self, location_name: str, devices: int, assignments: int):
        self.location_name = location_name
        self.devices = devices
        self.assignments = assignments
        super().__init__("Standort wird noch verwendet")


class LocationService:
    """Coordinates validation, persistence, activity logging, and commits."""

    def __init__(
        self,
        repository: LocationRepository,
        activity_logger: Callable[..., None],
    ) -> None:
        self._repository = repository
        self._activity_logger = activity_logger

    def list_locations(self, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        return [dict(row) for row in self._repository.list_all(connection)]

    def create(
        self,
        connection: sqlite3.Connection,
        payload: Mapping[str, Any] | None,
    ) -> None:
        location = validate_location_input(payload)
        try:
            self._repository.create(connection, location)
        except sqlite3.IntegrityError as error:
            raise LocationAlreadyExistsError from error
        self._activity_logger(connection, "create", "location", details={"name": location.name})
        connection.commit()

    def update(
        self,
        connection: sqlite3.Connection,
        location_id: int,
        payload: Mapping[str, Any] | None,
    ) -> None:
        location = validate_location_input(payload)
        if not self._repository.update(connection, location_id, location):
            raise LocationNotFoundError
        self._activity_logger(connection, "update", "location", location_id, {"name": location.name})
        connection.commit()

    def delete(self, connection: sqlite3.Connection, location_id: int) -> None:
        location = self._repository.find(connection, location_id)
        if not location:
            raise LocationNotFoundError
        device_count, assignment_count = self._repository.reference_counts(connection, location_id)
        if device_count or assignment_count:
            raise LocationInUseError(location["name"], device_count, assignment_count)
        if not self._repository.delete(connection, location_id):
            raise LocationNotFoundError
        self._activity_logger(connection, "delete", "location", location_id)
        connection.commit()
