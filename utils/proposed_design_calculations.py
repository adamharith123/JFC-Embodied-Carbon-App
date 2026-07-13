"""
Proposed Design - Embodied Carbon Calculations

Deliberately kept separate from any Streamlit code, with plain,
descriptive variable names, so this logic can be read, checked, and
changed without needing to touch the UI file.
"""


def calculate_equivalent_quantity(determination_type, input_value, building_area_m2):
    """
    Converts a user's raw input into an equivalent quantity to
    multiply against per-unit carbon factors.

    determination_type : "total_quantity" or "grid_spacing"
    input_value         : the number the user typed in (either a
                           straight count, or a grid spacing side
                           length in metres)
    building_area_m2    : the building's floor area - only used for
                           the grid spacing calculation

    Returns the equivalent quantity, or None if it can't be
    calculated (e.g. building area is missing for grid spacing).
    """

    if determination_type == "total_quantity":
        total_units = input_value
        return total_units

    if determination_type == "grid_spacing":

        if not building_area_m2 or building_area_m2 <= 0:
            return None

        grid_spacing_side_length_m = input_value
        equivalent_quantity = building_area_m2 / grid_spacing_side_length_m
        return equivalent_quantity

    return None


def calculate_component_carbon(equivalent_quantity, carbon_factors_row):
    """
    Multiplies an equivalent quantity by one row of per-unit
    embodied carbon factors, returning the A1-3 / A4 / A5 / Total
    contributions.

    carbon_factors_row : a pandas Series with "A1-3", "A4", "A5",
                          and "Total (A1-3 + A4 + A5)" columns -
                          taken from either Apparatus Output or
                          Product Output.
    """

    carbon_a1_3 = float(carbon_factors_row["A1-3"]) * equivalent_quantity
    carbon_a4 = float(carbon_factors_row["A4"]) * equivalent_quantity
    carbon_a5 = float(carbon_factors_row["A5"]) * equivalent_quantity
    carbon_total = float(carbon_factors_row["Total (A1-3 + A4 + A5)"]) * equivalent_quantity

    return {
        "A1-A3": carbon_a1_3,
        "A4": carbon_a4,
        "A5": carbon_a5,
        "Total": carbon_total,
    }


def find_carbon_factors_row(apparatus_output_df, apparatus_name):
    """
    Looks up the generic (apparatus-level average) carbon factors
    for a given apparatus name from the Apparatus Output sheet.
    """

    matching_rows = apparatus_output_df[
        apparatus_output_df["Apparatus"] == apparatus_name
    ]

    if matching_rows.empty:
        return None

    return matching_rows.iloc[0]


def find_product_carbon_factors_row(apparatus_output_df, apparatus_name, product_type_name):
    """
    Looks up a specific branded product's carbon factors from the
    Apparatus Output sheet, filtered to rows matching both the
    apparatus and the specific Product Type.
    """

    if apparatus_output_df is None or apparatus_output_df.empty:
        return None

    matching_rows = apparatus_output_df[
        (apparatus_output_df["Apparatus"] == apparatus_name)
        & (apparatus_output_df["Product Type"] == product_type_name)
    ]

    if matching_rows.empty:
        return None

    return matching_rows.iloc[0]


def get_available_product_types(apparatus_output_df, apparatus_name):
    """
    Returns the list of Product Type names available for a given
    apparatus, read from the Apparatus Output sheet - e.g. the
    specific branded components that exist for "Smoke Detector".
    """

    if apparatus_output_df is None or apparatus_output_df.empty:
        return []

    matching_rows = apparatus_output_df[
        apparatus_output_df["Apparatus"] == apparatus_name
    ]

    return (
        matching_rows["Product Type"]
        .dropna()
        .astype(str)
        .sort_values()
        .unique()
        .tolist()
    )

import math


# ==========================================================
# Sprinklers
# ==========================================================

