"""
Project version storage — SQLite backend.

Single source of truth stored in a shared .db file, intended to sit
on a permanent on-site host machine and be accessed by multiple
engineers over the local network.
"""

import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join("data", "project_store.db")


def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT PRIMARY KEY,
                area REAL,
                notes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                version INTEGER,
                version_notes TEXT,
                timestamp TEXT,
                design_json TEXT,
                results_json TEXT,
                summary_json TEXT,
                FOREIGN KEY (project_name) REFERENCES projects(name)
            )
            """
        )
        conn.commit()


@contextmanager
def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    # WAL mode allows concurrent readers while a write is in progress —
    # important since several iPads may be viewing history while
    # someone else saves a new version.
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()


_ensure_db()


def get_project_names():
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM projects ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


def get_project_meta(project_name):
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT area, notes FROM projects WHERE name = ?",
            (project_name,),
        ).fetchone()

    if not row:
        return None

    return {"area": row[0], "notes": row[1]}


def get_next_version_number(project_name):
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(version) FROM versions WHERE project_name = ?",
            (project_name,),
        ).fetchone()

    if not row or row[0] is None:
        return 1

    return row[0] + 1


def get_project_versions(project_name):
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT version, version_notes, timestamp,
                   design_json, results_json, summary_json
            FROM versions
            WHERE project_name = ?
            ORDER BY version DESC
            """,
            (project_name,),
        ).fetchall()

    versions = []
    for r in rows:
        versions.append(
            {
                "version": r[0],
                "version_notes": r[1],
                "timestamp": r[2],
                "design": json.loads(r[3]),
                "results": json.loads(r[4]),
                "summary": json.loads(r[5]),
            }
        )
    return versions


def save_project_version(
    project_name,
    area,
    notes,
    version_notes,
    design_df,
    results_df,
    summary,
):
    version_number = get_next_version_number(project_name)
    timestamp = datetime.now().isoformat(timespec="seconds")

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (name, area, notes)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                area = excluded.area,
                notes = excluded.notes
            """,
            (project_name, area, notes),
        )

        conn.execute(
            """
            INSERT INTO versions (
                project_name, version, version_notes, timestamp,
                design_json, results_json, summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_name,
                version_number,
                version_notes,
                timestamp,
                design_df.to_json(orient="records"),
                results_df.to_json(orient="records"),
                json.dumps(summary),
            ),
        )

        conn.commit()

    return version_number