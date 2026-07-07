"""
Project version storage.

Handles persistence of project metadata and design/version history,
so designers can iterate on the same project over time and retrieve
any past version and its results.
"""

import json
import os
from datetime import datetime

STORE_PATH = os.path.join("data", "project_store.json")


def _ensure_store():
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    if not os.path.exists(STORE_PATH):
        with open(STORE_PATH, "w") as f:
            json.dump({}, f)


def _load_store():
    _ensure_store()
    with open(STORE_PATH, "r") as f:
        return json.load(f)


def _save_store(store):
    _ensure_store()
    with open(STORE_PATH, "w") as f:
        json.dump(store, f, indent=2, default=str)


def get_project_names():
    return sorted(_load_store().keys())


def get_project_meta(project_name):
    project = _load_store().get(project_name)
    if not project:
        return None
    return {
        "area": project.get("area", 0.0),
        "notes": project.get("notes", ""),
    }


def get_next_version_number(project_name):
    project = _load_store().get(project_name)
    if not project or not project.get("versions"):
        return 1
    return max(v["version"] for v in project["versions"]) + 1


def get_project_versions(project_name):
    project = _load_store().get(project_name)
    if not project:
        return []
    return sorted(
        project.get("versions", []),
        key=lambda v: v["version"],
        reverse=True,
    )


def get_version_data(project_name, version_number):
    for v in get_project_versions(project_name):
        if v["version"] == version_number:
            return v
    return None


def save_project_version(
    project_name,
    area,
    notes,
    version_notes,
    design_df,
    results_df,
    summary,
):
    store = _load_store()

    project = store.setdefault(
        project_name,
        {"area": area, "notes": notes, "versions": []},
    )

    project["area"] = area
    project["notes"] = notes

    version_number = get_next_version_number(project_name)

    project["versions"].append(
        {
            "version": version_number,
            "version_notes": version_notes,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "design": design_df.to_dict(orient="records"),
            "results": results_df.to_dict(orient="records"),
            "summary": summary,
        }
    )

    _save_store(store)

    return version_number