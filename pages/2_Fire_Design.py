import streamlit as st
import pandas as pd
import copy
import math

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer
from utils.project_store import (
    get_project_names,
    get_project_meta,
    get_project_versions,
    reserve_next_version,
    finalize_version,
    update_existing_version,
    delete_version,
)
from utils.database_loader import load_carbon_database, get_building_classes
from utils.calculations import summarise_results
from utils.charts import create_apparatus_pie_chart, create_lifecycle_bar_chart

from utils.proposed_design_calculations import (
    calculate_equivalent_quantity,
    calculate_component_carbon,
    find_product_carbon_factors_row,
    get_available_product_types,
    calculate_sprinkler_head_quantity,
    calculate_sprinkler_pipework_default_length,
    default_linear_spacing_for_hazard,
)
from utils.standards_engine import get_parameter, calculate_quantity, get_available_condition_values
from utils.database_loader import get_building_class_applicability

from utils.proposed_design_calculations import (
    calculate_equivalent_quantity,
    calculate_component_carbon,
    find_product_carbon_factors_row,
    get_available_product_types,
)
from utils.standards_engine import (
    get_parameter,
    calculate_quantity,
    get_available_condition_values,
    get_extinguisher_requirement,
)
from utils.component_groups import (
    component_spec,
    init_group_state,
    render_component,
    render_component_group,
    calculate_component,
    calculate_component_group,
    component_group_design_rows,
    KIND_QUANTITY,
    KIND_GRID_SPACING,
    KIND_AREA,
    KIND_MASS_VOLUME,
    KIND_LENGTH,
    KIND_LINKED_CHILD,
)

from utils.database_loader import (
    load_carbon_database,
    get_building_classes,
    get_building_class_applicability,
)

# ==========================================================
# Page Configuration
# ==========================================================

st.set_page_config(
    page_title="TestUI",
    page_icon="🧪",
    layout="wide",
)

apply_global_styles()

