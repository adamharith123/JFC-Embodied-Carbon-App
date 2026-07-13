"""
Project version storage — SQLite backend.

Single source of truth stored in a shared .db file, intended to sit
on a permanent on-site host machine and be accessed by multiple
engineers over the local network.

Version numbers are reserved atomically (via a UNIQUE constraint on
project_name + version) so two people starting a new version at the
same moment can never collide - the second person automatically gets
the next number instead.
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
                status TEXT DEFAULT 'final',
                FOREIGN KEY (project_name) REFERENCES projects(name)
            )
            """
        )
        conn.commit()

        # Migration: older databases created before "status" existed
        # get it added automatically, defaulting existing rows to 'final'.
        cols = [row[1] for row in conn.execute("PRAGMA table_info(versions)").fetchall()]
        if "status" not in cols:
            conn.execute("ALTER TABLE versions ADD COLUMN status TEXT DEFAULT 'final'")
            conn.commit()

        # Enforce one version number per project. Wrapped in try/except
        # because if duplicate (project_name, version) rows already
        # exist from before this fix, creating the index will fail -
        # in that case, duplicates need manual cleanup via the Manage
        # Version History page before this constraint can take effect.
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_project_version "
                "ON versions(project_name, version)"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass


@contextmanager
def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()


_ensure_db()


# ==========================================================
# Basic Lookups
# ==========================================================

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
                   design_json, results_json, summary_json, status
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
                "design": json.loads(r[3]) if r[3] else [],
                "results": json.loads(r[4]) if r[4] else [],
                "summary": json.loads(r[5]) if r[5] else {},
                "status": r[6] if r[6] else "final",
            }
        )
    return versions


def get_version_data(project_name, version_number):
    for v in get_project_versions(project_name):
        if v["version"] == version_number:
            return v
    return None


# ==========================================================
# Original Save (still used by 3_Existing_Design.py)
# ==========================================================

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
                design_json, results_json, summary_json, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'final')
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


# ==========================================================
# Reservation-Based Save (used by TestUI)
# ==========================================================

def reserve_next_version(project_name, area, notes):
    """
    Atomically reserves the next version number for a project by
    immediately inserting an empty 'draft' row. If two people attempt
    this at the same moment, the UNIQUE(project_name, version) index
    guarantees only one succeeds per number - the other retries with
    the next number automatically.
    """

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
        conn.commit()

    max_attempts = 10

    for _ in range(max_attempts):

        version_number = get_next_version_number(project_name)
        timestamp = datetime.now().isoformat(timespec="seconds")

        try:
            with _get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO versions (
                        project_name, version, version_notes, timestamp,
                        design_json, results_json, summary_json, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')
                    """,
                    (
                        project_name,
                        version_number,
                        "",
                        timestamp,
                        "[]",
                        "[]",
                        "{}",
                    ),
                )
                conn.commit()
            return version_number

        except sqlite3.IntegrityError:
            # Someone else claimed this version number in the
            # meantime - try the next one instead.
            continue

    raise RuntimeError(
        "Could not reserve a version number after multiple attempts. "
        "Please try again."
    )


def finalize_version(
    project_name,
    version_number,
    area,
    notes,
    version_notes,
    design_df,
    results_df,
    summary,
):
    """
    Fills in a previously-reserved draft version with real data and
    marks it as final.
    """

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
            UPDATE versions
            SET version_notes = ?,
                timestamp = ?,
                design_json = ?,
                results_json = ?,
                summary_json = ?,
                status = 'final'
            WHERE project_name = ? AND version = ?
            """,
            (
                version_notes,
                datetime.now().isoformat(timespec="seconds"),
                design_df.to_json(orient="records"),
                results_df.to_json(orient="records"),
                json.dumps(summary),
                project_name,
                version_number,
            ),
        )
        conn.commit()


def update_existing_version(
    project_name,
    version_number,
    area,
    notes,
    version_notes,
    design_df,
    results_df,
    summary,
):
    """
    Overwrites an already-final version's data - used when a saved
    version is explicitly reopened and edited. Appends a timestamped
    edit marker to the version notes so the edit history stays
    visible, rather than silently overwriting what was there before.
    """

    edit_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    edit_marker = f"\n[Edited {edit_timestamp}]"
    combined_notes = (version_notes or "") + edit_marker

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
            UPDATE versions
            SET version_notes = ?,
                timestamp = ?,
                design_json = ?,
                results_json = ?,
                summary_json = ?,
                status = 'final'
            WHERE project_name = ? AND version = ?
            """,
            (
                combined_notes,
                datetime.now().isoformat(timespec="seconds"),
                design_df.to_json(orient="records"),
                results_df.to_json(orient="records"),
                json.dumps(summary),
                project_name,
                version_number,
            ),
        )
        conn.commit()


# ==========================================================
# Editing / Deletion (used by Manage Version History)
# ==========================================================

def update_version_notes(project_name, version_number, new_notes):
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE versions
            SET version_notes = ?
            WHERE project_name = ? AND version = ?
            """,
            (new_notes, project_name, version_number),
        )
        conn.commit()


def delete_version(project_name, version_number):
    """
    Deletes a specific saved version (or draft). Does not renumber
    remaining versions, so version history stays honest.
    """
    with _get_connection() as conn:
        conn.execute(
            """
            DELETE FROM versions
            WHERE project_name = ? AND version = ?
            """,
            (project_name, version_number),
        )
        conn.commit()


def delete_project(project_name):
    """
    Deletes a project and all of its saved versions entirely.
    """
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM versions WHERE project_name = ?",
            (project_name,),
        )
        conn.execute(
            "DELETE FROM projects WHERE name = ?",
            (project_name,),
        )
        conn.commit()