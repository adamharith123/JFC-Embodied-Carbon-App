"""
FireCarbonApp v6

Design Engine

Engineering logic for generating fire safety systems
from editable engineering databases.

No Streamlit UI code.
"""

import pandas as pd


def get_required_systems(
    building_class: str,
    building_class_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return all applicable fire safety systems
    for the selected NCC Building Class.

    Parameters
    ----------
    building_class
        Selected NCC Building Class.

    building_class_df
        Building Class worksheet.

    Returns
    -------
    pd.DataFrame
    """

    if building_class_df.empty:
        return pd.DataFrame()

    building_class = str(building_class).strip()

    print("\n========== DESIGN ENGINE DEBUG ==========")
    print("Selected Building Class:", building_class)
    print("\nColumns:")
    print(building_class_df.columns.tolist())

    print("\nData Preview:")
    print(building_class_df.head(10))

    print("=========================================\n")

    first_column = building_class_df.columns[0]

    row = building_class_df[
        building_class_df[first_column]
        .astype(str)
        .str.startswith(building_class)
    ]

    if row.empty:
        return pd.DataFrame()

    row = row.iloc[0]

    systems = []

    for column in building_class_df.columns[1:]:

        value = str(row[column]).strip().lower()

        if value.startswith("yes"):

            systems.append(
                {
                    "Fire Safety System": column,
                    "Requirement": "Required",
                }
            )

        elif value.startswith("conditional"):

            systems.append(
                {
                    "Fire Safety System": column,
                    "Requirement": "Conditional",
                }
            )

    return pd.DataFrame(systems)
