"""Restore a verified SQLite backup while Inventory Pro is stopped."""

from __future__ import annotations

import argparse

import app as inventory_app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", help="Path to a .db, .zip, .db.enc or .zip.enc backup artifact.")
    parser.add_argument(
        "--database",
        default=inventory_app.DATABASE,
        help="SQLite database file to replace; defaults to INVENTORY_DATABASE_PATH.",
    )
    arguments = parser.parse_args()
    result = inventory_app.restore_sqlite_backup(arguments.backup, arguments.database)
    print(f"Restored: {result['database']}")
    if result["rollback"]:
        print(f"Rollback snapshot: {result['rollback']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