SPRINKLER_HAZARD_AREA_PER_HEAD_M2 = {
    "Low": 21,
    "Ordinary": 12,
    "High": 9,
}


def default_linear_spacing_for_hazard(hazard_rating):
    """
    Converts a hazard classification's area-per-head allowance into
    an equivalent linear spacing (m), since Area = Linear Spacing^2.
    """
    area_per_head_m2 = SPRINKLER_HAZARD_AREA_PER_HEAD_M2.get(hazard_rating, 12)
    return math.sqrt(area_per_head_m2)


def calculate_sprinkler_head_quantity(determination_type, input_value, building_area_m2):
    """
    determination_type : "quantity" or "linear_spacing"
    input_value         : either a straight head count, or a linear
                           spacing value in metres
    """

    if determination_type == "quantity":
        return input_value

    if determination_type == "linear_spacing":
        if not building_area_m2 or building_area_m2 <= 0:
            return None
        if not input_value or input_value <= 0:
            return None
        return building_area_m2 / (input_value ** 2)

    return None


def calculate_sprinkler_pipework_default_length(
    num_risers,
    num_storeys,
    floor_to_floor_height_m,
    sprinkler_head_quantity,
    floor_area_m2,
    linear_spacing_m,
):
    """
    Risers x Storeys x Floor-to-Floor Height + Sprinkler Number x
    Floor Area / sqrt(Linear Spacing)

    Returns None if any required input is missing or zero, since the
    formula can't be evaluated meaningfully without all of them.
    """

    required_inputs = [
        num_risers,
        num_storeys,
        floor_to_floor_height_m,
        sprinkler_head_quantity,
        floor_area_m2,
        linear_spacing_m,
    ]

    if any(v is None or v == 0 for v in required_inputs):
        return None

    riser_length = num_risers * num_storeys * floor_to_floor_height_m
    lateral_length = (sprinkler_head_quantity * floor_area_m2) / math.sqrt(linear_spacing_m)

    return riser_length + lateral_length


# ==========================================================
# Hose Reels (calculation logic ready - UI not yet wired)
# ==========================================================

DEFAULT_HOSE_REEL_COVERAGE_AREA_M2 = 30


def calculate_hose_reel_count(total_area_m2, coverage_area_per_reel_m2=None):
    coverage = coverage_area_per_reel_m2 or DEFAULT_HOSE_REEL_COVERAGE_AREA_M2
    if not total_area_m2 or coverage <= 0:
        return None
    return total_area_m2 / coverage


# ==========================================================
# Extinguishers (calculation logic ready - UI not yet wired)
# ==========================================================
# Per spec: the descriptive-input mode (fire class / hazard / type /
# special risk) always contributes zero for now. Only Quantity
# Override actually calculates.

def calculate_extinguisher_quantity(mode, quantity_override_value):
    if mode == "quantity_override":
        return quantity_override_value
    return 0  # descriptive-input mode always returns 0, per spec


# ==========================================================
# Emergency Lighting (calculation logic ready - UI not yet wired)
# ==========================================================

DEFAULT_LUMINAIRE_COVERAGE_M2 = 100
DEFAULT_EGRESS_CORRIDOR_FACTOR = 10


def calculate_luminaire_count(
    protected_area_m2,
    number_of_exits,
    number_of_stairs,
    coverage_per_luminaire_m2=None,
    egress_corridor_factor=None,
    luminaire_count_override=None,
):
    if luminaire_count_override:
        return luminaire_count_override

    coverage = coverage_per_luminaire_m2 or DEFAULT_LUMINAIRE_COVERAGE_M2
    egress_factor = egress_corridor_factor or DEFAULT_EGRESS_CORRIDOR_FACTOR

    if not protected_area_m2 or coverage <= 0:
        return None

    base_count = (protected_area_m2 / coverage) * egress_factor
    return base_count + (number_of_exits or 0) + (2 * (number_of_stairs or 0))