st.markdown(
    """
    <style>
    [class*="st-key-cat_nav_na_"] button {
        background-color: #9E9E9E !important;
        color: white !important;
        border: none !important;
    }
    [class*="st-key-cat_nav_dts_"] button {
        background-color: #2E7D32 !important;
        color: white !important;
        border: none !important;
    }
    [class*="st-key-cat_nav_pbd_"] button {
        background-color: #C62828 !important;
        color: white !important;
        border: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_header("TestUI", APP_SUBTITLE, APP_STATUS)

# ==========================================================
# Category / Subcategory Taxonomy
# ==========================================================
# This is the single hand-maintained source of truth for the app's
# structure. Apparatus names here are best-guess and MUST be checked
# against the actual Carbon Database - rename freely, this is the
# only place that needs updating.

CATEGORY_NAMES = {
    1: "Means of Detection",
    2: "Means of Warning",
    3: "Means of Egress",
    4: "Means of First Aid Fire-Fighting",
    5: "Means of Restricting Fire Spread / Structural Protection",
    6: "Means of Suppression",
    7: "Means of Smoke Hazard Management",
    8: "Means of Fire Brigade Access and Intervention",
    9: "Fire Safety Management",
    10: "Special Hazards",
}

CATEGORY_SUBCATEGORIES = {
    1: [
        "Smoke Detectors", "Heat Detectors", "Aspirating Units",
        "Sampling", "Manual Call Points", "Fire Indicator Panels",
    ],
    2: [
        "Audio", "Cabling", "EWIS Panels", "Visual Alarm Devices",
    ],
    3: [
        "Emergency Luminaires", "Illuminated Exit Signs", "Directional Exit Signs",
    ],
    4: [
        "Hose Reels", "Portable Extinguishers",
    ],
    5: [
        "Plasterboard Wall Assemblies", "Speed Panel Wall Assemblies",
        "Masonry Wall Assemblies", "Concrete Wall Assemblies",
        "Fire-Resistant Mastic", "Fire Batts", "Fire-Stop Mortar",
        "Intumescent Collars", "Intumescent Pipe Wraps",
        "Fire-Resistant Joint Seals", "Fire and Smoke Dampers",
        "Applied Structural Fire Protection", "Fire Doors", "Smoke Doors",
        "Non-Fire-Rated Doors", "Fire Resistant Glazing",
        "Heat Strengthened Glazing", "Fire Shutters", "Fire Curtains",
    ],
    6: [
        "Sprinklers", "Hydrants",
    ],
    7: [
        "Smoke Exhaust Fans", "Fire Resistant Ductwork",
        "Regular Sheet Metal Ductwork",
    ],
    8: [
        "Fire Control Centre",
    ],
    9: [
        "Fire Safety Signage", "Evacuation Diagram Systems",
        "Fire Equipment Identification Signs",
    ],
    10: [
        "Data-Centre Gaseous Suppression Systems",
        "Battery Energy Storage Fire Protection Systems",
        "Commercial Kitchen Suppression Systems",
        "Carpark Special Detection Systems",
        "Atrium Fire and Smoke-Control Systems",
    ],
}

CATEGORY_APPARATUS_MAP = {
    (1, "Smoke Detectors"): "Smoke Detector",
    (1, "Heat Detectors"): "Heat Detector",
    (1, "Aspirating Units"): "Aspirating Unit",
    (1, "Sampling Pipework"): "Sampling Pipework",
    (1, "Sampling Points"): "Sampling Point",
    (1, "Manual Call Points"): "Manual Call Point",
    (1, "Fire Indicator Panels"): "Fire Indicator Panel",

    (2, "Speakers"): "Speaker",
    (2, "EWIS Panels"): "EWIS Panel",
    (2, "Amplifiers"): "Amplifier",
    (2, "Fire-Rated Cabling"): "Fire-Rated Cabling",
    (2, "Non-Fire-Rated Cabling"): "Non-Fire-Rated Cabling",
    (2, "Batteries"): "Battery",
    (2, "Visual Alarm Devices"): "Visual Alarm Device",
    (2, "Mounting Bases"): "Mounting Base",
    (2, "Sounders"): "Sounder",
    (2, "Sounder Bases"): "Sounder Base",

    (3, "Emergency Luminaires"): "Emergency Luminaire",
    (3, "Illuminated Exit Signs"): "Illuminated Exit Sign",
    (3, "Directional Exit Signs"): "Directional Exit Sign",

    (4, "Hose Reel Assemblies"): "Hose Reel Assembly",
    (4, "Hose Reel Cabinets"): "Cabinet",
    (4, "Hose Reel Pipework"): "Pipework",
    (4, "Hose Reel Valves"): "Valve",
    (4, "Portable Extinguishers"): "Portable Extinguisher",
    (4, "Extinguisher Brackets"): "Bracket",
    (4, "Extinguisher Cabinets"): "Cabinet",

    (5, "Plasterboard Wall Assemblies"): "Plasterboard Wall Assembly",
    (5, "Speed Panel Wall Assemblies"): "Speed Panel Wall Assembly",
    (5, "Masonry Wall Assemblies"): "Masonry Wall Assembly",
    (5, "Concrete Wall Assemblies"): "Concrete Wall Assembly",
    (5, "Fire-Resistant Mastic"): "Fire-Resistant Mastic",
    (5, "Fire Batts"): "Fire Batt",
    (5, "Fire-Stop Mortar"): "Fire-Stop Mortar",
    (5, "Intumescent Collars"): "Intumescent Collar",
    (5, "Intumescent Pipe Wraps"): "Intumescent Pipe Wrap",
    (5, "Fire-Resistant Joint Seals"): "Fire-Resistant Joint Seal",
    (5, "Fire and Smoke Dampers"): "Fire and Smoke Damper",
    (5, "Applied Structural Fire Protection"): "Applied Structural Fire Protection",
    (5, "Fire Doors"): "Fire Door",
    (5, "Smoke Doors"): "Smoke Door",
    (5, "Non-Fire-Rated Doors"): "Non-Fire-Rated Door",
    (5, "Fire Resistant Glazing"): "Fire Resistant Glazing",
    (5, "Heat Strengthened Glazing"): "Heat Strengthened Glazing",
    (5, "Fire Shutters"): "Fire Shutter",
    (5, "Fire Curtains"): "Fire Curtain",

    (6, "Sprinkler Heads"): "Sprinkler Head",
    (6, "Sprinkler Pipework"): "Sprinkler Pipework",
    (6, "Sprinkler Valves"): "Sprinkler Valve",
    (6, "Sprinkler Pumps"): "Sprinkler Pump",
    (6, "Hydrant Valves"): "Hydrant Valve",
    (6, "Hydrant Pipework"): "Hydrant Pipework",
    (6, "Hydrant Boosters"): "Hydrant Booster",
    (6, "Hydrant Pumps"): "Hydrant Pump",

    (7, "Smoke Exhaust Fans"): "Smoke Exhaust Fan",
    (7, "Fire Resistant Ductwork"): "Fire Resistant Ductwork",
    (7, "Regular Sheet Metal Ductwork"): "Regular Sheet Metal Ductwork",

    (8, "Fire Control Centre"): "Fire Control Centre",

    (9, "Fire Safety Signage"): "Fire Safety Signage",
    (9, "Evacuation Diagram Systems"): "Evacuation Diagram System",
    (9, "Fire Equipment Identification Signs"): "Fire Equipment Identification Sign",

    (10, "Data-Centre Gaseous Suppression Systems"): "Data-Centre Gaseous Suppression System",
    (10, "Battery Energy Storage Fire Protection Systems"): "Battery Energy Storage Fire Protection System",
    (10, "Commercial Kitchen Suppression Systems"): "Commercial Kitchen Suppression System",
    (10, "Carpark Special Detection Systems"): "Carpark Special Detection System",
    (10, "Atrium Fire and Smoke-Control Systems"): "Atrium Fire and Smoke-Control System",
}

# ==========================================================
# Component Group Definitions
# ==========================================================
# Each entry declares what's inside a "component_group" subcategory.
# Adding a new grouped category = adding a list here, no new
# render/calculate code required.

# Shared between blank_subcategory_state(), rendering, and calculation
# for the Sprinklers group's Valves/Pumps children.
SPRINKLER_GROUP_CHILD_SPECS = [
    component_spec("valves", "Sprinkler Valves", "Sprinkler Valve", KIND_LINKED_CHILD, parent_key="heads"),
    component_spec("pumps", "Sprinkler Pumps", "Sprinkler Pump", KIND_QUANTITY, unit_label="pumps"),
]

GROUP_DEFINITIONS = {

    (4, "Hose Reels"): [
        component_spec("assembly", "Hose Reel Assembly", "Hose Reel Assembly", KIND_QUANTITY, unit_label="reels"),
        component_spec("pipework", "Hose Reel Pipework", "Pipework", KIND_LENGTH),
        component_spec("cabinets", "Hose Reel Cabinets", "Cabinet", KIND_LINKED_CHILD, parent_key="assembly"),
        component_spec("valves", "Hose Reel Valves", "Valve", KIND_LINKED_CHILD, parent_key="assembly"),
    ],

    (2, "Audio"): [
        component_spec("speakers", "Speakers", "Speaker", KIND_GRID_SPACING),
        component_spec("speaker_batteries", "Speaker Batteries", "Battery", KIND_LINKED_CHILD,
                       parent_key="speakers", linked_mode="override_only"),

        component_spec("amplifiers", "Amplifiers", "Amplifier", KIND_QUANTITY, unit_label="units"),
        component_spec("amplifier_batteries", "Amplifier Batteries", "Battery", KIND_LINKED_CHILD,
                       parent_key="amplifiers", linked_mode="override_only"),

        component_spec("sounders", "Sounders", "Sounder", KIND_GRID_SPACING),
        component_spec("sounder_batteries", "Sounder Batteries", "Battery", KIND_LINKED_CHILD,
                       parent_key="sounders", linked_mode="override_only"),
        component_spec("sounder_bases", "Sounder Bases", "Sounder Base", KIND_LINKED_CHILD,
                       parent_key="sounders"),
    ],

    (2, "Cabling"): [
        component_spec("fire_rated_cabling", "Fire-Rated Cabling", "Fire-Rated Cabling", KIND_QUANTITY, unit_label="units"),
        component_spec("non_fire_rated_cabling", "Non-Fire-Rated Cabling", "Non-Fire-Rated Cabling", KIND_QUANTITY, unit_label="units"),
    ],

    (2, "EWIS Panels"): [
        component_spec("ewis_panels", "EWIS Panels", "EWIS Panel", KIND_QUANTITY, unit_label="units"),
        component_spec("ewis_batteries", "EWIS Panel Batteries", "Battery", KIND_LINKED_CHILD,
                       parent_key="ewis_panels", linked_mode="override_only"),
    ],

    (2, "Visual Alarm Devices"): [
        component_spec("visual_alarm_devices", "Visual Alarm Devices", "Visual Alarm Device", KIND_GRID_SPACING),
        component_spec("visual_alarm_batteries", "Visual Alarm Device Batteries", "Battery", KIND_LINKED_CHILD,
                       parent_key="visual_alarm_devices", linked_mode="override_only"),
        component_spec("mounting_bases", "Mounting Bases", "Mounting Base", KIND_LINKED_CHILD,
                       parent_key="visual_alarm_devices"),
    ],

    (6, "Hydrants"): [
        component_spec("hydrant_valves", "Hydrant Valves", "Hydrant Valve", KIND_QUANTITY, unit_label="valves",
                       disclaimer="A reference formula exists in the Standards Calc Database (Risers × Storeys × "
                                  "Outlets per Riser per Storey) - it's a simplified proxy, not a direct AS2419.1 "
                                  "quantity rule. Confirm the required quantity manually."),
        component_spec("hydrant_pipework", "Hydrant Pipework", "Hydrant Pipework", KIND_LENGTH),
        component_spec("hydrant_boosters", "Hydrant Boosters", "Hydrant Booster", KIND_QUANTITY, unit_label="boosters",
                       disclaimer="Typically 1 booster assembly per hydrant system - confirm against site layout and AS2419.1."),
        component_spec("hydrant_pumps", "Hydrant Pumps", "Hydrant Pump", KIND_QUANTITY, unit_label="pumps"),
    ],
}

# Subcategories needing a UI/calculation shape different from the
# default "simple" one. Anything not listed here defaults to "simple".
# Only subcategories needing a UI/calculation shape different from
# the default "simple" (N/A/DTS/PBD table) go here. Everything else
# in CATEGORY_SUBCATEGORIES defaults to "simple" automatically.
SUBCATEGORY_KIND = {
    (1, "Sampling"): "sampling_group",
    (2, "Audio"): "component_group",
    (2, "Cabling"): "component_group",
    (2, "EWIS Panels"): "component_group",
    (2, "Visual Alarm Devices"): "component_group",
    (6, "Sprinklers"): "sprinkler_group",
    (6, "Hydrants"): "component_group",
    (4, "Hose Reel Pipework"): "manual_length",
    (3, "Emergency Luminaires"): "not_implemented",
    (4, "Portable Extinguishers"): "extinguisher",
    (4, "Hose Reels"): "component_group",
    (10, "Data-Centre Gaseous Suppression Systems"): "unavailable",
    (10, "Battery Energy Storage Fire Protection Systems"): "unavailable",
    (10, "Commercial Kitchen Suppression Systems"): "unavailable",
    (10, "Carpark Special Detection Systems"): "unavailable",
    (10, "Atrium Fire and Smoke-Control Systems"): "unavailable",
    # New grouped subcategories use "component_group" - see
    # GROUP_DEFINITIONS below for what's inside each one.
}


def get_apparatus_name(cat_num, sub_name):
    return CATEGORY_APPARATUS_MAP.get((cat_num, sub_name))


def get_subcategory_kind(cat_num, sub_name):
    return SUBCATEGORY_KIND.get((cat_num, sub_name), "simple")


# ==========================================================
# Determination Types (generic "simple" kind)
# ==========================================================

DETERMINATION_TYPES = {
    "total_quantity": "Total Quantity (Units)",
    "grid_spacing": "Grid Spacing (Side length metres)",
}
DETERMINATION_TYPE_LABELS = {label: key for key, label in DETERMINATION_TYPES.items()}
DETERMINATION_TYPE_OPTIONS = list(DETERMINATION_TYPES.values())

DTS_DEFAULTS = {
    (1, "Heat Detectors"): {"determination_type": "grid_spacing", "value": 10},
    (1, "Smoke Detectors"): {"determination_type": "grid_spacing", "value": 10},
}
DEFAULT_DTS_FALLBACK = {"determination_type": "grid_spacing", "value": 10}


def get_dts_default(cat_num, sub_name):
    """
    Returns {"determination_type": ..., "value": ...} used to
    pre-fill a subcategory's table when DTS is selected.

    For subcategories with a real AS-based formula in the calc_rules
    sheet, this computes a live value from current Project
    Information. Anything not listed here falls back to a generic
    default (grid spacing of 10) as a placeholder.
    """

    info = st.session_state.get("test_project_info", {})
    building_area = info.get("building_area")
    storeys = info.get("building_storeys")
    exits_per_storey = info.get("building_exits_per_storey")

    if (cat_num, sub_name) == (1, "Smoke Detectors"):
        coverage = get_parameter("detection", "smoke_detector", "coverage_area")
        spacing = math.sqrt(coverage) if coverage else None
        return {"determination_type": "grid_spacing", "value": round(spacing, 2) if spacing else 10}

    if (cat_num, sub_name) == (1, "Heat Detectors"):
        coverage = get_parameter("detection", "heat_detector", "coverage_area")
        spacing = math.sqrt(coverage) if coverage else None
        return {"determination_type": "grid_spacing", "value": round(spacing, 2) if spacing else 10}

    if (cat_num, sub_name) == (1, "Aspirating Units"):
        coverage = get_parameter("detection", "aspirating_detection", "coverage_area")
        spacing = math.sqrt(coverage) if coverage else None
        return {"determination_type": "grid_spacing", "value": round(spacing, 2) if spacing else 10}

    if (cat_num, sub_name) == (1, "Manual Call Points"):
        qty = calculate_quantity(
            "detection", "manual_call_point", "count_formula",
            {"storeys": storeys, "exits_per_storey": exits_per_storey},
        )
        return {"determination_type": "total_quantity", "value": qty if qty is not None else 0}

    if (cat_num, sub_name) == (1, "Fire Indicator Panels"):
        return {"determination_type": "total_quantity", "value": 1}

    if (cat_num, sub_name) == (4, "Hose Reel Assemblies"):
        area_per_storey = (building_area / storeys) if (building_area and storeys) else None
        qty = calculate_quantity(
            "hose_reel", "hose_reel", "quantity_formula",
            {
                "storeys": storeys,
                "area_per_storey": area_per_storey,
                "effective_area_per_reel": get_parameter("hose_reel", "hose_reel", "effective_area_per_reel"),
            },
        )
        return {"determination_type": "total_quantity", "value": qty if qty is not None else 0}

    if (cat_num, sub_name) == (4, "Hose Reel Cabinets"):
        # Cabinets always equal the Hose Reel Assemblies count, per
        # your note that these are definitionally equal.
        hr_state = (
            st.session_state.get("test_categories", {})
            .get(4, {})
            .get("subcategories", {})
            .get("Hose Reel Assemblies")
        )
        hr_qty = None
        if hr_state and not hr_state["table"].empty:
            hr_qty = hr_state["table"].iloc[0].get("Value")
        return {"determination_type": "total_quantity", "value": hr_qty if hr_qty is not None else 0}

    if (cat_num, sub_name) == (4, "Portable Extinguishers"):
        qty = calculate_quantity(
            "extinguisher", "portable_extinguisher", "class_a_quantity_formula",
            {
                "storeys": storeys,
                "floor_area": building_area,
                "max_area_class_a": get_parameter(
                    "extinguisher", "portable_extinguisher", "max_area_class_a_no_suppression"
                ),
            },
        )
        return {"determination_type": "total_quantity", "value": qty if qty is not None else 0}

    return DTS_DEFAULTS.get((cat_num, sub_name), DEFAULT_DTS_FALLBACK)


def get_determination_type_label(internal_key):
    return DETERMINATION_TYPES.get(internal_key, internal_key)


# ==========================================================
# Sprinkler-Specific Determination Types
# ==========================================================

SPRINKLER_DETERMINATION_TYPES = {
    "quantity": "Quantity",
    "linear_spacing": "Linear Spacing (m)",
}
SPRINKLER_DETERMINATION_LABELS = {label: key for key, label in SPRINKLER_DETERMINATION_TYPES.items()}
SPRINKLER_DETERMINATION_OPTIONS = list(SPRINKLER_DETERMINATION_TYPES.values())

EXTINGUISHER_DETERMINATION_TYPES = {
    "quantity": "Quantity",
    "coverage_area": "Coverage Area (m² per extinguisher)",
}
EXTINGUISHER_DETERMINATION_LABELS = {label: key for key, label in EXTINGUISHER_DETERMINATION_TYPES.items()}
EXTINGUISHER_DETERMINATION_OPTIONS = list(EXTINGUISHER_DETERMINATION_TYPES.values())

BRACKET_CABINET_MODE_OPTIONS = ["Equal to Extinguishers", "Quantity Override"]

HAZARD_RATING_OPTIONS = get_available_condition_values("sprinkler", "sprinkler_head", "spacing_area")

PIPEWORK_MODE_OPTIONS = ["Default Formula", "Manual Override"]

# ==========================================================
# Table / State Templates
# ==========================================================

def empty_display_row():
    return pd.DataFrame(
        [{"Determination Type": None, "Value": None, "Product Type": None}]
    )


def dts_default_row(cat_num, sub_name):
    dts = get_dts_default(cat_num, sub_name)
    label = get_determination_type_label(dts["determination_type"])
    return pd.DataFrame(
        [{"Determination Type": label, "Value": dts["value"], "Product Type": None}]
    )


def pbd_default_row(cat_num, sub_name):
    dts = get_dts_default(cat_num, sub_name)
    label = get_determination_type_label(dts["determination_type"])
    return pd.DataFrame(
        [{"Determination Type": label, "Value": None, "Product Type": None}]
    )


def empty_sprinkler_heads_table():
    return pd.DataFrame(
        columns=["Product Type", "Determination Type", "Value", "Hazard Rating"]
    )


def sprinkler_heads_dts_table():
    default_hazard = "Ordinary Hazard"
    spacing_area = get_parameter("sprinkler", "sprinkler_head", "spacing_area", condition_value=default_hazard)
    linear_spacing = math.sqrt(spacing_area) if spacing_area else None
    return pd.DataFrame(
        [{
            "Product Type": None,
            "Determination Type": SPRINKLER_DETERMINATION_TYPES["linear_spacing"],
            "Value": round(linear_spacing, 2) if linear_spacing else None,
            "Hazard Rating": default_hazard,
        }]
    )


def sprinkler_heads_pbd_table():
    return pd.DataFrame(
        [{
            "Product Type": None,
            "Determination Type": SPRINKLER_DETERMINATION_TYPES["linear_spacing"],
            "Value": None,
            "Hazard Rating": "Ordinary",
        }]
    )


def blank_subcategory_state(cat_num, sub_name):

    kind = get_subcategory_kind(cat_num, sub_name)

    if kind == "manual_length":
        return {
            "expanded": False,
            "product_type": None,
            "manual_value": None,
        }
    
    if kind == "sprinkler_group":
        return {
            "expanded": False,
            "heads_status": "N/A",
            "heads_table": empty_sprinkler_heads_table(),
            "pipework_mode": "Default Formula",
            "pipework_product_type": None,
            "pipework_manual_value": None,
            "group": init_group_state(SPRINKLER_GROUP_CHILD_SPECS),
        }
    
    if kind == "component_group":
        return init_group_state(GROUP_DEFINITIONS[(cat_num, sub_name)])
    
    if kind == "extinguisher":
        return {
            "status": "N/A",
            "expanded": False,
            "hazard_class": "Ordinary",
            "fire_class_a": True,
            "fire_class_b": False,
            "has_fixed_suppression": False,
            "electronics_present": False,
            "product_type": None,
            "determination_type": "Quantity",
            "override_value": None,
            "bracket_included": False,
            "bracket_mode": "Equal to Extinguishers",
            "bracket_quantity_override": None,
            "bracket_product_type": None,
            "cabinet_included": False,
            "cabinet_mode": "Equal to Extinguishers",
            "cabinet_quantity_override": None,
            "cabinet_product_type": None,
        }
    
    if kind == "sampling_group":
        return {
            "expanded": False,
            "pipework_product_type": None,
            "pipework_quantity": None,
            "points_product_type": None,
            "points_quantity": None,
        }

    # "simple" and "not_implemented" share the same state shape
    return {
        "status": "N/A",
        "expanded": False,
        "table": empty_display_row(),
    }


def fresh_categories():
    return {
        cat_num: {
            "subcategories": {
                sub_name: blank_subcategory_state(cat_num, sub_name)
                for sub_name in CATEGORY_SUBCATEGORIES[cat_num]
            }
        }
        for cat_num in CATEGORY_NAMES
    }


def get_subcategory_color_status(cat_num, sub_name, sub_state):
    kind = get_subcategory_kind(cat_num, sub_name)
    if kind in ("sprinkler_pipework", "manual_length"):
        return "PBD" if sub_state.get("product_type") else "N/A"
    if kind == "extinguisher":
        return sub_state.get("status", "N/A")
    if kind == "sprinkler_group":
        return "PBD" if sub_state.get("heads_status") in ("DTS", "PBD") else "N/A"
    if kind == "component_group":
        has_any_data = any(
            comp.get("value") or comp.get("included")
            for comp in sub_state.get("components", {}).values()
        )
        return "PBD" if has_any_data else "N/A"
    if kind in ("not_implemented", "unavailable"):
        return "N/A"
    return sub_state.get("status", "N/A")


def load_categories_from_design_rows(design_rows):
    """
    Reconstructs the test_categories structure from a previously
    saved version's design data, so an existing version can be
    reopened for editing exactly as it was left.
    """

    categories = fresh_categories()

    rows_by_subcategory = {}
    for row in design_rows:
        key = (row.get("Category"), row.get("Subcategory"))
        rows_by_subcategory.setdefault(key, []).append(row)

    for cat_num, cat_name in CATEGORY_NAMES.items():
        for sub_name in CATEGORY_SUBCATEGORIES[cat_num]:

            matching_rows = rows_by_subcategory.get((cat_name, sub_name), [])
            if not matching_rows:
                continue

            kind = get_subcategory_kind(cat_num, sub_name)

            if kind == "sprinkler_heads":

                status = matching_rows[0].get("Status", "N/A")
                if status == "N/A" or not matching_rows[0].get("Determination Type"):
                    table = empty_sprinkler_heads_table()
                else:
                    table = pd.DataFrame(
                        [
                            {
                                "Product Type": r.get("Product Type"),
                                "Determination Type": r.get("Determination Type"),
                                "Value": r.get("Value"),
                                "Hazard Rating": r.get("Hazard Rating"),
                            }
                            for r in matching_rows
                        ]
                    )

                categories[cat_num]["subcategories"][sub_name] = {
                    "status": status,
                    "expanded": False,
                    "table": table,
                }

            elif kind == "sprinkler_pipework":

                r = matching_rows[0]
                categories[cat_num]["subcategories"][sub_name] = {
                    "expanded": False,
                    "mode": r.get("Status") or "Default Formula",
                    "product_type": r.get("Product Type"),
                    "manual_value": r.get("Value"),
                }

            else:

                r = matching_rows[0]
                status = r.get("Status", "N/A")

                if status == "N/A" or not r.get("Determination Type"):
                    table = empty_display_row()
                else:
                    table = pd.DataFrame(
                        [{
                            "Determination Type": r.get("Determination Type"),
                            "Value": r.get("Value"),
                            "Product Type": r.get("Product Type"),
                        }]
                    )

                categories[cat_num]["subcategories"][sub_name] = {
                    "status": status,
                    "expanded": False,
                    "table": table,
                }

    return categories


def version_summary_label(v):
    first_line = (v["version_notes"] or "").strip().splitlines()
    note_preview = first_line[0][:60] if first_line else "No notes"
    status_tag = " (Draft — incomplete)" if v["status"] == "draft" else ""
    return f"Version {v['version']} — {note_preview}{status_tag}"


# ==========================================================
# Session State
# ==========================================================

if "test_step" not in st.session_state:
    st.session_state.test_step = 1

if "test_project_info" not in st.session_state:
    st.session_state.test_project_info = {}

if "test_categories" not in st.session_state:
    st.session_state.test_categories = fresh_categories()

if "test_selected_category" not in st.session_state:
    st.session_state.test_selected_category = 1

if "test_results_df" not in st.session_state:
    st.session_state.test_results_df = pd.DataFrame()

if "test_summary" not in st.session_state:
    st.session_state.test_summary = {}

if "test_dirty" not in st.session_state:
    st.session_state.test_dirty = False

if "test_last_saved_snapshot" not in st.session_state:
    st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)

if "test_show_unsaved_dialog" not in st.session_state:
    st.session_state.test_show_unsaved_dialog = False

if "test_editing_mode" not in st.session_state:
    st.session_state.test_editing_mode = None

if "test_editing_version_number" not in st.session_state:
    st.session_state.test_editing_version_number = None

if "test_is_new_unsaved_draft" not in st.session_state:
    st.session_state.test_is_new_unsaved_draft = False

carbon_db = load_carbon_database()

# ==========================================================
# STEP 1: Project Information
# ==========================================================

if st.session_state.test_step == 1:

    st.markdown(
        """
    Set up the proposed design assessment by entering building details below,
    then proceed to select and configure fire safety systems.
    """
    )

    st.divider()

    st.subheader("Project Information")

    project_mode = st.radio(
        "Project Type",
        ["New Project", "Existing Project"],
        horizontal=True,
        key="test_project_mode",
    )

    show_next_button = True
    selected_existing_version = None

    if project_mode == "New Project":

        col1, col2 = st.columns(2)

        with col1:
            project_name = st.text_input(
                "Project Name",
                placeholder="Example: ABC Office Fitout",
                key="test_project_name_new",
            )

        with col2:
            building_area = st.number_input(
                "Building Area (m²)",
                min_value=0.0,
                step=1.0,
                key="test_building_area_new",
            )

        assessment_notes = st.text_area(
            "Assessment Notes",
            placeholder="Optional project notes...",
            key="test_assessment_notes_new",
        )

    else:

        existing_projects = get_project_names()

        if not existing_projects:
            st.info("No existing projects found yet. Create a New Project first.")
            st.stop()

        col1, col2 = st.columns(2)

        with col1:
            project_name = st.selectbox(
                "Select Project",
                existing_projects,
                key="test_project_name_existing",
            )

        project_meta = get_project_meta(project_name)

        with col2:
            building_area = st.number_input(
                "Building Area (m²)",
                min_value=0.0,
                step=1.0,
                value=float(project_meta["area"]) if project_meta and project_meta["area"] else 0.0,
                key="test_building_area_existing",
            )

        assessment_notes = st.text_area(
            "Assessment Notes",
            value=project_meta["notes"] if project_meta else "",
            key="test_assessment_notes_existing",
        )

        versions = get_project_versions(project_name)

        version_options = ["+ New Version"] + [version_summary_label(v) for v in versions]

        selected_version_label = st.selectbox(
            "Select Version",
            version_options,
            key="test_version_choice",
        )

        if selected_version_label != "+ New Version":

            selected_index = version_options.index(selected_version_label) - 1
            selected_existing_version = versions[selected_index]

            show_next_button = False

            st.divider()

            st.info("🔒 This version is locked. Click **Edit Version** below to make changes.")

            summary = selected_existing_version["summary"]

            if summary:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("A1-A3", f"{summary.get('A1-A3', 0):,.2f} kgCO₂e")
                col2.metric("A4", f"{summary.get('A4', 0):,.2f} kgCO₂e")
                col3.metric("A5", f"{summary.get('A5', 0):,.2f} kgCO₂e")
                col4.metric("Total", f"{summary.get('Total', 0):,.2f} kgCO₂e")

            if selected_existing_version["version_notes"]:
                st.markdown("**Version Notes**")
                st.text(selected_existing_version["version_notes"])

            design_rows = selected_existing_version["design"]

            if design_rows:
                st.markdown("**Design Composition**")
                st.dataframe(
                    pd.DataFrame(design_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            edit_version_clicked = st.button(
                "✏️ Edit Version",
                use_container_width=True,
            )

            if edit_version_clicked:

                building_classes = get_building_classes()

                st.session_state.test_project_info = {
                    "project_mode": project_mode,
                    "project_name": project_name,
                    "building_area": building_area,
                    "assessment_notes": assessment_notes,
                    "building_class": building_classes[0] if building_classes else "",
                    "version_notes": selected_existing_version["version_notes"] or "",
                    "building_storeys": None,
                    "building_floor_to_floor_height": None,
                    "building_risers": None,
                    "building_exits_per_storey": None,
                }

                st.session_state.test_categories = load_categories_from_design_rows(design_rows)
                st.session_state.test_results_df = pd.DataFrame(selected_existing_version["results"])
                st.session_state.test_summary = selected_existing_version["summary"]

                st.session_state.test_editing_mode = "edit"
                st.session_state.test_editing_version_number = selected_existing_version["version"]
                st.session_state.test_is_new_unsaved_draft = False

                st.session_state.test_dirty = False
                st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)

                st.session_state.test_step = 2
                st.rerun()

    if show_next_button:

        building_classes = get_building_classes()

        building_class = st.selectbox(
            "Building Class (NCC)",
            building_classes if building_classes else ["No building classes found"],
            key="test_building_class",
        )

        with st.expander("Additional Building Inputs (used by some systems)"):

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                building_storeys = st.number_input(
                    "Number of Storeys",
                    min_value=0,
                    step=1,
                    key="test_building_storeys",
                )

            with col2:
                building_floor_to_floor_height = st.number_input(
                    "Floor to Floor Height (m)",
                    min_value=0.0,
                    step=0.1,
                    key="test_building_ftf_height",
                )

            with col3:
                building_risers = st.number_input(
                    "Number of Risers",
                    min_value=0,
                    step=1,
                    key="test_building_risers",
                )

            with col4:
                building_exits_per_storey = st.number_input(
                    "Number of Exits per Storey",
                    min_value=0,
                    step=1,
                    key="test_building_exits_per_storey",
                )

        version_notes = st.text_area(
            "Version Notes",
            placeholder="Describe what changed in this design iteration...",
            key=f"test_version_notes_{project_mode}_{project_name}",
        )

        st.divider()

        next_step = st.button(
            "Next: Configure Fire Safety Systems →",
            use_container_width=True,
        )

        if next_step:

            if not project_name:
                st.error("Please enter or select a project name before continuing.")
            else:
                reserved_version = reserve_next_version(project_name, building_area, assessment_notes)

                st.session_state.test_project_info = {
                    "project_mode": project_mode,
                    "project_name": project_name,
                    "building_area": building_area,
                    "assessment_notes": assessment_notes,
                    "building_class": building_class,
                    "version_notes": version_notes,
                    "building_storeys": building_storeys,
                    "building_floor_to_floor_height": building_floor_to_floor_height,
                    "building_risers": building_risers,
                    "building_exits_per_storey": building_exits_per_storey,
                }

                st.session_state.test_categories = fresh_categories()
                st.session_state.test_results_df = pd.DataFrame()
                st.session_state.test_summary = {}

                st.session_state.test_editing_mode = "new"
                st.session_state.test_editing_version_number = reserved_version
                st.session_state.test_is_new_unsaved_draft = True

                st.session_state.test_step = 2
                st.session_state.test_dirty = False
                st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)
                st.rerun()

    render_footer()

# ==========================================================
# STEP 2: Fire Safety System Configuration
# ==========================================================

else:

    info = st.session_state.test_project_info

    # ==========================================================
    # Calculation Logic
    # ==========================================================

    def run_calculation():

        apparatus_output_df = carbon_db["apparatus_output"]
        building_area_m2 = info.get("building_area", 0)

        results = []
        warnings = []

        total_sprinkler_head_quantity = 0.0
        effective_linear_spacing_m = None

        for cat_num, sub_names in CATEGORY_SUBCATEGORIES.items():
            for sub_name in sub_names:

                kind = get_subcategory_kind(cat_num, sub_name)
                sub_state = st.session_state.test_categories[cat_num]["subcategories"][sub_name]
                apparatus_name = get_apparatus_name(cat_num, sub_name)

                # ------------------------------------------------
                # "simple" kind
                # ------------------------------------------------
                if kind == "simple":

                    if sub_state["status"] == "N/A":
                        continue

                    table = sub_state["table"]
                    if table.empty:
                        continue

                    row = table.iloc[0]
                    determination_label = row.get("Determination Type")
                    input_value = row.get("Value")
                    product_type_name = row.get("Product Type")

                    if not apparatus_name:
                        warnings.append(f"{sub_name}: no Carbon Database mapping configured yet.")
                        continue

                    if input_value is None or pd.isna(input_value) or input_value == 0:
                        warnings.append(f"{sub_name}: Value must be greater than 0 to be included.")
                        continue

                    determination_type_key = DETERMINATION_TYPE_LABELS.get(determination_label)

                    equivalent_quantity = calculate_equivalent_quantity(
                        determination_type_key, input_value, building_area_m2
                    )

                    if equivalent_quantity is None:
                        warnings.append(f"{sub_name}: Building Area must be set to use Grid Spacing.")
                        continue

                    if not isinstance(product_type_name, str) or not product_type_name.strip():
                        warnings.append(
                            f"{sub_name}: no Product Type selected - not included in the calculation."
                        )
                        continue

                    carbon_factors_row = find_product_carbon_factors_row(
                        apparatus_output_df, apparatus_name, product_type_name
                    )

                    if carbon_factors_row is None:
                        warnings.append(
                            f"{sub_name}: Product Type '{product_type_name}' not found for '{apparatus_name}'."
                        )
                        continue

                    carbon_result = calculate_component_carbon(equivalent_quantity, carbon_factors_row)

                    results.append({
                        "Apparatus": sub_name,
                        "Product Type": product_type_name,
                        "Quantity": equivalent_quantity,
                        "A1-A3": carbon_result["A1-A3"],
                        "A4": carbon_result["A4"],
                        "A5": carbon_result["A5"],
                        "Total": carbon_result["Total"],
                    })

                # ------------------------------------------------
                # Sprinkler Heads (multi-row)
                # ------------------------------------------------
                elif kind == "sprinkler_heads":

                    if sub_state["status"] == "N/A":
                        continue

                    table = sub_state["table"]
                    if table.empty:
                        continue

                    for _, row in table.iterrows():

                        determination_label = row.get("Determination Type")
                        input_value = row.get("Value")
                        product_type_name = row.get("Product Type")

                        if input_value is None or pd.isna(input_value) or input_value == 0:
                            warnings.append(f"{sub_name}: a row is missing a Value - skipped.")
                            continue

                        det_key = SPRINKLER_DETERMINATION_LABELS.get(determination_label)

                        if det_key == "quantity":
                            quantity = input_value
                        else:  # linear_spacing
                            quantity = calculate_quantity(
                                "sprinkler", "sprinkler_head", "quantity_formula",
                                {
                                    "protected_area": building_area_m2,
                                    "spacing_area": (input_value ** 2) if input_value else None,
                                },
                            )

                        if quantity is None:
                            warnings.append(
                                f"{sub_name}: Building Area must be set to use Linear Spacing."
                            )
                            continue

                        if not isinstance(product_type_name, str) or not product_type_name.strip():
                            warnings.append(
                                f"{sub_name}: a row has no Product Type selected - not included."
                            )
                            continue

                        carbon_factors_row = find_product_carbon_factors_row(
                            apparatus_output_df, "Sprinkler Head", product_type_name
                        )

                        if carbon_factors_row is None:
                            warnings.append(
                                f"{sub_name}: Product Type '{product_type_name}' not found for 'Sprinkler Head'."
                            )
                            continue

                        carbon_result = calculate_component_carbon(quantity, carbon_factors_row)

                        results.append({
                            "Apparatus": sub_name,
                            "Product Type": product_type_name,
                            "Quantity": quantity,
                            "A1-A3": carbon_result["A1-A3"],
                            "A4": carbon_result["A4"],
                            "A5": carbon_result["A5"],
                            "Total": carbon_result["Total"],
                        })

                        total_sprinkler_head_quantity += quantity

                        if det_key == "linear_spacing" and effective_linear_spacing_m is None:
                            effective_linear_spacing_m = input_value

                # ------------------------------------------------
                # Sprinkler Pipework
                # ------------------------------------------------
                elif kind == "sprinkler_pipework":

                    mode = sub_state.get("mode")
                    product_type_name = sub_state.get("product_type")

                    if not isinstance(product_type_name, str) or not product_type_name.strip():
                        warnings.append(f"{sub_name}: no Product Type selected - not included.")
                        continue

                    if mode == "Manual Override":

                        length_m = sub_state.get("manual_value")

                        if not length_m or length_m <= 0:
                            warnings.append(f"{sub_name}: enter a manual length greater than 0.")
                            continue

                    else:  # Default Formula

                        variables = {
                            "risers": info.get("building_risers") or get_parameter("sprinkler", "pipework", "default_risers"),
                            "storeys": info.get("building_storeys"),
                            "floor_to_floor_height": info.get("building_floor_to_floor_height"),
                            "protected_area": building_area_m2,
                            "spacing_area": (effective_linear_spacing_m ** 2) if effective_linear_spacing_m else None,
                        }

                        vertical = calculate_quantity("sprinkler", "pipework", "vertical_riser_formula", variables)
                        horizontal = calculate_quantity("sprinkler", "pipework", "horizontal_pipe_formula", variables)

                        if vertical is None or horizontal is None:
                            warnings.append(
                                f"{sub_name}: insufficient inputs to compute the default formula "
                                f"(check Risers, Storeys, Floor-to-Floor Height, and Sprinkler Heads)."
                            )
                            continue

                        length_m = vertical + horizontal

                    carbon_factors_row = find_product_carbon_factors_row(
                        apparatus_output_df, "Sprinkler Pipework", product_type_name
                    )

                    if carbon_factors_row is None:
                        warnings.append(
                            f"{sub_name}: Product Type '{product_type_name}' not found for 'Sprinkler Pipework'."
                        )
                        continue

                    carbon_result = calculate_component_carbon(length_m, carbon_factors_row)

                    results.append({
                        "Apparatus": sub_name,
                        "Product Type": product_type_name,
                        "Quantity": length_m,
                        "A1-A3": carbon_result["A1-A3"],
                        "A4": carbon_result["A4"],
                        "A5": carbon_result["A5"],
                        "Total": carbon_result["Total"],
                    })

                # ------------------------------------------------
                # Manual Length (Hose Reel Pipework)
                # ------------------------------------------------
                elif kind == "manual_length":

                    product_type_name = sub_state.get("product_type")
                    length_m = sub_state.get("manual_value")

                    if not isinstance(product_type_name, str) or not product_type_name.strip():
                        warnings.append(f"{sub_name}: no Product Type selected - not included.")
                        continue

                    if not length_m or length_m <= 0:
                        warnings.append(f"{sub_name}: enter a length greater than 0.")
                        continue

                    carbon_factors_row = find_product_carbon_factors_row(
                        apparatus_output_df, apparatus_name, product_type_name
                    )

                    if carbon_factors_row is None:
                        warnings.append(
                            f"{sub_name}: Product Type '{product_type_name}' not found for '{apparatus_name}'."
                        )
                        continue

                    carbon_result = calculate_component_carbon(length_m, carbon_factors_row)

                    results.append({
                        "Apparatus": sub_name,
                        "Product Type": product_type_name,
                        "Quantity": length_m,
                        "A1-A3": carbon_result["A1-A3"],
                        "A4": carbon_result["A4"],
                        "A5": carbon_result["A5"],
                        "Total": carbon_result["Total"],
                    })

                elif kind == "sampling_group":

                    for child_label, product_key, qty_key, apparatus_key in [
                        ("Sampling Pipework", "pipework_product_type", "pipework_quantity", "Sampling Pipework"),
                        ("Sampling Points", "points_product_type", "points_quantity", "Sampling Points"),
                    ]:

                        product_type_name = sub_state.get(product_key)
                        quantity = sub_state.get(qty_key)

                        if not quantity or quantity <= 0:
                            continue  # not an error - simply not included if left blank

                        if not isinstance(product_type_name, str) or not product_type_name.strip():
                            warnings.append(f"{child_label}: no Product Type selected - not included.")
                            continue

                        child_apparatus_name = get_apparatus_name(1, apparatus_key)

                        carbon_factors_row = find_product_carbon_factors_row(
                            apparatus_output_df, child_apparatus_name, product_type_name
                        )

                        if carbon_factors_row is None:
                            warnings.append(
                                f"{child_label}: Product Type '{product_type_name}' not found for '{child_apparatus_name}'."
                            )
                            continue

                        carbon_result = calculate_component_carbon(quantity, carbon_factors_row)

                        results.append({
                            "Apparatus": child_label,
                            "Product Type": product_type_name,
                            "Quantity": quantity,
                            "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                            "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                        })

                elif kind == "sprinkler_group":

                    local_total_heads_quantity = 0.0
                    local_effective_linear_spacing_m = None

                    if sub_state["heads_status"] != "N/A" and not sub_state["heads_table"].empty:

                        for _, row in sub_state["heads_table"].iterrows():

                            determination_label = row.get("Determination Type")
                            input_value = row.get("Value")
                            product_type_name = row.get("Product Type")

                            if input_value is None or pd.isna(input_value) or input_value == 0:
                                warnings.append(f"{sub_name}: a Sprinkler Head row is missing a Value - skipped.")
                                continue

                            det_key = SPRINKLER_DETERMINATION_LABELS.get(determination_label)

                            if det_key == "quantity":
                                quantity = input_value
                            else:
                                quantity = calculate_quantity(
                                    "sprinkler", "sprinkler_head", "quantity_formula",
                                    {"protected_area": building_area_m2, "spacing_area": (input_value ** 2) if input_value else None},
                                )

                            if quantity is None:
                                warnings.append(f"{sub_name}: Building Area must be set to use Linear Spacing.")
                                continue

                            if not isinstance(product_type_name, str) or not product_type_name.strip():
                                warnings.append(f"{sub_name}: a Sprinkler Head row has no Product Type selected - not included.")
                                continue

                            carbon_factors_row = find_product_carbon_factors_row(
                                apparatus_output_df, "Sprinkler Head", product_type_name
                            )

                            if carbon_factors_row is None:
                                warnings.append(f"{sub_name}: Product Type '{product_type_name}' not found for 'Sprinkler Head'.")
                                continue

                            carbon_result = calculate_component_carbon(quantity, carbon_factors_row)

                            results.append({
                                "Apparatus": "Sprinkler Heads",
                                "Product Type": product_type_name,
                                "Quantity": quantity,
                                "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                            })

                            local_total_heads_quantity += quantity

                            if det_key == "linear_spacing" and local_effective_linear_spacing_m is None:
                                local_effective_linear_spacing_m = input_value

                    pipework_product_type_name = sub_state.get("pipework_product_type")

                    if isinstance(pipework_product_type_name, str) and pipework_product_type_name.strip():

                        length_m = None

                        if sub_state["pipework_mode"] == "Manual Override":

                            length_m = sub_state.get("pipework_manual_value")
                            if not length_m or length_m <= 0:
                                warnings.append(f"{sub_name}: enter a manual Sprinkler Pipework length greater than 0.")
                                length_m = None

                        else:

                            variables = {
                                "risers": info.get("building_risers") or get_parameter("sprinkler", "pipework", "default_risers"),
                                "storeys": info.get("building_storeys"),
                                "floor_to_floor_height": info.get("building_floor_to_floor_height"),
                                "protected_area": building_area_m2,
                                "spacing_area": (local_effective_linear_spacing_m ** 2) if local_effective_linear_spacing_m else None,
                            }
                            vertical = calculate_quantity("sprinkler", "pipework", "vertical_riser_formula", variables)
                            horizontal = calculate_quantity("sprinkler", "pipework", "horizontal_pipe_formula", variables)

                            if vertical is None or horizontal is None:
                                warnings.append(
                                    f"{sub_name}: insufficient inputs to compute the default Sprinkler Pipework formula "
                                    f"(check Risers, Storeys, Floor-to-Floor Height, and Sprinkler Heads)."
                                )
                            else:
                                length_m = vertical + horizontal

                        if length_m:

                            carbon_factors_row = find_product_carbon_factors_row(
                                apparatus_output_df, "Sprinkler Pipework", pipework_product_type_name
                            )

                            if carbon_factors_row is None:
                                warnings.append(f"{sub_name}: Product Type '{pipework_product_type_name}' not found for 'Sprinkler Pipework'.")
                            else:
                                carbon_result = calculate_component_carbon(length_m, carbon_factors_row)
                                results.append({
                                    "Apparatus": "Sprinkler Pipework",
                                    "Product Type": pipework_product_type_name,
                                    "Quantity": length_m,
                                    "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                    "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                                })

                    resolved_quantities = {"heads": local_total_heads_quantity if local_total_heads_quantity > 0 else None}

                    for spec in SPRINKLER_GROUP_CHILD_SPECS:
                        comp_state = sub_state["group"]["components"][spec["key"]]
                        parent_qty = resolved_quantities.get(spec.get("parent_key")) if spec["kind"] == KIND_LINKED_CHILD else None
                        result = calculate_component(
                            spec, comp_state, apparatus_output_df,
                            building_area_m2=building_area_m2, parent_quantity=parent_qty, warnings=warnings,
                        )
                        if result:
                            results.append(result)

                elif kind == "component_group":

                    specs = GROUP_DEFINITIONS[(cat_num, sub_name)]

                    group_results = calculate_component_group(
                        specs, sub_state, apparatus_output_df,
                        building_area_m2=building_area_m2, warnings=warnings,
                    )

                    results.extend(group_results)

                elif kind == "extinguisher":

                    if sub_state["status"] == "N/A":
                        continue

                    product_type_name = sub_state.get("product_type")

                    if not isinstance(product_type_name, str) or not product_type_name.strip():
                        warnings.append(f"{sub_name}: no Product Type selected for Extinguishers - not included.")
                        continue

                    extinguisher_quantity = None

                    if sub_state["status"] == "DTS":

                        candidate_quantities = []

                        if sub_state.get("fire_class_a"):
                            req_a = get_extinguisher_requirement(sub_state["hazard_class"], "A", sub_state["has_fixed_suppression"])
                            if req_a and req_a["max_area"]:
                                qty_a = calculate_quantity(
                                    "extinguisher", "portable_extinguisher", "quantity_formula",
                                    {"storeys": info.get("building_storeys"), "floor_area": building_area_m2, "max_area": req_a["max_area"]},
                                )
                                if qty_a is not None:
                                    candidate_quantities.append(qty_a)

                        if sub_state.get("fire_class_b"):
                            req_b = get_extinguisher_requirement(sub_state["hazard_class"], "B", sub_state["has_fixed_suppression"])
                            if req_b and req_b["max_area"]:
                                qty_b = calculate_quantity(
                                    "extinguisher", "portable_extinguisher", "quantity_formula",
                                    {"storeys": info.get("building_storeys"), "floor_area": building_area_m2, "max_area": req_b["max_area"]},
                                )
                                if qty_b is not None:
                                    candidate_quantities.append(qty_b)

                        if candidate_quantities:
                            extinguisher_quantity = max(candidate_quantities)  # conservative: more onerous class governs

                    else:  # PBD

                        det_key = EXTINGUISHER_DETERMINATION_LABELS.get(sub_state["determination_type"])
                        override_value = sub_state.get("override_value")

                        if not override_value or override_value <= 0:
                            warnings.append(f"{sub_name}: enter a Value greater than 0 for Extinguishers.")
                        elif det_key == "quantity":
                            extinguisher_quantity = override_value
                        elif det_key == "coverage_area":
                            extinguisher_quantity = calculate_quantity(
                                "extinguisher", "portable_extinguisher", "quantity_formula",
                                {"storeys": info.get("building_storeys"), "floor_area": building_area_m2, "max_area": override_value},
                            )
                            if extinguisher_quantity is None:
                                warnings.append(f"{sub_name}: Building Area and Storeys must be set to use Coverage Area.")

                    if extinguisher_quantity and extinguisher_quantity > 0:

                        carbon_factors_row = find_product_carbon_factors_row(
                            apparatus_output_df, apparatus_name, product_type_name
                        )

                        if carbon_factors_row is None:
                            warnings.append(f"Extinguishers: Product Type '{product_type_name}' not found for '{apparatus_name}'.")
                        else:
                            carbon_result = calculate_component_carbon(extinguisher_quantity, carbon_factors_row)
                            results.append({
                                "Apparatus": "Portable Extinguishers",
                                "Product Type": product_type_name,
                                "Quantity": extinguisher_quantity,
                                "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                            })
                    else:
                        warnings.append(
                            f"{sub_name}: insufficient inputs to calculate an extinguisher quantity."
                        )

                    # ---- Brackets ----

                    bracket_active = (sub_state["status"] == "DTS") or sub_state.get("bracket_included")

                    if bracket_active and extinguisher_quantity:

                        bracket_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Brackets"))
                        bracket_product = sub_state.get("bracket_product_type")

                        if sub_state["status"] == "DTS" or sub_state.get("bracket_mode") == "Equal to Extinguishers":
                            bracket_qty = extinguisher_quantity
                        else:
                            bracket_qty = sub_state.get("bracket_quantity_override")

                        if not bracket_product:
                            warnings.append("Brackets: no Product Type selected - not included.")
                        elif not bracket_qty or bracket_qty <= 0:
                            warnings.append("Brackets: quantity must be greater than 0 - not included.")
                        else:
                            carbon_factors_row = find_product_carbon_factors_row(
                                apparatus_output_df, bracket_apparatus, bracket_product
                            )
                            if carbon_factors_row is None:
                                warnings.append(f"Brackets: Product Type '{bracket_product}' not found for '{bracket_apparatus}'.")
                            else:
                                carbon_result = calculate_component_carbon(bracket_qty, carbon_factors_row)
                                results.append({
                                    "Apparatus": "Extinguisher Brackets",
                                    "Product Type": bracket_product,
                                    "Quantity": bracket_qty,
                                    "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                    "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                                })

                    # ---- Cabinets ----

                    cabinet_active = (sub_state["status"] == "DTS") or sub_state.get("cabinet_included")

                    if cabinet_active and extinguisher_quantity:

                        cabinet_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Cabinets"))
                        cabinet_product = sub_state.get("cabinet_product_type")

                        if sub_state["status"] == "DTS" or sub_state.get("cabinet_mode") == "Equal to Extinguishers":
                            cabinet_qty = extinguisher_quantity
                        else:
                            cabinet_qty = sub_state.get("cabinet_quantity_override")

                        if not cabinet_product:
                            warnings.append("Cabinets: no Product Type selected - not included.")
                        elif not cabinet_qty or cabinet_qty <= 0:
                            warnings.append("Cabinets: quantity must be greater than 0 - not included.")
                        else:
                            carbon_factors_row = find_product_carbon_factors_row(
                                apparatus_output_df, cabinet_apparatus, cabinet_product
                            )
                            if carbon_factors_row is None:
                                warnings.append(f"Cabinets: Product Type '{cabinet_product}' not found for '{cabinet_apparatus}'.")
                            else:
                                carbon_result = calculate_component_carbon(cabinet_qty, carbon_factors_row)
                                results.append({
                                    "Apparatus": "Extinguisher Cabinets",
                                    "Product Type": cabinet_product,
                                    "Quantity": cabinet_qty,
                                    "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                    "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                                })
                # ------------------------------------------------
                # "not_implemented" kind - skipped silently
                # ------------------------------------------------
                else:
                    continue

        for w in warnings:
            st.warning(w)

        results_df = pd.DataFrame(results)
        summary = summarise_results(results_df)

        st.session_state.test_results_df = results_df
        st.session_state.test_summary = summary

        return not results_df.empty


    def build_design_dataframe():

        rows = []

        for cat_num, cat_name in CATEGORY_NAMES.items():
            for sub_name in CATEGORY_SUBCATEGORIES[cat_num]:

                kind = get_subcategory_kind(cat_num, sub_name)
                sub_state = st.session_state.test_categories[cat_num]["subcategories"][sub_name]

                if kind == "sprinkler_heads":

                    status = sub_state["status"]
                    table = sub_state["table"]

                    if status == "N/A" or table.empty:
                        rows.append({
                            "Category": cat_name, "Subcategory": sub_name, "Status": status,
                            "Determination Type": None, "Value": None,
                            "Product Type": None, "Hazard Rating": None,
                        })
                    else:
                        for _, r in table.iterrows():
                            rows.append({
                                "Category": cat_name, "Subcategory": sub_name, "Status": status,
                                "Determination Type": r.get("Determination Type"),
                                "Value": r.get("Value"),
                                "Product Type": r.get("Product Type"),
                                "Hazard Rating": r.get("Hazard Rating"),
                            })

                elif kind == "sprinkler_pipework":

                    rows.append({
                        "Category": cat_name, "Subcategory": sub_name,
                        "Status": sub_state.get("mode"),
                        "Determination Type": sub_state.get("mode"),
                        "Value": sub_state.get("manual_value"),
                        "Product Type": sub_state.get("product_type"),
                        "Hazard Rating": None,
                    })

                elif kind == "manual_length":

                    rows.append({
                        "Category": cat_name, "Subcategory": sub_name,
                        "Status": "Manual",
                        "Determination Type": "Manual",
                        "Value": sub_state.get("manual_value"),
                        "Product Type": sub_state.get("product_type"),
                        "Hazard Rating": None,
                    })

                elif kind == "sampling_group":

                    rows.append({
                        "Category": cat_name, "Subcategory": "Sampling Pipework",
                        "Status": "Manual", "Determination Type": "Quantity",
                        "Value": sub_state.get("pipework_quantity"),
                        "Product Type": sub_state.get("pipework_product_type"),
                        "Hazard Rating": None,
                    })
                    rows.append({
                        "Category": cat_name, "Subcategory": "Sampling Points",
                        "Status": "Manual", "Determination Type": "Quantity",
                        "Value": sub_state.get("points_quantity"),
                        "Product Type": sub_state.get("points_product_type"),
                        "Hazard Rating": None,
                    })

                elif kind == "sprinkler_group":

                    if sub_state["heads_table"].empty:
                        rows.append({
                            "Category": cat_name, "Subcategory": "Sprinkler Heads",
                            "Status": sub_state.get("heads_status"),
                            "Determination Type": None, "Value": None,
                            "Product Type": None, "Hazard Rating": None,
                        })
                    else:
                        for _, r in sub_state["heads_table"].iterrows():
                            rows.append({
                                "Category": cat_name, "Subcategory": "Sprinkler Heads",
                                "Status": sub_state.get("heads_status"),
                                "Determination Type": r.get("Determination Type"),
                                "Value": r.get("Value"),
                                "Product Type": r.get("Product Type"),
                                "Hazard Rating": r.get("Hazard Rating"),
                            })

                    rows.append({
                        "Category": cat_name, "Subcategory": "Sprinkler Pipework",
                        "Status": sub_state.get("pipework_mode"),
                        "Determination Type": sub_state.get("pipework_mode"),
                        "Value": sub_state.get("pipework_manual_value"),
                        "Product Type": sub_state.get("pipework_product_type"),
                        "Hazard Rating": None,
                    })

                    rows.extend(component_group_design_rows(cat_name, SPRINKLER_GROUP_CHILD_SPECS, sub_state["group"]))

                elif kind == "component_group":

                    specs = GROUP_DEFINITIONS[(cat_num, sub_name)]
                    rows.extend(component_group_design_rows(cat_name, specs, sub_state))

                elif kind == "extinguisher":

                    rows.append({
                        "Category": cat_name, "Subcategory": sub_name,
                        "Status": sub_state.get("status", "N/A"),
                        "Determination Type": f"Hazard: {sub_state.get('hazard_class')}, "
                                               f"Class A: {sub_state.get('fire_class_a')}, "
                                               f"Class B: {sub_state.get('fire_class_b')}, "
                                               f"Suppression: {sub_state.get('has_fixed_suppression')}, "
                                               f"Extinguisher determination: {sub_state.get('determination_type')}",
                        "Value": sub_state.get("override_value"),
                        "Product Type": sub_state.get("product_type"),
                        "Hazard Rating": sub_state.get("hazard_class"),
                    })
                    if sub_state.get("bracket_included") or sub_state.get("status") == "DTS":
                        rows.append({
                            "Category": cat_name, "Subcategory": "Extinguisher Brackets",
                            "Status": sub_state.get("bracket_mode"),
                            "Determination Type": sub_state.get("bracket_mode"),
                            "Value": sub_state.get("bracket_quantity_override"),
                            "Product Type": sub_state.get("bracket_product_type"),
                            "Hazard Rating": None,
                        })
                    if sub_state.get("cabinet_included") or sub_state.get("status") == "DTS":
                        rows.append({
                            "Category": cat_name, "Subcategory": "Extinguisher Cabinets",
                            "Status": sub_state.get("cabinet_mode"),
                            "Determination Type": sub_state.get("cabinet_mode"),
                            "Value": sub_state.get("cabinet_quantity_override"),
                            "Product Type": sub_state.get("cabinet_product_type"),
                            "Hazard Rating": None,
                        })

                else:

                    status = sub_state.get("status", "N/A")
                    table = sub_state.get("table", empty_display_row())

                    if status == "N/A" or table.empty:
                        rows.append({
                            "Category": cat_name, "Subcategory": sub_name, "Status": status,
                            "Determination Type": None, "Value": None,
                            "Product Type": None, "Hazard Rating": None,
                        })
                    else:
                        r = table.iloc[0]
                        rows.append({
                            "Category": cat_name, "Subcategory": sub_name, "Status": status,
                            "Determination Type": r.get("Determination Type"),
                            "Value": r.get("Value"),
                            "Product Type": r.get("Product Type"),
                            "Hazard Rating": None,
                        })

        return pd.DataFrame(rows)


    def perform_save():

        project_name = info.get("project_name")
        version_number = st.session_state.test_editing_version_number

        run_calculation()

        if st.session_state.test_editing_mode == "edit":
            update_existing_version(
                project_name=project_name, version_number=version_number,
                area=info.get("building_area"), notes=info.get("assessment_notes"),
                version_notes=info.get("version_notes"),
                design_df=build_design_dataframe(),
                results_df=st.session_state.test_results_df,
                summary=st.session_state.test_summary,
            )
        else:
            finalize_version(
                project_name=project_name, version_number=version_number,
                area=info.get("building_area"), notes=info.get("assessment_notes"),
                version_notes=info.get("version_notes"),
                design_df=build_design_dataframe(),
                results_df=st.session_state.test_results_df,
                summary=st.session_state.test_summary,
            )
            st.session_state.test_is_new_unsaved_draft = False

        st.session_state.test_dirty = False
        st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)

        return version_number


    def discard_changes():
        st.session_state.test_categories = copy.deepcopy(st.session_state.test_last_saved_snapshot)
        st.session_state.test_dirty = False

        if st.session_state.test_editing_mode == "new" and st.session_state.test_is_new_unsaved_draft:
            delete_version(info["project_name"], st.session_state.test_editing_version_number)


    # ==========================================================
    # Unsaved Changes Dialog
    # ==========================================================

    @st.dialog("Unsaved Changes")
    def unsaved_changes_dialog():

        st.write("You have unsaved changes to this design. Save them before leaving, or discard them?")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("💾 Save", use_container_width=True):
                if not info.get("project_name"):
                    st.error("Please enter or select a project name before saving.")
                else:
                    perform_save()
                    st.session_state.test_show_unsaved_dialog = False
                    st.session_state.test_step = 1
                    st.rerun()

        with col2:
            if st.button("🗑️ Discard", use_container_width=True):
                discard_changes()
                st.session_state.test_show_unsaved_dialog = False
                st.session_state.test_step = 1
                st.rerun()

        with col3:
            if st.button("Cancel", use_container_width=True):
                st.session_state.test_show_unsaved_dialog = False
                st.rerun()


    if st.session_state.test_show_unsaved_dialog:
        unsaved_changes_dialog()

    # ==========================================================
    # Header / Back Button
    # ==========================================================

    editing_tag = " (editing)" if st.session_state.test_editing_mode == "edit" else ""

    st.caption(
        f"**{info['project_name']}** · Version {st.session_state.test_editing_version_number}{editing_tag} · "
        f"{info['building_area']:,.0f} m² · {info['building_class']}"
    )

    applicability = get_building_class_applicability(info.get("building_class"))

    if applicability:
        with st.expander("ℹ️ NCC Building Class Applicability"):
            for system_name, requirement in applicability.items():
                st.caption(f"**{system_name}**: {requirement}")

    back = st.button("← Back to Project Information")

    if back:
        if st.session_state.test_dirty:
            st.session_state.test_show_unsaved_dialog = True
            st.rerun()
        else:
            if st.session_state.test_editing_mode == "new" and st.session_state.test_is_new_unsaved_draft:
                delete_version(info["project_name"], st.session_state.test_editing_version_number)
            st.session_state.test_step = 1
            st.rerun()

    st.divider()

    nav_col, body_col = st.columns([1, 3])

    # ------------------------------------------------------
    # Left: Category Navigation
    # ------------------------------------------------------

    def get_category_status_word(cat_num):
        subs = st.session_state.test_categories[cat_num]["subcategories"]
        if not subs:
            return "na"
        statuses = [
            get_subcategory_color_status(cat_num, sub_name, sub_state)
            for sub_name, sub_state in subs.items()
        ]
        if "PBD" in statuses:
            return "pbd"
        if "DTS" in statuses:
            return "dts"
        return "na"

    with nav_col:

        st.markdown("**Fire Safety Systems**")

        for i in range(1, 11):

            status_word = get_category_status_word(i)

            label = f"{i}. {CATEGORY_NAMES[i]}"
            if i == st.session_state.test_selected_category:
                label = f"▶ {label}"

            with st.container(key=f"cat_nav_{status_word}_{i}"):
                clicked = st.button(label, key=f"cat_nav_button_{i}", use_container_width=True)

            if clicked:
                st.session_state.test_selected_category = i
                st.rerun()

    # ------------------------------------------------------
    # Right: Category Detail Body
    # ------------------------------------------------------

    with body_col:

        selected = st.session_state.test_selected_category
        subcats = CATEGORY_SUBCATEGORIES[selected]

        st.markdown(f"### {CATEGORY_NAMES[selected]}")

        for sub_name in subcats:

            kind = get_subcategory_kind(selected, sub_name)
            sub_state = st.session_state.test_categories[selected]["subcategories"][sub_name]
            apparatus_name = get_apparatus_name(selected, sub_name)

            st.divider()

            # ================================================
            # not_implemented kind
            # ================================================
            if kind == "not_implemented":

                st.markdown(f"**{sub_name}**")
                st.info(
                    "This system's calculation logic has been specified but isn't wired into "
                    "the UI yet - let me know when you'd like this one built."
                )
                continue

            if kind == "unavailable":

                st.markdown(f"**{sub_name}**")
                st.info("This is not available.")
                continue

            # ================================================
            # sprinkler_pipework kind (no N/A/DTS/PBD toggle)
            # ================================================
            if kind == "sprinkler_pipework":

                arrow_col, name_col = st.columns([0.5, 4])

                with arrow_col:
                    arrow_label = "▼" if sub_state["expanded"] else "▶"
                    toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")

                with name_col:
                    st.markdown(f"**{sub_name}**")

                if toggle_expand:
                    sub_state["expanded"] = not sub_state["expanded"]
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()

                if sub_state["expanded"]:

                    product_options = get_available_product_types(
                        carbon_db.get("apparatus_output"), "Sprinkler Pipework"
                    )

                    mode_col, product_col = st.columns(2)

                    with mode_col:
                        new_mode = st.radio(
                            "Mode",
                            PIPEWORK_MODE_OPTIONS,
                            index=PIPEWORK_MODE_OPTIONS.index(sub_state.get("mode", "Default Formula")),
                            horizontal=True,
                            key=f"pipework_mode_{selected}_{sub_name}",
                        )

                    with product_col:
                        new_product = st.selectbox(
                            "Product Type",
                            ["(none selected)"] + product_options,
                            index=(
                                (["(none selected)"] + product_options).index(sub_state.get("product_type"))
                                if sub_state.get("product_type") in product_options else 0
                            ),
                            key=f"pipework_product_{selected}_{sub_name}",
                        )

                    if new_mode != sub_state.get("mode"):
                        sub_state["mode"] = new_mode
                        st.session_state.test_dirty = True

                    resolved_product = None if new_product == "(none selected)" else new_product
                    if resolved_product != sub_state.get("product_type"):
                        sub_state["product_type"] = resolved_product
                        st.session_state.test_dirty = True

                    if sub_state["mode"] == "Manual Override":

                        new_value = st.number_input(
                            "Pipework Length (m)",
                            min_value=0.0,
                            step=1.0,
                            value=float(sub_state.get("manual_value") or 0.0),
                            key=f"pipework_value_{selected}_{sub_name}",
                        )
                        if new_value != sub_state.get("manual_value"):
                            sub_state["manual_value"] = new_value
                            st.session_state.test_dirty = True

                    else:

                        st.number_input(
                            "Pipework Length (m) — calculated automatically",
                            value=0.0,
                            disabled=True,
                            key=f"pipework_value_disabled_{selected}_{sub_name}",
                        )
                        st.caption(
                            "Formula: Risers × Storeys × Floor-to-Floor Height + "
                            "Sprinkler Number × Floor Area / √(Linear Spacing). "
                            "Requires Risers, Storeys, and Floor-to-Floor Height to be set "
                            "on the Project Information page, plus at least one Sprinkler Head "
                            "row configured."
                        )
                        st.caption(
                            "⚠️ This default formula is an early-stage geometric approximation, "
                            "not a cited AS clause. Verify before relying on it for design."
                        )

                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                continue
            if kind == "manual_length":

                arrow_col, name_col = st.columns([0.5, 4])

                with arrow_col:
                    arrow_label = "▼" if sub_state["expanded"] else "▶"
                    toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")

                with name_col:
                    st.markdown(f"**{sub_name}**")

                if toggle_expand:
                    sub_state["expanded"] = not sub_state["expanded"]
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()

                if sub_state["expanded"]:

                    product_options = get_available_product_types(
                        carbon_db.get("apparatus_output"), apparatus_name
                    )

                    new_product = st.selectbox(
                        "Product Type",
                        ["(none selected)"] + product_options,
                        index=(
                            (["(none selected)"] + product_options).index(sub_state.get("product_type"))
                            if sub_state.get("product_type") in product_options else 0
                        ),
                        key=f"manual_product_{selected}_{sub_name}",
                    )

                    new_value = st.number_input(
                        "Length (m)",
                        min_value=0.0,
                        step=1.0,
                        value=float(sub_state.get("manual_value") or 0.0),
                        key=f"manual_value_{selected}_{sub_name}",
                    )

                    resolved_product = None if new_product == "(none selected)" else new_product

                    if resolved_product != sub_state.get("product_type") or new_value != sub_state.get("manual_value"):
                        sub_state["product_type"] = resolved_product
                        sub_state["manual_value"] = new_value
                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                        st.session_state.test_dirty = True

                continue
            if kind == "sampling_group":

                arrow_col, name_col = st.columns([0.5, 4])

                with arrow_col:
                    arrow_label = "▼" if sub_state["expanded"] else "▶"
                    toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")

                with name_col:
                    st.markdown(f"**{sub_name}**")

                if toggle_expand:
                    sub_state["expanded"] = not sub_state["expanded"]
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()

                if sub_state["expanded"]:

                    pipework_apparatus = get_apparatus_name(1, "Sampling Pipework")
                    points_apparatus = get_apparatus_name(1, "Sampling Points")

                    st.markdown("##### Sampling Pipework")

                    pipework_products = get_available_product_types(carbon_db.get("apparatus_output"), pipework_apparatus)

                    new_pipework_product = st.selectbox(
                        "Product Type", ["(none selected)"] + pipework_products,
                        index=(
                            (["(none selected)"] + pipework_products).index(sub_state.get("pipework_product_type"))
                            if sub_state.get("pipework_product_type") in pipework_products else 0
                        ),
                        key=f"sampling_pipework_product_{selected}_{sub_name}",
                    )
                    new_pipework_quantity = st.number_input(
                        "Quantity", min_value=0, step=1,
                        value=int(sub_state.get("pipework_quantity") or 0),
                        key=f"sampling_pipework_qty_{selected}_{sub_name}",
                    )

                    resolved_pipework_product = None if new_pipework_product == "(none selected)" else new_pipework_product
                    if resolved_pipework_product != sub_state.get("pipework_product_type") or new_pipework_quantity != sub_state.get("pipework_quantity"):
                        sub_state["pipework_product_type"] = resolved_pipework_product
                        sub_state["pipework_quantity"] = new_pipework_quantity
                        st.session_state.test_dirty = True

                    st.divider()
                    st.markdown("##### Sampling Points")

                    points_products = get_available_product_types(carbon_db.get("apparatus_output"), points_apparatus)

                    new_points_product = st.selectbox(
                        "Product Type", ["(none selected)"] + points_products,
                        index=(
                            (["(none selected)"] + points_products).index(sub_state.get("points_product_type"))
                            if sub_state.get("points_product_type") in points_products else 0
                        ),
                        key=f"sampling_points_product_{selected}_{sub_name}",
                    )
                    new_points_quantity = st.number_input(
                        "Quantity", min_value=0, step=1,
                        value=int(sub_state.get("points_quantity") or 0),
                        key=f"sampling_points_qty_{selected}_{sub_name}",
                    )

                    resolved_points_product = None if new_points_product == "(none selected)" else new_points_product
                    if resolved_points_product != sub_state.get("points_product_type") or new_points_quantity != sub_state.get("points_quantity"):
                        sub_state["points_product_type"] = resolved_points_product
                        sub_state["points_quantity"] = new_points_quantity
                        st.session_state.test_dirty = True

                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                continue

            if kind == "sprinkler_group":

                arrow_col, name_col = st.columns([0.5, 4])
                with arrow_col:
                    arrow_label = "▼" if sub_state["expanded"] else "▶"
                    toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")
                with name_col:
                    st.markdown(f"**{sub_name}**")

                if toggle_expand:
                    sub_state["expanded"] = not sub_state["expanded"]
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()

                if sub_state["expanded"]:

                    # ---- Heads ----
                    st.markdown("##### Sprinkler Heads")

                    new_heads_status = st.radio(
                        "Determination Method", ["N/A", "DTS", "PBD"],
                        index=["N/A", "DTS", "PBD"].index(sub_state["heads_status"]),
                        horizontal=True,
                        key=f"sprinkler_heads_status_{selected}_{sub_name}",
                    )
                    if new_heads_status != sub_state["heads_status"]:
                        sub_state["heads_status"] = new_heads_status
                        if new_heads_status == "DTS":
                            sub_state["heads_table"] = sprinkler_heads_dts_table()
                        elif new_heads_status == "PBD":
                            sub_state["heads_table"] = sprinkler_heads_pbd_table()
                        else:
                            sub_state["heads_table"] = empty_sprinkler_heads_table()
                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                        st.session_state.test_dirty = True
                        st.rerun()

                    if sub_state["heads_status"] == "N/A":
                        st.dataframe(empty_sprinkler_heads_table(), use_container_width=True, hide_index=True)
                        st.caption("The embodied carbon for this system is not considered.")
                    else:
                        heads_product_options = get_available_product_types(carbon_db.get("apparatus_output"), "Sprinkler Head")
                        is_dts_heads = sub_state["heads_status"] == "DTS"

                        edited_heads = st.data_editor(
                            sub_state["heads_table"],
                            use_container_width=True, hide_index=True,
                            num_rows="fixed" if is_dts_heads else "dynamic",
                            column_config={
                                "Product Type": st.column_config.SelectboxColumn(
                                    "Product Type", options=heads_product_options if heads_product_options else ["No products found"], required=False,
                                ),
                                "Determination Type": st.column_config.SelectboxColumn(
                                    "Determination Type", options=SPRINKLER_DETERMINATION_OPTIONS, required=True, disabled=is_dts_heads,
                                ),
                                "Value": st.column_config.NumberColumn("Value", min_value=0.0, required=True, disabled=is_dts_heads),
                                "Hazard Rating": st.column_config.SelectboxColumn(
                                    "Hazard Rating", options=HAZARD_RATING_OPTIONS, required=True, disabled=is_dts_heads,
                                ),
                            },
                            key=f"table_sprinkler_heads_{selected}_{sub_name}",
                        )

                        if not edited_heads.equals(sub_state["heads_table"]):
                            sub_state["heads_table"] = edited_heads
                            st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                            st.session_state.test_dirty = True

                    st.divider()

                    # ---- Pipework ----
                    st.markdown("##### Sprinkler Pipework")

                    pipework_product_options = get_available_product_types(carbon_db.get("apparatus_output"), "Sprinkler Pipework")

                    mode_col, product_col = st.columns(2)
                    with mode_col:
                        new_pipework_mode = st.radio(
                            "Mode", PIPEWORK_MODE_OPTIONS,
                            index=PIPEWORK_MODE_OPTIONS.index(sub_state["pipework_mode"]),
                            horizontal=True,
                            key=f"sprinkler_pipework_mode_{selected}_{sub_name}",
                        )
                    with product_col:
                        new_pipework_product = st.selectbox(
                            "Product Type", ["(none selected)"] + pipework_product_options,
                            index=(
                                (["(none selected)"] + pipework_product_options).index(sub_state.get("pipework_product_type"))
                                if sub_state.get("pipework_product_type") in pipework_product_options else 0
                            ),
                            key=f"sprinkler_pipework_product_{selected}_{sub_name}",
                        )

                    if new_pipework_mode != sub_state["pipework_mode"]:
                        sub_state["pipework_mode"] = new_pipework_mode
                        st.session_state.test_dirty = True

                    resolved_pipework_product = None if new_pipework_product == "(none selected)" else new_pipework_product
                    if resolved_pipework_product != sub_state.get("pipework_product_type"):
                        sub_state["pipework_product_type"] = resolved_pipework_product
                        st.session_state.test_dirty = True

                    if sub_state["pipework_mode"] == "Manual Override":
                        new_pipework_value = st.number_input(
                            "Pipework Length (m)", min_value=0.0, step=1.0,
                            value=float(sub_state.get("pipework_manual_value") or 0.0),
                            key=f"sprinkler_pipework_value_{selected}_{sub_name}",
                        )
                        if new_pipework_value != sub_state.get("pipework_manual_value"):
                            sub_state["pipework_manual_value"] = new_pipework_value
                            st.session_state.test_dirty = True
                    else:
                        st.number_input(
                            "Pipework Length (m) — calculated automatically",
                            value=0.0, disabled=True,
                            key=f"sprinkler_pipework_value_disabled_{selected}_{sub_name}",
                        )
                        st.caption(
                            "Formula: Risers × Storeys × Floor-to-Floor Height + "
                            "Sprinkler Number × Floor Area / √(Linear Spacing). "
                            "Requires Risers, Storeys, and Floor-to-Floor Height set "
                            "on the Project Information page, plus at least one Sprinkler Head row."
                        )
                        st.caption(
                            "⚠️ This default formula is an early-stage geometric approximation, "
                            "not a cited AS clause. Verify before relying on it for design."
                        )

                    st.divider()

                    # ---- Valves + Pumps (generic library) ----
                    for i, spec in enumerate(SPRINKLER_GROUP_CHILD_SPECS):
                        if i > 0:
                            st.divider()
                        comp_state = sub_state["group"]["components"][spec["key"]]
                        changed = render_component(
                            spec, comp_state, carbon_db.get("apparatus_output"),
                            parent_quantity=None,
                            key_prefix=f"sprinkler_group_{selected}_{sub_name}",
                        )
                        if changed:
                            st.session_state.test_dirty = True

                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                continue

            if kind == "component_group":

                specs = GROUP_DEFINITIONS[(selected, sub_name)]

                result = render_component_group(
                    sub_name, specs, sub_state, carbon_db.get("apparatus_output"),
                    key_prefix=f"group_{selected}_{sub_name}",
                )

                if result == "toggled":
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()
                elif result:
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.session_state.test_dirty = True

                continue
            
            if kind == "extinguisher":

                arrow_col, name_col, toggle_col = st.columns([0.5, 2, 3])

                with arrow_col:
                    arrow_label = "▼" if sub_state["expanded"] else "▶"
                    toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")

                with name_col:
                    st.markdown(f"**{sub_name}**")

                with toggle_col:
                    new_status = st.radio(
                        "Determination Method", ["N/A", "DTS", "PBD"],
                        index=["N/A", "DTS", "PBD"].index(sub_state["status"]),
                        horizontal=True,
                        key=f"status_toggle_{selected}_{sub_name}",
                        label_visibility="collapsed",
                    )

                if toggle_expand:
                    sub_state["expanded"] = not sub_state["expanded"]
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()

                if new_status != sub_state["status"]:
                    sub_state["status"] = new_status
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.session_state.test_dirty = True
                    st.rerun()

                if sub_state["expanded"]:

                    if sub_state["status"] == "N/A":

                        st.caption("The embodied carbon for this system is not considered.")

                    else:

                        is_dts = sub_state["status"] == "DTS"

                        # ==================================================
                        # Extinguishers
                        # ==================================================

                        st.markdown("##### Extinguishers")

                        col1, col2 = st.columns(2)

                        with col1:
                            new_hazard = st.selectbox(
                                "Hazard Classification", ["Light", "Ordinary", "High"],
                                index=["Light", "Ordinary", "High"].index(sub_state["hazard_class"]),
                                key=f"ext_hazard_{selected}_{sub_name}",
                            )
                            new_class_a = st.checkbox(
                                "Class A Fire Risk Present", value=sub_state["fire_class_a"],
                                key=f"ext_class_a_{selected}_{sub_name}",
                            )
                            new_class_b = st.checkbox(
                                "Class B Fire Risk Present", value=sub_state["fire_class_b"],
                                key=f"ext_class_b_{selected}_{sub_name}",
                            )

                        with col2:
                            new_suppression = st.checkbox(
                                "Fixed Automatic Fire Suppression Present in This Area",
                                value=sub_state["has_fixed_suppression"],
                                key=f"ext_suppression_{selected}_{sub_name}",
                            )
                            new_electronics = st.checkbox(
                                "Electrical / Electronics Equipment Present (aggravating factor)",
                                value=sub_state["electronics_present"],
                                key=f"ext_electronics_{selected}_{sub_name}",
                            )

                        for key, new_val in [
                            ("hazard_class", new_hazard), ("fire_class_a", new_class_a),
                            ("fire_class_b", new_class_b), ("has_fixed_suppression", new_suppression),
                            ("electronics_present", new_electronics),
                        ]:
                            if sub_state[key] != new_val:
                                sub_state[key] = new_val
                                st.session_state.test_dirty = True

                        # ---- Requirement warning (informational, both DTS and PBD) ----

                        requirement_lines = []

                        if new_class_a:
                            req_a = get_extinguisher_requirement(new_hazard, "A", new_suppression)
                            if req_a:
                                requirement_lines.append(
                                    f"Class A: minimum rating **{req_a['min_rating']}** "
                                    f"(covers up to {req_a['max_area']:,.0f} m² per extinguisher)"
                                )

                        if new_class_b:
                            req_b = get_extinguisher_requirement(new_hazard, "B", new_suppression)
                            if req_b:
                                travel_note = f", travel distance {req_b['travel_distance']} m" if req_b["travel_distance"] else ""
                                requirement_lines.append(
                                    f"Class B: minimum rating **{req_b['min_rating']}** "
                                    f"(covers up to {req_b['max_area']:,.0f} m² per extinguisher{travel_note})"
                                )

                        if new_electronics:
                            requirement_lines.append(
                                "Electronics/electrical equipment present: an **(E)-rated** "
                                "extinguisher is additionally required for use on live electrical equipment."
                            )

                        if requirement_lines:
                            st.warning(
                                "**Minimum extinguisher requirement for this circumstance:**\n\n"
                                + "\n\n".join(f"- {line}" for line in requirement_lines)
                                + "\n\nThis cannot be automatically verified against the selected "
                                "Product Type below - please confirm the chosen product meets or "
                                "exceeds these ratings."
                            )

                        extinguisher_products = get_available_product_types(
                            carbon_db.get("apparatus_output"), apparatus_name
                        )

                        new_product = st.selectbox(
                            "Product Type", ["(none selected)"] + extinguisher_products,
                            index=(
                                (["(none selected)"] + extinguisher_products).index(sub_state.get("product_type"))
                                if sub_state.get("product_type") in extinguisher_products else 0
                            ),
                            key=f"ext_product_{selected}_{sub_name}",
                        )
                        resolved_product = None if new_product == "(none selected)" else new_product
                        if resolved_product != sub_state.get("product_type"):
                            sub_state["product_type"] = resolved_product
                            st.session_state.test_dirty = True

                        if sub_state["status"] == "PBD":

                            det_col, val_col = st.columns(2)

                            with det_col:
                                new_det_type = st.selectbox(
                                    "Determination Type", EXTINGUISHER_DETERMINATION_OPTIONS,
                                    index=EXTINGUISHER_DETERMINATION_OPTIONS.index(sub_state["determination_type"]),
                                    key=f"ext_det_type_{selected}_{sub_name}",
                                )

                            with val_col:
                                new_override_value = st.number_input(
                                    "Value", min_value=0.0, step=1.0,
                                    value=float(sub_state.get("override_value") or 0.0),
                                    key=f"ext_override_value_{selected}_{sub_name}",
                                )

                            if new_det_type != sub_state["determination_type"] or new_override_value != sub_state.get("override_value"):
                                sub_state["determination_type"] = new_det_type
                                sub_state["override_value"] = new_override_value
                                st.session_state.test_dirty = True

                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                        # ==================================================
                        # Brackets
                        # ==================================================

                        st.divider()
                        st.markdown("##### Brackets")

                        new_bracket_included = st.checkbox(
                            "Include Brackets", value=sub_state["bracket_included"],
                            disabled=is_dts,
                            key=f"bracket_included_{selected}_{sub_name}",
                        )
                        if new_bracket_included != sub_state["bracket_included"] and not is_dts:
                            sub_state["bracket_included"] = new_bracket_included
                            st.session_state.test_dirty = True

                        if is_dts or new_bracket_included:

                            bracket_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Brackets"))
                            bracket_products = get_available_product_types(carbon_db.get("apparatus_output"), bracket_apparatus)

                            new_bracket_product = st.selectbox(
                                "Bracket Product Type", ["(none selected)"] + bracket_products,
                                index=(
                                    (["(none selected)"] + bracket_products).index(sub_state.get("bracket_product_type"))
                                    if sub_state.get("bracket_product_type") in bracket_products else 0
                                ),
                                key=f"bracket_product_{selected}_{sub_name}",
                            )
                            resolved_bracket_product = None if new_bracket_product == "(none selected)" else new_bracket_product
                            if resolved_bracket_product != sub_state.get("bracket_product_type"):
                                sub_state["bracket_product_type"] = resolved_bracket_product
                                st.session_state.test_dirty = True

                            if not is_dts:
                                new_bracket_mode = st.radio(
                                    "Bracket Quantity", BRACKET_CABINET_MODE_OPTIONS,
                                    index=BRACKET_CABINET_MODE_OPTIONS.index(sub_state["bracket_mode"]),
                                    horizontal=True,
                                    key=f"bracket_mode_{selected}_{sub_name}",
                                )
                                if new_bracket_mode != sub_state["bracket_mode"]:
                                    sub_state["bracket_mode"] = new_bracket_mode
                                    st.session_state.test_dirty = True

                                if sub_state["bracket_mode"] == "Quantity Override":
                                    new_bracket_qty = st.number_input(
                                        "Bracket Quantity", min_value=0, step=1,
                                        value=int(sub_state.get("bracket_quantity_override") or 0),
                                        key=f"bracket_qty_{selected}_{sub_name}",
                                    )
                                    if new_bracket_qty != sub_state.get("bracket_quantity_override"):
                                        sub_state["bracket_quantity_override"] = new_bracket_qty
                                        st.session_state.test_dirty = True
                            else:
                                st.caption("DTS: bracket quantity is set equal to the extinguisher quantity.")

                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                        # ==================================================
                        # Cabinets
                        # ==================================================

                        st.divider()
                        st.markdown("##### Cabinets")

                        new_cabinet_included = st.checkbox(
                            "Include Cabinets", value=sub_state["cabinet_included"],
                            disabled=is_dts,
                            key=f"cabinet_included_{selected}_{sub_name}",
                        )
                        if new_cabinet_included != sub_state["cabinet_included"] and not is_dts:
                            sub_state["cabinet_included"] = new_cabinet_included
                            st.session_state.test_dirty = True

                        if is_dts or new_cabinet_included:

                            cabinet_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Cabinets"))
                            cabinet_products = get_available_product_types(carbon_db.get("apparatus_output"), cabinet_apparatus)

                            new_cabinet_product = st.selectbox(
                                "Cabinet Product Type", ["(none selected)"] + cabinet_products,
                                index=(
                                    (["(none selected)"] + cabinet_products).index(sub_state.get("cabinet_product_type"))
                                    if sub_state.get("cabinet_product_type") in cabinet_products else 0
                                ),
                                key=f"cabinet_product_{selected}_{sub_name}",
                            )
                            resolved_cabinet_product = None if new_cabinet_product == "(none selected)" else new_cabinet_product
                            if resolved_cabinet_product != sub_state.get("cabinet_product_type"):
                                sub_state["cabinet_product_type"] = resolved_cabinet_product
                                st.session_state.test_dirty = True

                            if not is_dts:
                                new_cabinet_mode = st.radio(
                                    "Cabinet Quantity", BRACKET_CABINET_MODE_OPTIONS,
                                    index=BRACKET_CABINET_MODE_OPTIONS.index(sub_state["cabinet_mode"]),
                                    horizontal=True,
                                    key=f"cabinet_mode_{selected}_{sub_name}",
                                )
                                if new_cabinet_mode != sub_state["cabinet_mode"]:
                                    sub_state["cabinet_mode"] = new_cabinet_mode
                                    st.session_state.test_dirty = True

                                if sub_state["cabinet_mode"] == "Quantity Override":
                                    new_cabinet_qty = st.number_input(
                                        "Cabinet Quantity", min_value=0, step=1,
                                        value=int(sub_state.get("cabinet_quantity_override") or 0),
                                        key=f"cabinet_qty_{selected}_{sub_name}",
                                    )
                                    if new_cabinet_qty != sub_state.get("cabinet_quantity_override"):
                                        sub_state["cabinet_quantity_override"] = new_cabinet_qty
                                        st.session_state.test_dirty = True
                            else:
                                st.caption("DTS: cabinet quantity is set equal to the extinguisher quantity.")

                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                continue

            # ================================================
            # sprinkler_heads kind
            # ================================================
            if kind == "sprinkler_heads":

                arrow_col, name_col, toggle_col = st.columns([0.5, 2, 3])

                with arrow_col:
                    arrow_label = "▼" if sub_state["expanded"] else "▶"
                    toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")

                with name_col:
                    st.markdown(f"**{sub_name}**")

                with toggle_col:
                    new_status = st.radio(
                        "Determination Method", ["N/A", "DTS", "PBD"],
                        index=["N/A", "DTS", "PBD"].index(sub_state["status"]),
                        horizontal=True,
                        key=f"status_toggle_{selected}_{sub_name}",
                        label_visibility="collapsed",
                    )

                if toggle_expand:
                    sub_state["expanded"] = not sub_state["expanded"]
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()

                if new_status != sub_state["status"]:
                    sub_state["status"] = new_status
                    if new_status == "DTS":
                        sub_state["table"] = sprinkler_heads_dts_table()
                    elif new_status == "PBD":
                        sub_state["table"] = sprinkler_heads_pbd_table()
                    else:
                        sub_state["table"] = empty_sprinkler_heads_table()
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.session_state.test_dirty = True
                    st.rerun()

                if sub_state["expanded"]:

                    if sub_state["status"] == "N/A":
                        st.dataframe(empty_sprinkler_heads_table(), use_container_width=True, hide_index=True)
                        st.caption("The embodied carbon for this system is not considered.")

                    else:

                        product_options = get_available_product_types(
                            carbon_db.get("apparatus_output"), "Sprinkler Head"
                        )

                        is_dts = sub_state["status"] == "DTS"

                        edited = st.data_editor(
                            sub_state["table"],
                            use_container_width=True,
                            hide_index=True,
                            num_rows="fixed" if is_dts else "dynamic",
                            column_config={
                                "Product Type": st.column_config.SelectboxColumn(
                                    "Product Type",
                                    options=product_options if product_options else ["No products found"],
                                    required=False,
                                ),
                                "Determination Type": st.column_config.SelectboxColumn(
                                    "Determination Type",
                                    options=SPRINKLER_DETERMINATION_OPTIONS,
                                    required=True,
                                    disabled=is_dts,
                                ),
                                "Value": st.column_config.NumberColumn(
                                    "Value", min_value=0.0, required=True, disabled=is_dts,
                                ),
                                "Hazard Rating": st.column_config.SelectboxColumn(
                                    "Hazard Rating", options=HAZARD_RATING_OPTIONS, required=True, disabled=is_dts,
                                ),
                            },
                            key=f"table_sprinkler_heads_{selected}_{sub_name}",
                        )

                        if not edited.equals(sub_state["table"]):
                            st.session_state.test_categories[selected]["subcategories"][sub_name]["table"] = edited
                            st.session_state.test_dirty = True

                continue

            # ================================================
            # "simple" kind (default)
            # ================================================

            arrow_col, name_col, toggle_col = st.columns([0.5, 2, 3])

            with arrow_col:
                arrow_label = "▼" if sub_state["expanded"] else "▶"
                toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")

            with name_col:
                st.markdown(f"**{sub_name}**")

            with toggle_col:
                new_status = st.radio(
                    "Determination Method", ["N/A", "DTS", "PBD"],
                    index=["N/A", "DTS", "PBD"].index(sub_state["status"]),
                    horizontal=True,
                    key=f"status_toggle_{selected}_{sub_name}",
                    label_visibility="collapsed",
                )

            if toggle_expand:
                sub_state["expanded"] = not sub_state["expanded"]
                st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                st.rerun()

            if new_status != sub_state["status"]:
                sub_state["status"] = new_status
                if new_status == "DTS":
                    sub_state["table"] = dts_default_row(selected, sub_name)
                elif new_status == "PBD":
                    sub_state["table"] = pbd_default_row(selected, sub_name)
                else:
                    sub_state["table"] = empty_display_row()
                st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                st.session_state.test_dirty = True
                st.rerun()

            if sub_state["expanded"]:

                if sub_state["status"] == "N/A":
                    st.dataframe(empty_display_row(), use_container_width=True, hide_index=True)
                    st.caption("The embodied carbon for this system is not considered.")

                else:

                    product_options = get_available_product_types(
                        carbon_db.get("apparatus_output"), apparatus_name
                    )
                    is_dts = sub_state["status"] == "DTS"

                    edited = st.data_editor(
                        sub_state["table"],
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "Determination Type": st.column_config.SelectboxColumn(
                                "Determination Type", options=DETERMINATION_TYPE_OPTIONS,
                                required=True, disabled=is_dts,
                            ),
                            "Value": st.column_config.NumberColumn(
                                "Value", min_value=0.0, required=True, disabled=is_dts,
                            ),
                            "Product Type": st.column_config.SelectboxColumn(
                                "Product Type",
                                options=product_options if product_options else ["No products found"],
                                required=False,
                            ),
                        },
                        key=f"table_{selected}_{sub_name}",
                    )

                    if not edited.equals(sub_state["table"]):
                        st.session_state.test_categories[selected]["subcategories"][sub_name]["table"] = edited
                        st.session_state.test_dirty = True

    # ==========================================================
    # Calculate / Save / Results
    # ==========================================================

    st.divider()

    calculate = st.button("Calculate Embodied Carbon", use_container_width=True)

    if calculate:
        run_calculation()

    st.divider()

    save_label = "💾 Update Version" if st.session_state.test_editing_mode == "edit" else "💾 Save This Version"
    save_version = st.button(save_label, use_container_width=True)

    if save_version:
        if not info.get("project_name"):
            st.error("Please enter or select a project name before saving.")
        else:
            version_number = perform_save()
            if st.session_state.test_editing_mode == "edit":
                st.success(f"Version {version_number} of '{info['project_name']}' updated.")
            else:
                st.success(f"Saved as Version {version_number} of '{info['project_name']}'.")

    if not st.session_state.test_results_df.empty:

        summary = st.session_state.test_summary

        st.divider()
        st.subheader("Embodied Carbon Summary")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("A1-A3", f"{summary['A1-A3']:,.2f} kgCO₂e")
        col2.metric("A4", f"{summary['A4']:,.2f} kgCO₂e")
        col3.metric("A5", f"{summary['A5']:,.2f} kgCO₂e")
        col4.metric("Total", f"{summary['Total']:,.2f} kgCO₂e")

        st.divider()
        st.subheader("Calculation Results")
        st.dataframe(st.session_state.test_results_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Carbon Analysis Dashboard")

        left, right = st.columns(2)
        with left:
            fig = create_apparatus_pie_chart(st.session_state.test_results_df)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
        with right:
            fig = create_lifecycle_bar_chart(st.session_state.test_summary)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

    render_footer()