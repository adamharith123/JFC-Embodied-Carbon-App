"""
Condition Sheet Loader

Reads the "Condition" sheet from the Standards Calc Database - the
lookup table for every Formula-column "design parameter" (e.g.
smoke_detector_coverage_area, sprinkler_coverage_area,
extinguisher_coverage_area) that isn't a Building Input.

Expected columns (case/whitespace-insensitive), up to 3 condition
key/value pairs per row:

    Parameter                        - exact variable name as used in
                                        ui_structure's Formula column
                                        (the join key)
    Condition Key 1 / Condition Value 1
    Condition Key 2 / Condition Value 2
    Condition Key 3 / Condition Value 3
                                      - "default"/"default" for a key
                                        this row doesn't condition on.
                                        A row's real condition set is
                                        whichever of the 3 pairs isn't
                                        "default" - a row can use 0
                                        (unconditioned - a flat value
                                        for the whole Parameter), 1
                                        (e.g. sprinkler_coverage_area,
                                        keyed on fire_hazard alone), or
                                        up to 3 (e.g.
                                        extinguisher_coverage_area,
                                        keyed on automatic_fixed_
                                        suppression + fire_hazard +
                                        the Minimum Rating and
                                        Classification the engineer
                                        picks per row).
    value                             - the number
    unit / note                       - documentation only, never
                                        used in calculation

A condition key is either a Building Input (resolved automatically -
see component_groups.py's CONDITION_KEY_ALIASES) or, if it isn't one,
an "extra" condition the engineer picks per row via its own selector
column in the standardized panel (see
_render_standardized_input_component) - the Rating dropdown is not
something DTS can auto-decide, since AS 2444 offers several
compliant options, not one deterministic answer.

A Parameter may have several rows (one per condition combination)
plus, recommended but not required, a fully-"default" fallback row
for when nothing else matches yet.
"""

import pandas as pd
import streamlit as st
import os

from utils.constants import CALC_RULES_DATABASE_FILE

SHEET_NAME = "Condition"

_KEY_SLOTS = [
    ("condition_key_1", "condition_value_1"),
    ("condition_key_2", "condition_value_2"),
    ("condition_key_3", "condition_value_3"),
]

# Real column names, lowercased+stripped -> canonical name this module
# uses internally. Tolerates "Condition Key" (no number, meaning slot
# 1) as well as "Condition Key 1"/"Condition Key 2"/"Condition Key 3".
_COLUMN_ALIASES = {
    "parameter": "parameter",
    "condition key": "condition_key_1",
    "condition key 1": "condition_key_1",
    "condition_key": "condition_key_1",
    "condition_key_1": "condition_key_1",
    "conditionkey": "condition_key_1",
    "condition value": "condition_value_1",
    "condition value 1": "condition_value_1",
    "condition_value": "condition_value_1",
    "condition_value_1": "condition_value_1",
    "conditionvalue": "condition_value_1",
    "condition key 2": "condition_key_2",
    "condition_key_2": "condition_key_2",
    "condition value 2": "condition_value_2",
    "condition_value_2": "condition_value_2",
    "condition key 3": "condition_key_3",
    "condition_key_3": "condition_key_3",
    "condition value 3": "condition_value_3",
    "condition_value_3": "condition_value_3",
    "value": "value",
    "unit": "unit",
    "note": "note",
    "notes": "note",
}


def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


