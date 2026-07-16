from pathlib import Path

APP_NAME = "Fire Safety Embodied Carbon App"
APP_VERSION = "v6.0"
APP_STATUS = "Internal Demonstration"
APP_SUBTITLE = (
    "Developed by Jacaranda Flame Consulting<br>"
    "in collaboration with ARUP"
)
ROOT_DIR = Path(__file__).resolve().parents[1]

ASSETS_DIR = ROOT_DIR / "assets"
DATABASE_DIR = ROOT_DIR / "database" / "databases"
TEMPLATE_DIR = ROOT_DIR / "database" / "templates"
ARCHIVE_DIR = ROOT_DIR / "database" / "archive"
EXPORT_DIR = ROOT_DIR / "exports"
REPORT_DIR = ROOT_DIR / "reports"

CARBON_DATABASE_FILE = DATABASE_DIR / "ARUP_v2_app.xlsx"
MASTER_CARBON_DATABASE_FILE = DATABASE_DIR / "ARUP_v2.xlsx"
# CARBON_DATABASE_FILE points at a trimmed, app-only copy - just the
# "Apparatus Output" and "dropdowns" sheets, frozen as static values.
# ARUP_v2.xlsx (also in this folder) is the real master/authoring file
# - it has live formulas (Apparatus Output SUMIFs against a BOQ table
# in Estimate Calculator) and its Apparatus Output sheet has a bloated
# used-range that makes it ~36s slower to parse than it needs to be.
# Whenever ARUP_v2.xlsx's Apparatus Output values are updated, someone
# needs to regenerate ARUP_v2_app.xlsx from it (extract Apparatus
# Output + dropdowns via a read-only, data_only=True pass - never
# re-save ARUP_v2.xlsx itself through openpyxl, since that wipes the
# cached values of its formula-heavy sheets).
STANDARDS_DATABASE_FILE = DATABASE_DIR / "Standards database_exp.xlsx"
USER_INPUT_DATABASE_FILE = DATABASE_DIR / "User Input List.xlsx"
CALC_RULES_DATABASE_FILE = DATABASE_DIR / "Standards_Calc_Database.xlsx"
# COMPONENT_DATABASE_FILE = DATABASE_DIR / "component_database_master.xlsx"

# New as of 16 July — FRL lookup data (material thickness -> FRL rating,
# Class 9 additional requirements). Not yet consumed anywhere in
# database_loader.py / standards_engine.py; wiring this in is separate
# follow-up work, not part of this file-replacement pass.
FRL_DATABASE_FILE = DATABASE_DIR / "Fire Resistance Level (FRL).xlsx"

ARUP_LOGO = ASSETS_DIR / "arup_logo.png"
JFC_LOGO = ASSETS_DIR / "jfc_logo.png"

ARUP_RED = "#D71920"
ARUP_DARK_RED = "#B51219"
SOFT_RED = "#FBEAEA"
CHARCOAL = "#202020"
LIGHT_GREY = "#F7F7F7"
MID_GREY = "#666666"
