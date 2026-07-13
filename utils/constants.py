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

CARBON_DATABASE_FILE = DATABASE_DIR / "carbon_database_master.xlsx"
STANDARDS_DATABASE_FILE = DATABASE_DIR / "standards_database_master.xlsx"
USER_INPUT_DATABASE_FILE = DATABASE_DIR / "user_input_database.xlsx"
COMPONENT_DATABASE_FILE = DATABASE_DIR / "component_database_master.xlsx"

ARUP_LOGO = ASSETS_DIR / "arup_logo.png"
JFC_LOGO = ASSETS_DIR / "jfc_logo.png"

ARUP_RED = "#D71920"
ARUP_DARK_RED = "#B51219"
SOFT_RED = "#FBEAEA"
CHARCOAL = "#202020"
LIGHT_GREY = "#F7F7F7"
MID_GREY = "#666666"
