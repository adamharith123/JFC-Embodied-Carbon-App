"""
Proposed Design - Embodied Carbon Calculations

Deliberately kept separate from any Streamlit code, with plain,
descriptive variable names, so this logic can be read, checked, and
changed without needing to touch the UI file.
"""

import pandas as pd


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


def _find_column(row, *candidates):
    """
    Returns the value of the first column name in `candidates` that
    actually exists on `row`. The database's carbon-factor column
    names have changed before (e.g. "A1-3" -> "A1-3 (kg CO2e)") -
    this keeps the calculation working across either naming instead
    of hard-failing with a KeyError the next time a column gets
    renamed.
    """
    for name in candidates:
        if name in row.index:
            return row[name]
    return None


def calculate_component_carbon(equivalent_quantity, carbon_factors_row):
    """
    Multiplies an equivalent quantity by one row of per-unit
    embodied carbon factors, returning the A1-3 / A4 / A5 / Total
    contributions.

    carbon_factors_row : a pandas Series with "A1-3", "A4", "A5",
                          and "Total (A1-3 + A4 + A5)" / "Total GWP (A1-3 + A4 + A5)"
                          columns - taken from either Apparatus Output
                          or Product Output.
    """

    def _factor(value):
        # Some database rows leave A4/A5 blank rather than 0 (e.g.
        # products with no declared transport or end-of-life stage) -
        # treat a missing factor as 0 rather than letting NaN propagate
        # into the results table.
        try:
            if value is None or (isinstance(value, float) and value != value):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    carbon_a1_3 = _factor(_find_column(carbon_factors_row, "A1-3", "A1-3 (kg CO2e)")) * equivalent_quantity
    carbon_a4 = _factor(_find_column(carbon_factors_row, "A4", "A4 (kg CO2e)")) * equivalent_quantity
    carbon_a5 = _factor(_find_column(carbon_factors_row, "A5", "A5 (kg CO2e)")) * equivalent_quantity
    carbon_total = _factor(_find_column(
        carbon_factors_row, "Total (A1-3 + A4 + A5)", "Total GWP (A1-3 + A4 + A5)", "Total"
    )) * equivalent_quantity

    return {
        "A1-A3": carbon_a1_3,
        "A4": carbon_a4,
        "A5": carbon_a5,
        "Total": carbon_total,
    }


def _normalise_apparatus_name(name):
    """Whitespace/case-insensitive key for matching apparatus names."""
    return str(name).strip().casefold()


# Product Type values that mean "no real variant chosen yet" - either
# genuinely blank, or the literal placeholder text some rows use
# while real product data hasn't been sourced. Both should behave
# the same way in the UI: a single "Standard" option, not a dropdown
# with a meaningless placeholder value in it.
_PLACEHOLDER_PRODUCT_TYPES = {"", "demo type"}


def find_carbon_factors_row(apparatus_output_df, apparatus_name):
    """
    Looks up the generic (apparatus-level average) carbon factors
    for a given apparatus name from the Apparatus Output sheet.
    Matching is case/whitespace-insensitive, since the database and
    the app's own component names don't always agree on casing
    (e.g. "Heat Detector" vs "Heat detector").
    """

    if apparatus_output_df is None or apparatus_output_df.empty:
        return None

    target = _normalise_apparatus_name(apparatus_name)
    matching_rows = apparatus_output_df[
        apparatus_output_df["Apparatus"].apply(_normalise_apparatus_name) == target
    ]

    if matching_rows.empty:
        return None

    return matching_rows.iloc[0]


def find_product_carbon_factors_row(apparatus_output_df, apparatus_name, product_type_name):
    """
    Looks up a specific product variant's carbon factors from the
    Apparatus Output sheet, filtered to rows matching both the
    apparatus and the specific Product Type.

    Apparatus name matching is case/whitespace-insensitive (see
    find_carbon_factors_row). Most apparatus have a single row whose
    Product Type is blank or the literal placeholder "Demo Type" (no
    real variant yet) - get_available_product_types() returns
    "Standard" as the placeholder option for those, so here a
    "Standard" selection matches any placeholder-Product-Type row
    rather than requiring an exact "Standard" text match that will
    never exist in the data.
    """

    if apparatus_output_df is None or apparatus_output_df.empty:
        return None

    if "Product Type" not in apparatus_output_df.columns:
        return find_carbon_factors_row(apparatus_output_df, apparatus_name)

    target = _normalise_apparatus_name(apparatus_name)
    matching_rows = apparatus_output_df[
        apparatus_output_df["Apparatus"].apply(_normalise_apparatus_name) == target
    ]

    if matching_rows.empty:
        return None

    product_types = matching_rows["Product Type"].fillna("").astype(str).str.strip()
    is_placeholder = product_types.str.casefold().isin(_PLACEHOLDER_PRODUCT_TYPES)
    has_real_variants = (~is_placeholder).any()

    if not has_real_variants:
        return matching_rows.iloc[0]

    selected = str(product_type_name).strip()
    match = matching_rows[product_types == selected]

    if match.empty:
        return None

    return match.iloc[0]


