import streamlit as st
import pandas as pd

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer
from utils.project_store import (
    get_project_names,
    get_project_versions,
    update_version_notes,
    delete_version,
    delete_project,
)

st.set_page_config(page_title="Manage Version History", page_icon="🛠️", layout="wide")

apply_global_styles()

render_header("Manage Version History", APP_SUBTITLE, APP_STATUS)

st.markdown(
    """
Review and make simple edits to saved project versions — update version
notes, or remove a version that was saved by mistake.
"""
)

st.divider()

projects = get_project_names()

if not projects:
    st.info("No saved projects yet.")
    st.stop()

selected_project = st.selectbox("Select Project", projects)

versions = get_project_versions(selected_project)

st.divider()

with st.expander("⚠️ Delete Entire Project", expanded=False):

    st.warning(
        f"This will permanently delete **{selected_project}** and "
        f"all {len(versions)} saved version(s). This cannot be undone."
    )

    confirm_project_delete = st.checkbox(
        f"Yes, I want to permanently delete '{selected_project}'",
        key=f"confirm_delete_project_{selected_project}",
    )

    delete_project_button = st.button(
        "🗑️ Delete Project Permanently",
        disabled=not confirm_project_delete,
        key=f"delete_project_{selected_project}",
    )

    if delete_project_button:
        delete_project(selected_project)
        st.success(f"Project '{selected_project}' has been deleted.")
        st.rerun()

st.subheader(f"{selected_project} — {len(versions)} version(s)")

for v in versions:

    design_df = pd.DataFrame(v["design"])
    summary = v["summary"]

    with st.expander(
        f"Version {v['version']} — {v['timestamp']}",
        expanded=False,
    ):

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("A1-A3", f"{summary['A1-A3']:,.2f} kgCO₂e")
        col2.metric("A4", f"{summary['A4']:,.2f} kgCO₂e")
        col3.metric("A5", f"{summary['A5']:,.2f} kgCO₂e")
        col4.metric("Total", f"{summary['Total']:,.2f} kgCO₂e")

        st.markdown("**Design Composition**")

        st.dataframe(
            design_df,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**Version Notes**")

        edited_notes = st.text_area(
            "Edit notes for this version",
            value=v["version_notes"] or "",
            key=f"notes_{selected_project}_{v['version']}",
            label_visibility="collapsed",
        )

        button_col1, button_col2, _ = st.columns([1, 1, 4])

        with button_col1:
            save_notes = st.button(
                "💾 Save Notes",
                key=f"save_{selected_project}_{v['version']}",
                use_container_width=True,
            )

        with button_col2:
            confirm_delete = st.checkbox(
                "Confirm delete",
                key=f"confirm_{selected_project}_{v['version']}",
            )

            delete_this_version = st.button(
                "🗑️ Delete Version",
                key=f"delete_{selected_project}_{v['version']}",
                use_container_width=True,
                disabled=not confirm_delete,
            )

        if save_notes:
            update_version_notes(
                selected_project,
                v["version"],
                edited_notes,
            )
            st.success(f"Version {v['version']} notes updated.")
            st.rerun()

        if delete_this_version:
            delete_version(
                selected_project,
                v["version"],
            )
            st.success(f"Version {v['version']} deleted.")
            st.rerun()

render_footer()