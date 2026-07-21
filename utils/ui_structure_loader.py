"""
UI Structure Loader

Reads the "ui_structure" sheet from the Standards Calc Database and
builds the same shapes the page code used to hand-write as Python
dicts: CATEGORY_SUBCATEGORIES, CATEGORY_APPARATUS_MAP, GROUP_DEFINITIONS,
SINGLE_COMPONENT_DEFINITIONS, and per-subcategory kind assignments.

This is the piece that makes the tool client-editable: adding a row to
this sheet makes a new apparatus appear in the UI, with no code change
and no redeploy. Only components with a genuinely unique UI shape
(Sprinkler Heads/Pipework, Extinguishers) are NOT declared here - they
stay hand-written in the page and are merged in separately.

Expected columns in the "ui_structure" sheet:

    Category           - integer 1-10
    Category Name       - display name for the category (only needs
                           to be filled once per category; repeated
                           rows are ignored after the first)
    Group               - if this apparatus is nested under an
                           expandable group (e.g. "Wall Assemblies"),
                           the group's display name. Leave blank for
                           a standalone entry.
    Label               - display name for this component
    Apparatus            - exact name in the Carbon Database's
                            Apparatus Output sheet
    Archetype           - "Input", "Linked Child", or
                           "Cross-Category Counter"
    Include Spacing      - Y/N (Input archetype only)
    Units                - comma-separated, e.g. "m2" or "kg,L"
                            (Input archetype only, ignored if Include
                            Spacing is Y)
    Parent               - the Label this mirrors (Linked Child), or
                            blank
    Linked Mode          - "Choice" or "Override Only" (Linked Child
                            only; defaults to "Choice")
    Counted Apparatus     - comma-separated Labels to offer as
                            checkboxes (Cross-Category Counter only)
    Disclaimer           - optional warning text shown under the input
    Requires FRL          - "Y" to show a separate FRL(min) selector
                            next to Value/Product Type (Input archetype
                            only) - see the frl_reference sheet and
                            utils/proposed_design_calculations.py
                            (get_frl_options/resolve_frl_multiplier)
"""

import pandas as pd
import streamlit as st
import os

from utils.constants import CALC_RULES_DATABASE_FILE
from utils.component_groups import (
    component_spec,
    KIND_INPUT,
    KIND_LINKED_CHILD,
    KIND_CROSS_CATEGORY_COUNTER,
)

ARCHETYPE_MAP = {
    "input": KIND_INPUT,
    "linked child": KIND_LINKED_CHILD,
    "cross-category counter": KIND_CROSS_CATEGORY_COUNTER,
}

# "Unavailable" is a sentinel, not a real archetype - it registers a
# subcategory (and category name) with no component behind it, for
# systems that are declared but not yet built out.
UNAVAILABLE_ARCHETYPE = "unavailable"

