from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

from utils.constants import (
    CARBON_DATABASE_FILE,
    STANDARDS_DATABASE_FILE,
)

# ==========================================================
# Generic Workbook Functions
# ==========================================================

def workbook_exists(path: Path) -> bool:
    """Return True if the workbook exists."""

    return path.exists() and path.suffix.lower() in [
        ".xlsx",
        ".xlsm",
        ".xls",
    ]


def get_workbook_sheet_names(path: Path):
    """Return worksheet names."""

    if not workbook_exists(path):
        return []

    wb = load_workbook(
        path,
        read_only=True,
        data_only=True,
    )

    return wb.sheetnames


def load_sheet(path: Path, sheet_name: str):
    """
    Load a worksheet into a pandas DataFrame.

    The BOQ worksheet has title rows above the
    column headings, so row 6 is used as the header.

    All other worksheets use the default header row.
    """

    if not workbook_exists(path):
        return pd.DataFrame()

    try:

        if sheet_name == "BOQ":

            return pd.read_excel(
                path,
                sheet_name=sheet_name,
                header=5,
            )
        if sheet_name == "Apparatus Output":

            return pd.read_excel(
                path,
                sheet_name=sheet_name,
                header=1,
            )

        return pd.read_excel(
            path,
            sheet_name=sheet_name,
        )

    except Exception:

        return pd.DataFrame()


# ==========================================================
# Carbon Database
# ==========================================================

def load_carbon_database():
    """
    Load the embodied carbon database.

    Returns
    -------
    dict
        Dictionary containing all engineering datasets
        required by the application.
    """

    boq = load_sheet(
        CARBON_DATABASE_FILE,
        "BOQ",
    )

    apparatus_output = load_sheet(
        CARBON_DATABASE_FILE,
        "Apparatus Output",
    )

    dropdowns = load_sheet(
        CARBON_DATABASE_FILE,
        "dropdowns",
    )

    systems = []

    # Prefer Apparatus Output because it is already
    # aggregated at apparatus level.

    if (
        not apparatus_output.empty
        and "Apparatus" in apparatus_output.columns
    ):

        systems = (
            apparatus_output["Apparatus"]
            .dropna()
            .astype(str)
            .sort_values()
            .unique()
            .tolist()
        )

    # Fallback to BOQ if required

    elif (
        not boq.empty
        and "Apparatus" in boq.columns
    ):

        systems = (
            boq["Apparatus"]
            .dropna()
            .astype(str)
            .sort_values()
            .unique()
            .tolist()
        )

    return {

        "path": CARBON_DATABASE_FILE,

        "exists": workbook_exists(
            CARBON_DATABASE_FILE
        ),

        "sheets": get_workbook_sheet_names(
            CARBON_DATABASE_FILE
        ),

        "boq": boq,

        "apparatus_output": apparatus_output,

        "dropdowns": dropdowns,

        "systems": systems,

    }


# ==========================================================
# Standards Database
# ==========================================================

def load_standards_database():
    """
    Load the standards database.
    """

    return {

        "path": STANDARDS_DATABASE_FILE,

        "exists": workbook_exists(
            STANDARDS_DATABASE_FILE
        ),

        "sheets": get_workbook_sheet_names(
            STANDARDS_DATABASE_FILE
        ),

        "standards_list": load_sheet(
            STANDARDS_DATABASE_FILE,
            "Standards List",
        ),

        "building_class": load_sheet(
            STANDARDS_DATABASE_FILE,
            "Building Class",
        ),

    }


# ==========================================================
# Application Loader
# ==========================================================

def load_all_databases():

    return {

        "carbon": load_carbon_database(),

        "standards": load_standards_database(),

    }


# ==========================================================
# Database Status
# ==========================================================

def database_status_summary():

    db = load_all_databases()

    return {

        "Carbon Database": {

            "exists": db["carbon"]["exists"],

            "path": db["carbon"]["path"],

            "sheets": db["carbon"]["sheets"],

            "apparatus": len(
                db["carbon"]["apparatus_output"]
            ),

            "boq_rows": len(
                db["carbon"]["boq"]
            ),

        },

        "Standards Database": {

            "exists": db["standards"]["exists"],

            "path": db["standards"]["path"],

            "sheets": db["standards"]["sheets"],

            "rows": len(
                db["standards"]["standards_list"]
            ),

        },

    }

# ==========================================================
# Proposed Design Helpers
# ==========================================================

def get_building_classes():
    """
    Return the available NCC building classes.
    """

    df = load_standards_database()["building_class"]

    if df.empty:
        return []

    first_col = df.columns[0]

    return (
        df[first_col]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


def get_standards_list():
    """
    Return the Standards List worksheet.
    """

    return load_standards_database()["standards_list"]