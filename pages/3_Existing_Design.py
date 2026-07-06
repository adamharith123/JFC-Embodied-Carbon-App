import streamlit as st
import pandas as pd

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import (
    apply_global_styles,
    render_header,
    render_footer,
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

    new_row = pd.DataFrame(
        [
            {
                "Fire Safety System": system,
                "Quantity": quantity,
            }
        ]
    )

    st.session_state.existing_design_df = pd.concat(
        [
            st.session_state.existing_design_df,
            new_row,
        ],
        ignore_index=True,
    )

# ==========================================================
# Current Systems
# ==========================================================

st.divider()

st.subheader("Current Systems")

st.dataframe(
    st.session_state.existing_design_df,
    use_container_width=True,
    hide_index=True,
)

# ==========================================================
# Calculate
# ==========================================================

st.divider()

calculate = st.button(
    "Calculate Embodied Carbon",
    use_container_width=True,
)

if calculate:

    results_df = calculate_existing_design(
        st.session_state.existing_design_df,
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