# Sheet uses friendly names ("Total Quantity", "Grid Spacing",
# "Coverage Area", "Formula") in the "Modes" column - map to the
# internal mode keys component_groups.py expects.
MODE_NAME_MAP = {
    "total quantity": "quantity",
    "quantity": "quantity",
    "grid spacing": "grid_spacing",
    "coverage area": "coverage_area",
    "formula": "formula",
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
        return pd.read_excel(CALC_RULES_DATABASE_FILE, sheet_name="ui_structure")
    except (ValueError, FileNotFoundError):
        return pd.DataFrame()


def _split_list(cell):
    if pd.isna(cell) or not str(cell).strip():
        return []
    return [item.strip() for item in str(cell).split(",") if item.strip()]


def _row_to_spec(row):

    archetype_raw = str(row.get("Archetype", "")).strip().lower()
    kind = ARCHETYPE_MAP.get(archetype_raw)

    if kind is None:
        raise ValueError(
            f"Unrecognized Archetype '{row.get('Archetype')}' for '{row.get('Label')}'. "
            f"Must be one of: Input, Linked Child, Cross-Category Counter."
        )

    key = str(row["Label"]).strip().lower().replace(" ", "_")

    disclaimer = row.get("Disclaimer")
    disclaimer = None if pd.isna(disclaimer) or not str(disclaimer).strip() else str(disclaimer).strip()

    info = row.get("Info")
    info = None if pd.isna(info) or not str(info).strip() else str(info).strip()

    if kind == KIND_INPUT:

        modes_raw = _split_list(row.get("Modes")) or ["Total Quantity"]
        modes = [MODE_NAME_MAP.get(m.strip().lower(), "quantity") for m in modes_raw]

        multi_row = str(row.get("Allow Multiple Rows", "")).strip().upper() == "Y"
        units = _split_list(row.get("Units")) or ["units"]

        formula_system = row.get("Formula System")
        formula_system = str(formula_system).strip() if not pd.isna(formula_system) and str(formula_system).strip() else None

        formula_component = row.get("Formula Component")
        formula_component = str(formula_component).strip() if not pd.isna(formula_component) and str(formula_component).strip() else None

        formula_parameters = _split_list(row.get("Formula Parameters"))

        parent = row.get("Parent")
        parent = str(parent).strip() if not pd.isna(parent) and str(parent).strip() else None

        frl_lookup = str(row.get("Requires FRL", "")).strip().upper() == "Y"

        return component_spec(
            key, str(row["Label"]).strip(), str(row["Apparatus"]).strip(), kind,
            disclaimer=disclaimer, modes=modes, multi_row=multi_row, units=units,
            parent_key=parent, formula_system=formula_system,
            formula_component=formula_component, formula_parameters=formula_parameters,
            frl_lookup=frl_lookup, info=info,
        )

    if kind == KIND_LINKED_CHILD:

        linked_mode_raw = str(row.get("Linked Mode", "")).strip().lower()
        linked_mode = "override_only" if linked_mode_raw == "override only" else "choice"

        return component_spec(
            key, str(row["Label"]).strip(), str(row["Apparatus"]).strip(), kind,
            disclaimer=disclaimer, parent_key=str(row.get("Parent", "")).strip(),
            linked_mode=linked_mode,
        )

    if kind == KIND_CROSS_CATEGORY_COUNTER:

        apparatus = row.get("Apparatus")
        apparatus = str(apparatus).strip() if not pd.isna(apparatus) else None

        return component_spec(
            key, str(row["Label"]).strip(), apparatus, kind,
            disclaimer=disclaimer, counted_apparatus=_split_list(row.get("Counted Apparatus")),
        )


def load_ui_structure():
    """
    Returns a dict with everything the page needs to merge into its
    own hand-written structures for the bespoke categories:

        {
            "category_names": {1: "Means of Detection", ...},
            "category_subcategories": {1: ["Sampling", ...], ...},
            "apparatus_map": {(1, "Speakers"): "Speaker", ...},
            "group_definitions": {(2, "Audio"): [spec, spec, ...], ...},
            "single_component_definitions": {(8, "Fire Control Centre"): spec, ...},
            "subcategory_kind": {(2, "Audio"): "component_group", ...},
        }
    """

    df = _load_raw_sheet(_mtime=_file_mtime(CALC_RULES_DATABASE_FILE))

    category_names = {}
    category_subcategories = {}
    apparatus_map = {}
    group_definitions = {}
    single_component_definitions = {}
    subcategory_kind = {}

    if df.empty:
        return {
            "category_names": category_names,
            "category_subcategories": category_subcategories,
            "apparatus_map": apparatus_map,
            "group_definitions": group_definitions,
            "single_component_definitions": single_component_definitions,
            "subcategory_kind": subcategory_kind,
        }

    for _, row in df.iterrows():

        if pd.isna(row.get("Category")) or pd.isna(row.get("Label")):
            continue

        cat_num = int(row["Category"])
        cat_display_name = row.get("Category Name")
        group_name = row.get("Group")
        group_name = str(group_name).strip() if not pd.isna(group_name) and str(group_name).strip() else None

        if not pd.isna(cat_display_name) and str(cat_display_name).strip():
            category_names.setdefault(cat_num, str(cat_display_name).strip())

        category_subcategories.setdefault(cat_num, [])

        archetype_raw = str(row.get("Archetype", "")).strip().lower()

        if archetype_raw == UNAVAILABLE_ARCHETYPE:
            sub_name = str(row["Label"]).strip()
            if sub_name not in category_subcategories[cat_num]:
                category_subcategories[cat_num].append(sub_name)
            subcategory_kind[(cat_num, sub_name)] = "unavailable"
            continue

        spec = _row_to_spec(row)

        apparatus_map[(cat_num, spec["label"])] = spec["apparatus"]

        if group_name:

            sub_name = group_name

            if sub_name not in category_subcategories[cat_num]:
                category_subcategories[cat_num].append(sub_name)
                subcategory_kind[(cat_num, sub_name)] = "component_group"
                group_definitions[(cat_num, sub_name)] = []

            group_definitions[(cat_num, sub_name)].append(spec)

        else:

            sub_name = spec["label"]

            if sub_name not in category_subcategories[cat_num]:
                category_subcategories[cat_num].append(sub_name)

            subcategory_kind[(cat_num, sub_name)] = "single_component"
            single_component_definitions[(cat_num, sub_name)] = spec

    return {
        "category_names": category_names,
        "category_subcategories": category_subcategories,
        "apparatus_map": apparatus_map,
        "group_definitions": group_definitions,
        "single_component_definitions": single_component_definitions,
        "subcategory_kind": subcategory_kind,
    }