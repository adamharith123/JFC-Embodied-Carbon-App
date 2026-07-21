"""
FireCarbonApp v6
Embodied Carbon Calculation Engine

This module contains the engineering calculation logic.

No Streamlit code should be placed in this file.
"""

import pandas as pd


def _find_column(row, *candidates):
    """See utils/proposed_design_calculations.py::_find_column - same
    tolerance for the renamed A1-3/A4/A5 columns, kept local here so
    this module still doesn't depend on Streamlit or its sibling
    module."""
    for name in candidates:
        if name in row.index:
            return row[name]
    return None


# ==========================================================
# Existing Design Calculation
# ==========================================================

def calculate_existing_design(existing_design_df, apparatus_output_df):
    """
    Calculate embodied carbon for an Existing Design assessment.

    Parameters
    ----------
    existing_design_df : pd.DataFrame
        User-entered fire safety systems.

    apparatus_output_df : pd.DataFrame
        Apparatus Output worksheet from the carbon database.

    Returns
    -------
    pd.DataFrame
        Apparatus-level embodied carbon results.
    """

    if existing_design_df.empty:
        return pd.DataFrame()

    results = []

    for _, row in existing_design_df.iterrows():

        apparatus = row["Fire Safety System"]
        quantity = row["Quantity"]

        match = apparatus_output_df[
            apparatus_output_df["Apparatus"] == apparatus
        ]

        if match.empty:
            continue

        match = match.iloc[0]

        a13 = float(_find_column(match, "A1-3", "A1-3 (kg CO2e)") or 0) * quantity
        a4 = float(_find_column(match, "A4", "A4 (kg CO2e)") or 0) * quantity
        a5 = float(_find_column(match, "A5", "A5 (kg CO2e)") or 0) * quantity
        total = float(_find_column(match, "Total (A1-3 + A4 + A5)", "Total") or 0) * quantity

        results.append(
            {
                "Apparatus": apparatus,
                "Quantity": quantity,
                "A1-A3": a13,
                "A4": a4,
                "A5": a5,
                "Total": total,
            }
        )

    return pd.DataFrame(results)


# ==========================================================
# Results Summary
# ==========================================================

def summarise_results(results_df):
    """
    Summarise embodied carbon results.

    Parameters
    ----------
    results_df : pd.DataFrame

    Returns
    -------
    dict
    """

    if results_df.empty:

        return {
            "A1-A3": 0.0,
            "A4": 0.0,
            "A5": 0.0,
            "Total": 0.0,
        }

    return {

        "A1-A3": results_df["A1-A3"].sum(),

        "A4": results_df["A4"].sum(),

        "A5": results_df["A5"].sum(),

        "Total": results_df["Total"].sum(),

    }