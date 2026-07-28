"""
Condition Sheet Loader

Reads the "Condition" sheet from the Standards Calc Database - the
lookup table for every Formula-column "design parameter" (e.g.
smoke_detector_coverage_area, sprinkler_coverage_area) that isn't a
Building Input.

Expected columns (case/whitespace-insensitive):

    Parameter        - exact variable name as used in ui_structure's
                        Formula column (the join key)
    Condition key     - "default" if this Parameter never varies,
                         otherwise the Building Input variable name
                         it's keyed off (e.g. "sprinkler_hazard_classification")
    Condition value   - the exact value of that Building Input this
                         row applies to (e.g. "High Hazard"); ignored
                         when Condition key is "default"
    value             - the number
    unit / note       - documentation only, never used in calculation

A Parameter may have several rows (one per Condition value) plus,
recommended but not required, a "default" fallback row.
"""

import pandas as pd
import streamlit as st
import os

from utils.constants import CALC_RULES_DATABASE_FILE

SHEET_NAME = "Condition"

# Real column names, lowercased+stripped -> canonical name this module
# uses internally. Tolerates the sheet using "Condition Key" or
# "Condition key" or "condition_key", etc.
_COLUMN_ALIASES = {
    "parameter": "parameter",
    "condition key": "condition_key",
    "condition key 1": "condition_key",
    "condition_key": "condition_key",
    "condition_key_1": "condition_key",
    "conditionkey": "condition_key",
    "condition value": "condition_value",
    "condition value 1": "condition_value",
    "condition_value": "condition_value",
    "condition_value_1": "condition_value",
    "conditionvalue": "condition_value",
    # Read in for forward-compatibility, but get_condition_value()
    # doesn't match on these yet - no current Formula-column design
    # parameter needs two combined conditions (unlike the old
    # calc_rules extinguisher tables, which needed hazard class +
    # rating together). Add matching here if/when one does.
    "condition key 2": "condition_key_2",
    "condition_key_2": "condition_key_2",
    "condition value 2": "condition_value_2",
    "condition_value_2": "condition_value_2",
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

    required = {"parameter", "condition_key", "condition_value", "value"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df["parameter"] = df["parameter"].astype(str).str.strip()
    df["condition_key"] = df["condition_key"].astype(str).str.strip()
    df["condition_value"] = df["condition_value"].astype(str).str.strip()
    return df


def get_condition_value(parameter_name, condition_key=None, condition_value=None):
    """
    Resolves the numeric value for a Formula-column design parameter.

      - condition_key/condition_value both given: looks for a row
        matching Parameter + that exact Condition key/value pair
        first (case-insensitive on the value), falling back to a
        "default" row for the same Parameter if no exact match exists.
      - condition_key/condition_value not given (or the parameter has
        no conditioned rows at all): looks for the "default" row.

    Returns (value, note) on success, or (None, None) if nothing
    matches - never raises, since an unfilled Condition sheet or an
    unmatched Building Input value is an expected in-progress state,
    not a bug.
    """
    df = _load_raw_sheet(_mtime=_file_mtime(CALC_RULES_DATABASE_FILE))
    if df.empty:
        return None, None

    param_rows = df[df["parameter"].str.lower() == str(parameter_name).strip().lower()]
    if param_rows.empty:
        return None, None

    if condition_key and condition_value is not None:
        match = param_rows[
            (param_rows["condition_key"].str.lower() == str(condition_key).strip().lower())
            & (param_rows["condition_value"].str.lower() == str(condition_value).strip().lower())
        ]
        if not match.empty:
            row = match.iloc[0]
            note = row.get("note") if "note" in df.columns and pd.notna(row.get("note")) else None
            return float(row["value"]), note

    default_match = param_rows[param_rows["condition_key"].str.lower() == "default"]
    if not default_match.empty:
        row = default_match.iloc[0]
        note = row.get("note") if "note" in df.columns and pd.notna(row.get("note")) else None
        return float(row["value"]), note

    return None, None


def parameter_condition_key(parameter_name):
    """
    Returns the Building Input variable name this parameter is keyed
    off (e.g. "sprinkler_hazard_classification"), or None if the
    parameter is unconditioned ("default" only) or not found. Lets
    component_groups.py know which Building Input's current value to
    pass as condition_value without the caller needing to already
    know the sheet's layout.
    """
    df = _load_raw_sheet(_mtime=_file_mtime(CALC_RULES_DATABASE_FILE))
    if df.empty:
        return None

    param_rows = df[df["parameter"].str.lower() == str(parameter_name).strip().lower()]
    keys = {k for k in param_rows["condition_key"].str.lower().unique() if k and k != "default"}
    if len(keys) == 1:
        return keys.pop()
    return None