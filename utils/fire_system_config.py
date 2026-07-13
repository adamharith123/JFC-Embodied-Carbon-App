"""
Fire Safety System Configuration

Central source of truth for how the Proposed Design UI's categories
and subcategories relate to the Carbon Database's "Apparatus" names.

Keeping these names here — rather than scattered through the UI file —
makes it possible to check, at a glance, that the names typed here
match exactly what's in the Carbon Database Excel file. Mismatched
names (typos, trailing spaces, renamed systems) are the most common
cause of a system silently not being found during calculation.
"""

# ==========================================================
# Category / Subcategory Structure
# ==========================================================

CATEGORY_NAMES = {
    1: "Detection",
    2: "Category 2",
    3: "Category 3",
    4: "Category 4",
    5: "Category 5",
    6: "Category 6",
    7: "Category 7",
    8: "Category 8",
    9: "Category 9",
    10: "Category 10",
}

# Which subcategories live under each category, in order.
CATEGORY_SUBCATEGORIES = {
    1: ["Heat Detectors", "Smoke Detectors"],
    2: [],
    3: [],
    4: [],
    5: [],
    6: [],
    7: [],
    8: [],
    9: [],
    10: [],
}

# Maps (category_number, subcategory_name) -> Apparatus name, exactly
# as it appears in the Carbon Database's "Apparatus Output" and
# "Product Output" sheets.
CATEGORY_APPARATUS_MAP = {
    (1, "Heat Detectors"): "Heat Detector",
    (1, "Smoke Detectors"): "Smoke Detector",
}


def get_apparatus_name(category_number, subcategory_name):
    return CATEGORY_APPARATUS_MAP.get((category_number, subcategory_name))


# ==========================================================
# Determination Types
# ==========================================================
# internal_key -> display label shown in the dropdown.
# The label folds the unit into the name itself (per spec), so the
# separate "Units" column is no longer needed in the UI table.

DETERMINATION_TYPES = {
    "total_quantity": "Total Quantity (Units)",
    "grid_spacing": "Grid Spacing (Side length metres)",
}

# Reverse lookup: display label -> internal_key. Used when reading a
# value back out of the table during calculation.
DETERMINATION_TYPE_LABELS = {label: key for key, label in DETERMINATION_TYPES.items()}

DETERMINATION_TYPE_OPTIONS = list(DETERMINATION_TYPES.values())


def get_determination_type_label(internal_key):
    return DETERMINATION_TYPES.get(internal_key, internal_key)


# ==========================================================
# DTS (Deemed-to-Satisfy) Default Values
# ==========================================================
# Simple lookup: for each (category, subcategory), what value DTS
# assumes automatically when a user selects "DTS" instead of "PBD".
# This is intentionally a plain dict rather than anything fancier —
# it's meant to be readable and editable at a glance.

DTS_DEFAULTS = {
    (1, "Heat Detectors"): {
        "determination_type": "grid_spacing",
        "value": 10,
    },
    (1, "Smoke Detectors"): {
        "determination_type": "grid_spacing",
        "value": 10,
    },
}

DEFAULT_DTS_FALLBACK = {
    "determination_type": "grid_spacing",
    "value": 10,
}


def get_dts_default(category_number, subcategory_name):
    return DTS_DEFAULTS.get(
        (category_number, subcategory_name),
        DEFAULT_DTS_FALLBACK,
    )


# ==========================================================
# Validation Helper
# ==========================================================

def validate_apparatus_names(apparatus_output_df):
    """
    Cross-checks every apparatus name referenced in
    CATEGORY_APPARATUS_MAP against what actually exists in the
    Carbon Database's Apparatus Output sheet.

    Returns a list of (subcategory_name, apparatus_name) pairs that
    don't currently match anything in the database — useful for
    catching typos or a renamed system before it causes a silent
    "not found" during calculation, rather than after.
    """

    if apparatus_output_df is None or apparatus_output_df.empty:
        return list(CATEGORY_APPARATUS_MAP.items())

    known_names = set(
        apparatus_output_df["Apparatus"].dropna().astype(str)
    )

    mismatches = []

    for (cat_num, sub_name), apparatus_name in CATEGORY_APPARATUS_MAP.items():
        if apparatus_name not in known_names:
            mismatches.append((sub_name, apparatus_name))

    return mismatches