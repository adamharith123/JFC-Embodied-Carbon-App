"""
FireCarbonApp v6
Embodied Carbon Calculation Engine

This module contains the engineering calculation logic.

No Streamlit code should be placed in this file.
"""

import pandas as pd


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

        a13 = float(match["A1-3"]) * quantity
        a4 = float(match["A4"]) * quantity
        a5 = float(match["A5"]) * quantity
        total = float(match["Total (A1-3 + A4 + A5)"]) * quantity

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
