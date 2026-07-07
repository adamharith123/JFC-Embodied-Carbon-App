import shutil
from datetime import datetime

import streamlit as st

from utils.constants import (
    APP_SUBTITLE,
    APP_STATUS,
    CARBON_DATABASE_FILE,
    STANDARDS_DATABASE_FILE,
    COMPONENT_DATABASE_FILE,
    ARCHIVE_DIR,
)
from utils.styles import apply_global_styles, render_header, render_footer
from utils.database_validator import validate_required_sheets

st.set_page_config(page_title="Database Manager", page_icon="🗃", layout="wide")
apply_global_styles()

render_header("Database Manager", APP_SUBTITLE, APP_STATUS)

st.markdown("## Managed Databases")

databases = {
    "Carbon Database": {
        "path": CARBON_DATABASE_FILE,
        "required_sheets": ["BOQ", "dropdowns"],
    },
    "Standards Database": {
        "path": STANDARDS_DATABASE_FILE,
        "required_sheets": ["Standards List", "Building Class"],
    },
    "Component Database": {
        "path": COMPONENT_DATABASE_FILE,
        "required_sheets": [],
    },
}

for name, config in databases.items():
    st.markdown(f"### {name}")

    path = config["path"]

    if path.exists():
        st.success("Current database found")
        st.caption(str(path))

        with open(path, "rb") as file:
            st.download_button(
                label=f"Download current {name}",
                data=file,
                file_name=path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"download_{name}",
            )
    else:
        st.warning("Current database not found")

    uploaded_file = st.file_uploader(
        f"Import updated {name}",
        type=["xlsx", "xlsm", "xls"],
        key=f"upload_{name}",
    )

    if uploaded_file is not None:
        temp_path = path.parent / f"_temp_{uploaded_file.name}"

        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        validation = validate_required_sheets(
            temp_path,
            config["required_sheets"],
        )

        if validation["valid"]:
            st.success("Workbook validation passed.")

            if st.button(f"Confirm import {name}", key=f"confirm_{name}"):
                ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

                if path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archived_name = f"{path.stem}_{timestamp}{path.suffix}"
                    shutil.copy2(path, ARCHIVE_DIR / archived_name)

                shutil.move(temp_path, path)

                st.success(f"{name} imported successfully. Please refresh the app.")
                st.rerun()

        else:
            st.error("Workbook validation failed.")
            st.write("Missing sheets:", validation["missing_sheets"])

        st.divider()

render_footer()