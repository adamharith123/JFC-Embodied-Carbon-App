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