import streamlit as st
import pandas as pd

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import (
    apply_global_styles,
    render_header,
    render_footer,
)

from utils.project_store import (
    get_project_names,
    get_project_meta,
    get_next_version_number,
    save_project_version,
)

from utils.database_loader import load_carbon_database
from utils.calculations import (
    calculate_existing_design,
    summarise_results,
)



from utils.charts import (
    create_apparatus_pie_chart,
    create_lifecycle_bar_chart,
)
# ==========================================================
# Page Configuration
# ==========================================================

st.set_page_config(
    page_title="Existing Design",
    page_icon="📋",
    layout="wide",
)

apply_global_styles()

st.markdown(
    """
    <style>
    .st-key-manual_table_disabled,
    .st-key-csv_upload_disabled {
        opacity: 0.4;
        pointer-events: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_header(
    "Existing Design",
    APP_SUBTITLE,
    APP_STATUS,
)

# ==========================================================
# Load Databases
# ==========================================================

carbon_db = load_carbon_database()

fire_systems = carbon_db.get("systems", [])

if not fire_systems:
    st.error("No fire safety systems were found in the Carbon Database.")
    st.stop()

# ==========================================================
# Session State
# ==========================================================

if "existing_design_df" not in st.session_state:
    st.session_state.existing_design_df = pd.DataFrame(
        columns=[
            "Fire Safety System",
            "Quantity",
        ]
    )

if "existing_results_df" not in st.session_state:
    st.session_state.existing_results_df = pd.DataFrame()

if "existing_summary" not in st.session_state:
    st.session_state.existing_summary = {}

if "use_manual_table" not in st.session_state:
    st.session_state.use_manual_table = True

if "use_csv_upload" not in st.session_state:
    st.session_state.use_csv_upload = False

if "csv_upload_df" not in st.session_state:
    st.session_state.csv_upload_df = pd.DataFrame(
        columns=["Fire Safety System", "Quantity"]
    )

if "show_csv_preview" not in st.session_state:
    st.session_state.show_csv_preview = False

# ==========================================================
# Page Introduction
# ==========================================================

st.markdown(
    """
Estimate the upfront embodied carbon of an existing building by
manually entering the installed fire safety systems.

The available systems are loaded directly from the Carbon Database.
"""
)

# ==========================================================
# Project Information
# ==========================================================

st.subheader("Project Information")

project_mode = st.radio(
    "Project Type",
    ["New Project", "Existing Project"],
    horizontal=True,
    key="project_mode",
)

if project_mode == "New Project":

    col1, col2 = st.columns(2)

    with col1:
        project_name = st.text_input(
            "Project Name",
            placeholder="Example: ABC Office Fitout",
        )

    with col2:
        building_area = st.number_input(
            "Building Area (m²)",
            min_value=0.0,
            step=1.0,
        )

    assessment_notes = st.text_area(
        "Assessment Notes",
        placeholder="Optional project notes...",
    )

    next_version = 1

else:

    existing_projects = get_project_names()

    if not existing_projects:
        st.info("No existing projects found yet. Create a New Project first.")
        st.stop()

    col1, col2 = st.columns(2)

    with col1:
        project_name = st.selectbox(
            "Select Project",
            existing_projects,
        )

    project_meta = get_project_meta(project_name)

    with col2:
        building_area = st.number_input(
            "Building Area (m²)",
            min_value=0.0,
            step=1.0,
            value=float(project_meta["area"]),
        )

    assessment_notes = st.text_area(
        "Assessment Notes",
        value=project_meta["notes"],
    )

    next_version = get_next_version_number(project_name)

    st.info(f"This will be saved as **Version {next_version}** of '{project_name}'.")

version_notes = st.text_area(
    "Version Notes",
    placeholder="Describe what changed in this design iteration...",
)

st.divider()

# ==========================================================
# Fire Safety Systems
# ==========================================================

st.subheader("Existing Fire Safety Systems")

left, middle, right = st.columns([4, 1, 1])

with left:
    system = st.selectbox(
        "Fire Safety System",
        fire_systems,
    )

with middle:
    quantity = st.number_input(
        "Quantity",
        min_value=1,
        step=1,
    )

with right:
    st.write("")
    st.write("")
    add_system = st.button(
        "Add",
        use_container_width=True,
    )

# ==========================================================
# Add System
# ==========================================================

if add_system:

    df = st.session_state.existing_design_df

    existing_mask = df["Fire Safety System"] == system

    if existing_mask.any():
        df.loc[existing_mask, "Quantity"] += quantity
    else:
        new_row = pd.DataFrame(
            [
                {
                    "Fire Safety System": system,
                    "Quantity": quantity,
                }
            ]
        )

        df = pd.concat(
            [df, new_row],
            ignore_index=True,
        )

    st.session_state.existing_design_df = df

# ==========================================================
# Current Systems
# ==========================================================

st.divider()
st.subheader("Current Systems")

toggle_col, _ = st.columns([1, 5])

with toggle_col:
    st.session_state.use_manual_table = st.checkbox(
        "In use",
        value=st.session_state.use_manual_table,
        key="manual_table_toggle",
    )

table_key = (
    "manual_table_active"
    if st.session_state.use_manual_table
    else "manual_table_disabled"
)

with st.container(key=table_key):

    edited_df = st.data_editor(
        st.session_state.existing_design_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=not st.session_state.use_manual_table,
        column_config={
            "Fire Safety System": st.column_config.SelectboxColumn(
                "Fire Safety System",
                options=fire_systems,
                required=True,
            ),
            "Quantity": st.column_config.NumberColumn(
                "Quantity",
                min_value=1,
                step=1,
                required=True,
            ),
        },
        key="existing_design_editor",
    )

    st.session_state.existing_design_df = edited_df


st.divider()
st.subheader("Upload Existing Systems (CSV)")

toggle_col2, _ = st.columns([1, 5])

with toggle_col2:
    st.session_state.use_csv_upload = st.checkbox(
        "In use",
        value=st.session_state.use_csv_upload,
        key="csv_upload_toggle",
    )

csv_key = (
    "csv_upload_active"
    if st.session_state.use_csv_upload
    else "csv_upload_disabled"
)

with st.container(key=csv_key):

    upload_col, button_col = st.columns([4, 1])

    with upload_col:
        uploaded_file = st.file_uploader(
            "Upload CSV (columns: Apparatus, Quantity)",
            type=["csv"],
            disabled=not st.session_state.use_csv_upload,
            key="csv_uploader",
        )

    with button_col:
        st.write("")
        st.write("")
        preview_csv = st.button(
            "Preview CSV",
            use_container_width=True,
            disabled=not st.session_state.use_csv_upload,
        )

    if uploaded_file is not None:

        try:
            csv_df = pd.read_csv(uploaded_file)
            csv_df.columns = [c.strip() for c in csv_df.columns]

            rename_map = {}
            for col in csv_df.columns:
                if col.lower() in ("apparatus", "fire safety system", "system"):
                    rename_map[col] = "Fire Safety System"
                elif col.lower() in ("quantity", "qty"):
                    rename_map[col] = "Quantity"

            csv_df = csv_df.rename(columns=rename_map)

            if "Fire Safety System" not in csv_df.columns or "Quantity" not in csv_df.columns:
                st.error(
                    "CSV must contain an 'Apparatus' (or 'Fire Safety System') "
                    "column and a 'Quantity' column."
                )
            else:
                csv_df = csv_df[["Fire Safety System", "Quantity"]]

                csv_df = (
                    csv_df
                    .groupby("Fire Safety System", as_index=False)["Quantity"]
                    .sum()
                )

                st.session_state.csv_upload_df = csv_df

        except Exception as e:
            st.error(f"Could not read CSV file: {e}")

    if preview_csv:
        st.session_state.show_csv_preview = not st.session_state.show_csv_preview

    if st.session_state.show_csv_preview and not st.session_state.csv_upload_df.empty:
        st.dataframe(
            st.session_state.csv_upload_df,
            use_container_width=True,
            hide_index=True,
        )

# ==========================================================
# Calculate
# ==========================================================

# ==========================================================
# Calculate
# ==========================================================

st.divider()

calculate = st.button(
    "Calculate Embodied Carbon",
    use_container_width=True,
)

if calculate:

    sources = []

    if st.session_state.use_manual_table and not st.session_state.existing_design_df.empty:
        sources.append(st.session_state.existing_design_df)

    if st.session_state.use_csv_upload and not st.session_state.csv_upload_df.empty:
        sources.append(st.session_state.csv_upload_df)

    if not sources:
        st.warning(
            "No active data source contains any systems. Enable a source "
            "and add data before calculating."
        )
    else:
        combined_df = pd.concat(sources, ignore_index=True)

        grouped_df = (
            combined_df
            .groupby("Fire Safety System", as_index=False)["Quantity"]
            .sum()
        )

        apparatus_names = carbon_db["apparatus_output"]["Apparatus"]

        unmatched = grouped_df[
            ~grouped_df["Fire Safety System"].isin(apparatus_names)
        ]

        if not unmatched.empty:
            st.warning(
                "The following systems were not found in the Carbon Database "
                "and will be excluded from the results: "
                + ", ".join(unmatched["Fire Safety System"].tolist())
            )

        results_df = calculate_existing_design(
            grouped_df,
            carbon_db["apparatus_output"],
        )

        summary = summarise_results(results_df)

        st.session_state.existing_results_df = results_df
        st.session_state.existing_summary = summary

# ==========================================================
# Results
# ==========================================================

# ==========================================================
# Results
# ==========================================================

if not st.session_state.existing_results_df.empty:

    summary = st.session_state.existing_summary

    st.divider()

    st.subheader("Embodied Carbon Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "A1-A3",
        f"{summary['A1-A3']:,.2f} kgCO₂e",
    )

    col2.metric(
        "A4",
        f"{summary['A4']:,.2f} kgCO₂e",
    )

    col3.metric(
        "A5",
        f"{summary['A5']:,.2f} kgCO₂e",
    )

    col4.metric(
        "Total",
        f"{summary['Total']:,.2f} kgCO₂e",
    )

st.divider()

save_version = st.button(
    "💾 Save This Version",
    use_container_width=True,
)

if save_version:
    if not project_name:
        st.error("Please enter or select a project name before saving.")
    else:
        version_number = save_project_version(
            project_name=project_name,
            area=building_area,
            notes=assessment_notes,
            version_notes=version_notes,
            design_df=st.session_state.existing_design_df,
            results_df=st.session_state.existing_results_df,
            summary=st.session_state.existing_summary,
        )
        st.success(
            f"Saved as Version {version_number} of '{project_name}'."
        )

    st.divider()

    st.subheader("Calculation Results")

    st.dataframe(
        st.session_state.existing_results_df,
        use_container_width=True,
        hide_index=True,
    )

    # ==========================================================
    # Carbon Analysis Dashboard
    # ==========================================================

    st.divider()

    st.subheader("Carbon Analysis Dashboard")

    left, right = st.columns(2)

    with left:

        fig = create_apparatus_pie_chart(
            st.session_state.existing_results_df
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    with right:

        fig = create_lifecycle_bar_chart(
            st.session_state.existing_summary
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
            )

render_footer()