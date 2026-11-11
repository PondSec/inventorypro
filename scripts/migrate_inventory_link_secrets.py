"""Migrate legacy Inventory-Link secrets without writing values to output."""

from __future__ import annotations

import argparse

import app as inventory_app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reencrypt-all",
        action="store_true",
        help="Encrypt all decryptable values with the first configured rotation key.",
    )
    arguments = parser.parse_args()

    with inventory_app.app.app_context():
        inventory_app.init_db()
        result = inventory_app.migrate_inventory_link_secrets(
            inventory_app.get_db(),
            reencrypt_all=arguments.reencrypt_all,
        )
    print(f"Migrated: {result['migrated']}; skipped: {result['skipped']}")
    return 0 if result["skipped"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