def get_available_product_types(apparatus_output_df, apparatus_name):
    """
    Returns the list of Product Type names available for a given
    apparatus, read from the Apparatus Output sheet.

    Most apparatus have exactly one row whose Product Type is blank
    or the literal placeholder "Demo Type" - for those, return a
    single placeholder option ("Standard") so the dropdown has
    something selectable that isn't confusing filler text. A handful
    of apparatus (e.g. "Sprinkler head", "Illuminated exit sign")
    genuinely have multiple real named variants - for those, return
    the real variant names instead.
    """

    if apparatus_output_df is None or apparatus_output_df.empty:
        return []

    if "Product Type" not in apparatus_output_df.columns:
        target = _normalise_apparatus_name(apparatus_name)
        matching_rows = apparatus_output_df[
            apparatus_output_df["Apparatus"].apply(_normalise_apparatus_name) == target
        ]
        return ["Standard"] if not matching_rows.empty else []

    target = _normalise_apparatus_name(apparatus_name)
    matching_rows = apparatus_output_df[
        apparatus_output_df["Apparatus"].apply(_normalise_apparatus_name) == target
    ]

    if matching_rows.empty:
        return []

    product_types = matching_rows["Product Type"].fillna("").astype(str).str.strip()
    real_types = sorted(
        set(
            product_types[~product_types.str.casefold().isin(_PLACEHOLDER_PRODUCT_TYPES)]
        )
    )

    return real_types if real_types else ["Standard"]


# ==========================================================
# FRL (min) Lookup - Category 5 Wall Assemblies
# ==========================================================
#
# Decoupled from Product Type on purpose: Product Type selects the
# material/grade (e.g. a concrete grade), FRL(min) selects a required
# fire-resistance rating - the frl_reference sheet is what converts
# that combination into a thickness (Concrete/Masonry/Speed Panel,
# converted to a carbon quantity via a standard reference density) or
# a layer count (Plasterboard, whose per-m² factor is already one
# board layer). Required FRL is always a direct user override - no
# NCC lookup is ever performed here.

def get_frl_options(frl_reference_df, apparatus_name, product_type_name):
    """
    Returns the sorted list of FRL(min) values available for a given
    apparatus (+ product type, when the apparatus's thickness table
    depends on it, e.g. Plasterboard's board thickness).
    """

    if frl_reference_df is None or frl_reference_df.empty:
        return []

    target = _normalise_apparatus_name(apparatus_name)
    rows = frl_reference_df[
        frl_reference_df["Apparatus"].apply(_normalise_apparatus_name) == target
    ]

    if rows.empty:
        return []

    product_types = rows["Product Type"].fillna("").astype(str).str.strip()
    row_is_general = product_types == ""

    if product_type_name and (product_types == str(product_type_name).strip()).any():
        rows = rows[(product_types == str(product_type_name).strip()) | row_is_general]
    else:
        rows = rows[row_is_general]

    return sorted(int(v) for v in rows["FRL (min)"].dropna().unique())


def resolve_frl_multiplier(frl_reference_df, apparatus_name, product_type_name, frl_value):
    """
    Returns (multiplier, detail_text) for converting an entered wall
    area (m²) into the quantity the apparatus's carbon factor expects,
    or None if no matching row is found.

    - Thickness-based rows (Concrete/Masonry/Speed Panel): the
      Apparatus Output factor is per kg, so multiplier = thickness(m)
      x density(kg/m3), giving kg per m² of wall.
    - Layer-based rows (Plasterboard): the Apparatus Output factor is
      already per m² of a single board layer, so multiplier = layer
      count, giving m² of board per m² of wall.
    """

    if frl_reference_df is None or frl_reference_df.empty or frl_value is None:
        return None

    target = _normalise_apparatus_name(apparatus_name)
    rows = frl_reference_df[
        frl_reference_df["Apparatus"].apply(_normalise_apparatus_name) == target
    ]

    if rows.empty:
        return None

    product_types = rows["Product Type"].fillna("").astype(str).str.strip()
    selected = str(product_type_name).strip() if product_type_name else ""

    matches = rows[rows["FRL (min)"].astype(float) == float(frl_value)]
    if product_type_name:
        exact = matches[product_types.loc[matches.index] == selected]
        if not exact.empty:
            matches = exact
        else:
            matches = matches[product_types.loc[matches.index] == ""]

    if matches.empty:
        return None

    row = matches.iloc[0]

    layers = row.get("Layers")
    if pd.notna(layers):
        return float(layers), f"{int(layers)} board layer(s)"

    thickness_mm = row.get("Thickness (mm)")
    density = row.get("Density (kg/m3)")
    if pd.notna(thickness_mm) and pd.notna(density):
        thickness_m = float(thickness_mm) / 1000.0
        return thickness_m * float(density), f"{thickness_mm:g}mm thick @ {density:g} kg/m³"

    return None

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