@st.cache_data
def _load_raw_sheet(_mtime=None):
    if not CALC_RULES_DATABASE_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(CALC_RULES_DATABASE_FILE, sheet_name=SHEET_NAME)
    except (ValueError, FileNotFoundError):
        return pd.DataFrame()

    df = df.rename(columns={c: _COLUMN_ALIASES.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns})

    required = {"parameter", "condition_key_1", "condition_value_1", "value"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df["parameter"] = df["parameter"].astype(str).str.strip()
    for key_col, value_col in _KEY_SLOTS:
        if key_col not in df.columns:
            df[key_col] = "default"
        if value_col not in df.columns:
            df[value_col] = "default"
        df[key_col] = df[key_col].fillna("default").astype(str).str.strip()
        df[value_col] = df[value_col].fillna("default").astype(str).str.strip()

    return df


def _row_conditions(row):
    """
    The {condition_key: condition_value} dict for one Condition-sheet
    row, lowercased, excluding any slot left as "default"/blank - i.e.
    this row's actual, real condition set (0 to 3 entries).
    """
    conditions = {}
    for key_col, value_col in _KEY_SLOTS:
        key = str(row.get(key_col, "")).strip().lower()
        if key and key not in ("default", "nan", ""):
            conditions[key] = str(row.get(value_col, "")).strip().lower()
    return conditions


def _param_rows(df, parameter_name):
    return df[df["parameter"].str.lower() == str(parameter_name).strip().lower()]


def get_condition_value(parameter_name, conditions=None):
    """
    Resolves the numeric value for a Formula-column design parameter
    against however many condition key/value pairs you can currently
    supply (0 to 3) - conditions is a dict of
    {condition_key: condition_value}, keys/values matched case-
    insensitively.

    A row matches only if EVERY condition key it specifies is present
    in `conditions` with the same value (a row is never matched on a
    subset of its own conditions) - so a 3-key parameter like
    extinguisher_coverage_area won't resolve to anything until all 3
    are supplied, same as the sheet author intended. Falls back to a
    fully-unconditioned row (all 3 slots "default") for this Parameter
    if one exists and nothing more specific matched.

    Returns (value, note) on success, or (None, None) if nothing
    matches yet - never raises, since a Building Input not set yet, or
    an extra per-row selector not chosen yet, is an expected
    in-progress state, not a bug.
    """
    df = _load_raw_sheet(_mtime=_file_mtime(CALC_RULES_DATABASE_FILE))
    if df.empty:
        return None, None

    rows = _param_rows(df, parameter_name)
    if rows.empty:
        return None, None

    conditions = {str(k).strip().lower(): str(v).strip().lower() for k, v in (conditions or {}).items() if v is not None}

    default_row = None
    for _, row in rows.iterrows():
        row_conditions = _row_conditions(row)
        if not row_conditions:
            if default_row is None:
                default_row = row
            continue
        if all(conditions.get(k) == v for k, v in row_conditions.items()):
            note = row.get("note") if pd.notna(row.get("note")) else None
            return float(row["value"]), note

    if default_row is not None:
        note = default_row.get("note") if pd.notna(default_row.get("note")) else None
        return float(default_row["value"]), note

    return None, None


def parameter_condition_keys(parameter_name):
    """
    Every distinct non-default condition key used anywhere for this
    Parameter, in first-seen order (Condition Key 1's entries before
    Condition Key 2's, before Condition Key 3's, matching the order
    the sheet author built the lookup in). Returns [] for an
    unconditioned parameter.
    """
    df = _load_raw_sheet(_mtime=_file_mtime(CALC_RULES_DATABASE_FILE))
    if df.empty:
        return []

    rows = _param_rows(df, parameter_name)
    seen = []
    for _, row in rows.iterrows():
        for key_col, _value_col in _KEY_SLOTS:
            key = str(row.get(key_col, "")).strip().lower()
            if key and key not in ("default", "nan", "") and key not in seen:
                seen.append(key)
    return seen


def parameter_condition_options(parameter_name, condition_key):
    """
    Every distinct value ever used for one condition key on this
    Parameter (e.g. parameter_condition_options("extinguisher_coverage_area",
    "automatic_fixed_suppression") -> ["no", "yes"]), for populating
    that key's selector column with real options straight from the
    sheet - sorted for a stable dropdown order.

    This is the union across every OTHER condition combination too
    (a table's Selectbox column can't offer per-row options
    conditioned on another cell in the same row - same limitation as
    Required FRL (min) for Wall Assemblies) - the actual combination
    picked is validated at Calculate time instead of restricted at
    pick time.
    """
    df = _load_raw_sheet(_mtime=_file_mtime(CALC_RULES_DATABASE_FILE))
    if df.empty:
        return []

    rows = _param_rows(df, parameter_name)
    key = str(condition_key).strip().lower()
    values = set()
    for _, row in rows.iterrows():
        for key_col, value_col in _KEY_SLOTS:
            if str(row.get(key_col, "")).strip().lower() == key:
                values.add(str(row.get(value_col, "")).strip())
    return sorted(v for v in values if v)