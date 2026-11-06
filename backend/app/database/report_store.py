
"""SQLite persistence layer for ArchLens conformance reports."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional
from contextlib import closing


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "reports.db"


def get_connection() -> sqlite3.Connection:
    """Create a database connection and initialize the reports table."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            status TEXT NOT NULL,
            report_json TEXT NOT NULL
        )
        """
    )

    connection.commit()
    return connection


def migrate_database() -> None:
    """Upgrade an existing reports database safely."""

    with closing(get_connection()) as connection:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(reports)"
            ).fetchall()
        }

        if "run_id" not in columns:
            connection.execute(
                "ALTER TABLE reports ADD COLUMN run_id TEXT"
            )

        if "updated_at" not in columns:
            connection.execute(
                "ALTER TABLE reports ADD COLUMN updated_at TEXT"
            )

        # Backfill existing reports.
        connection.execute(
            """
            UPDATE reports
            SET run_id = id
            WHERE run_id IS NULL
            """
        )

        connection.execute(
            """
            UPDATE reports
            SET updated_at = created_at
            WHERE updated_at IS NULL
            """
        )

        connection.commit()


def save_report(report: dict[str, Any]) -> str:
    """Insert a new report or update an existing report."""

    report_id = report["id"]

    serialized_report = json.dumps(report, default=str)

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO reports
            (id, run_id, created_at, updated_at, status, report_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                report["run_id"],
                report["created_at"],
                report["updated_at"],
                report.get("status", "completed"),
                serialized_report,
            ),
        )

        connection.commit()

    return report_id


def get_report(report_id: str) -> Optional[dict]:
    """Retrieve a complete report by its ID."""

    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT report_json FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row["report_json"])


def list_reports() -> list[dict]:
    """List report metadata, newest first."""

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, run_id, created_at, updated_at, status
            FROM reports
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def delete_report(report_id: str) -> bool:
    """Delete a report. Returns True if a report was deleted."""

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM reports WHERE id = ?",
            (report_id,),
        )
        connection.commit()

    return cursor.rowcount > 0


# Automatically migrate the database when this module is imported.
migrate_database()
