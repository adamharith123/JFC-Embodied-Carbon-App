import streamlit as st
import pandas as pd

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer
from utils.project_store import get_project_names, get_project_versions
from utils.charts import create_apparatus_pie_chart, create_lifecycle_bar_chart

st.set_page_config(page_title="Version History", page_icon="🕒", layout="wide")

apply_global_styles()

render_header("Version History", APP_SUBTITLE, APP_STATUS)

st.page_link(
    "pages/5_Manage_Version_History.py",
    label="🛠️ Manage Version History",
    icon=None,
)

st.markdown(
    """
Browse past design iterations for any project and see how different
fire safety system configurations affect embodied carbon.
"""
)

st.divider()

projects = get_project_names()

if not projects:
    st.info("No saved projects yet. Save a version from the Existing Design page first.")
    st.stop()

col1, col2 = st.columns(2)

with col1:
    selected_project = st.selectbox("Select Project", projects)

versions = get_project_versions(selected_project)

version_labels = [
    f"Version {v['version']} — {v['timestamp']}" for v in versions
]

with col2:
    selected_label = st.selectbox("Select Version", version_labels)

selected_version = versions[version_labels.index(selected_label)]

st.divider()

st.subheader(f"{selected_project} — Version {selected_version['version']}")

if selected_version.get("version_notes"):
    st.markdown(f"**Version Notes:** {selected_version['version_notes']}")

summary = selected_version["summary"]

col1, col2, col3, col4 = st.columns(4)

col1.metric("A1-A3", f"{summary['A1-A3']:,.2f} kgCO₂e")
col2.metric("A4", f"{summary['A4']:,.2f} kgCO₂e")
col3.metric("A5", f"{summary['A5']:,.2f} kgCO₂e")
col4.metric("Total", f"{summary['Total']:,.2f} kgCO₂e")

st.divider()

st.subheader("Design Composition")

design_df = pd.DataFrame(selected_version["design"])
results_df = pd.DataFrame(selected_version["results"])

st.dataframe(design_df, width='stretch', hide_index=True)

st.divider()

st.subheader("Carbon Analysis Dashboard")

left, right = st.columns(2)

with left:
    fig = create_apparatus_pie_chart(results_df)
    if fig is not None:
        st.plotly_chart(fig, width='stretch')

with right:
    fig = create_lifecycle_bar_chart(summary)
    if fig is not None:
        st.plotly_chart(fig, width='stretch')

render_footer()