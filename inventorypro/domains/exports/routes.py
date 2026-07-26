"""Protected inventory export routes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import csv
import json
from io import StringIO
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping
import zipfile

from flask import Blueprint, Response, jsonify
from openpyxl import Workbook

from inventorypro.web.blueprints import stable_route

from .service import build_export_metadata, protect_spreadsheet_record, protect_spreadsheet_row


def build_exports_blueprint(
    *,
    get_db: Callable[[], Any],
    get_export_settings: Callable[[Any], Mapping[str, Any]],
    uploads_dir: Path,
    export_tables: Callable[..., dict[str, Any]],
    run_sqlite_backup: Callable[[Path], Any],
    log_activity: Callable[..., None],
    user_can: Callable[[str], bool],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    require_permission: Callable[[str], Callable[[Callable[..., Any]], Callable[..., Any]]],
) -> Blueprint:
    """Create export endpoints while preserving their URLs and permissions."""
    blueprint = Blueprint("exports", __name__)
    table_names: Sequence[str] = (
        "categories",
        "asset_categories",
        "locations",
        "devices",
        "assets",
        "asset_devices",
        "maintenance_tasks",
        "asset_assignment_history",
        "vendors",
        "contracts",
        "purchase_orders",
        "purchase_order_items",
        "attachments",
    )

    def add_uploads(archive: zipfile.ZipFile) -> None:
        for path in uploads_dir.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=str(Path("uploads") / path.relative_to(uploads_dir)))

    @stable_route(blueprint, "/api/export", methods=["GET"])
    @login_required
    @require_permission("server_settings.manage")
    def export_data():
        database = get_db()
        settings = get_export_settings(database)
        if not settings["importExport"]["exportAllowed"]:
            return jsonify({"error": "Export ist deaktiviert."}), 403
        export_format = settings["importExport"]["exportFormat"]
        include_uploads = settings["importExport"]["includeUploads"]
        temp_dir = Path(tempfile.mkdtemp(prefix="inventory_export_"))
        archive_path = None
        try:
            if export_format == "sqlite":
                database_path = temp_dir / "inventory.db"
                run_sqlite_backup(database_path)
                if include_uploads and uploads_dir.exists():
                    archive_path = temp_dir / "inventory_export.zip"
                    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                        archive.write(database_path, arcname="inventory.db")
                        add_uploads(archive)
                else:
                    archive_path = database_path
            elif export_format == "json":
                payload = export_tables(database, table_names)
                payload["_metadata"] = build_export_metadata(export_format, table_names)
                data_path = temp_dir / "inventory_export.json"
                data_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                if include_uploads and uploads_dir.exists():
                    archive_path = temp_dir / "inventory_export.zip"
                    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                        archive.write(data_path, arcname="inventory_export.json")
                        add_uploads(archive)
                else:
                    archive_path = data_path
            elif export_format == "xlsx":
                data_path = temp_dir / "inventory_export.xlsx"
                workbook = Workbook(write_only=True)
                metadata_sheet = workbook.create_sheet(title="metadata")
                metadata_sheet.append(["key", "value"])
                for key, value in build_export_metadata(export_format, table_names).items():
                    metadata_sheet.append([key, json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value])
                for table_name in table_names:
                    worksheet = workbook.create_sheet(title=table_name[:31])
                    columns = [column["name"] for column in database.execute(f"PRAGMA table_info({table_name})").fetchall()]
                    worksheet.append(columns)
                    for row in database.execute(f"SELECT * FROM {table_name}").fetchall():
                        worksheet.append(protect_spreadsheet_row(row[column] for column in columns))
                workbook.save(data_path)
                if include_uploads and uploads_dir.exists():
                    archive_path = temp_dir / "inventory_export.zip"
                    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                        archive.write(data_path, arcname="inventory_export.xlsx")
                        add_uploads(archive)
                else:
                    archive_path = data_path
            else:
                archive_path = temp_dir / "inventory_export.zip"
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    for table_name in table_names:
                        rows = database.execute(f"SELECT * FROM {table_name}").fetchall()
                        csv_path = temp_dir / f"{table_name}.csv"
                        if rows:
                            fieldnames = rows[0].keys()
                            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                                writer.writeheader()
                                for row in rows:
                                    writer.writerow(protect_spreadsheet_record(dict(row)))
                        else:
                            csv_path.write_text("", encoding="utf-8")
                        archive.write(csv_path, arcname=f"{table_name}.csv")
                    if include_uploads and uploads_dir.exists():
                        add_uploads(archive)
            if (export_format in {"sqlite", "json", "xlsx"} and include_uploads) or export_format == "csv":
                filename = "inventory_export.zip"
                mimetype = "application/zip"
            else:
                filename = f"inventory_export.{archive_path.suffix.lstrip('.')}"
                mimetype = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if export_format == "xlsx"
                    else "application/octet-stream"
                )
            log_activity(
                database,
                "export_created",
                "server_settings",
                details={"format": export_format, "includeUploads": include_uploads, "tables": list(table_names)},
            )
            database.commit()
            return Response(
                archive_path.read_bytes(),
                mimetype=mimetype,
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @stable_route(blueprint, "/api/export/devices", methods=["GET"])
    @login_required
    def export_devices():
        database = get_db()
        if not (user_can("devices.view") or user_can("devices.manage")):
            return jsonify({"error": "Keine Berechtigung"}), 403
        settings = get_export_settings(database)
        if not settings["importExport"]["exportAllowed"]:
            return jsonify({"error": "Export ist deaktiviert."}), 403
        devices = database.execute(
            """
            SELECT d.id, d.name, d.serial_number, d.specs, d.created_at, c.name as category_name
            FROM devices d
            JOIN categories c ON d.category_id = c.id
            ORDER BY d.created_at DESC
            """
        ).fetchall()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Kategorie", "Besitzer", "Spezifikationen", "Erstellt"])
        for device in devices:
            writer.writerow(
                protect_spreadsheet_row(
                    [
                        device["id"],
                        device["name"],
                        device["category_name"],
                        device["serial_number"] or "",
                        device["specs"] or "",
                        device["created_at"],
                    ]
                )
            )
        output.seek(0)
        log_activity(database, "export_created", "device", details={"format": "csv", "count": len(devices)})
        database.commit()
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=devices.csv"},
        )

    return blueprint
