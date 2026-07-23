import streamlit as st
import pandas as pd

from utils.constants import (
    APP_NAME,
    APP_SUBTITLE,
    APP_STATUS,
    ARUP_RED,
    ARUP_DARK_RED,
    SOFT_RED,
    CHARCOAL,
    MID_GREY,
)
from utils.styles import apply_global_styles, render_header, render_footer
from utils.project_store import (
    get_project_names,
    get_project_versions,
    update_version_notes,
    delete_version,
    delete_project,
)
from utils.database_manager import (
    DATABASE_REGISTRY,
    ensure_defaults_seeded,
    validate_workbook,
    get_live_bytes,
    replace_live_database,
    revert_to_default,
)


st.set_page_config(
    page_title="Help",
    page_icon="❓",
    layout="wide",
)

apply_global_styles()

render_header(
    APP_NAME,
    APP_SUBTITLE,
    APP_STATUS,
)

# Safe to call every load - only copies live files to database/defaults/
# the first time, never overwrites an existing default copy.
ensure_defaults_seeded()


# ==========================================================
# CALCULATION METHODOLOGY
# ==========================================================

st.markdown("## Calculation Methodology")

st.markdown(
    """
The Fire Safety Embodied Carbon App estimates the upfront embodied carbon (A1–A5)
associated with fire safety systems in buildings.

The application integrates engineering databases, Australian Standards and
embodied carbon data to support sustainable fire safety design decision-making.
Carbon results are presented through intuitive tables, charts and engineering
summaries.
"""
)

st.divider()


# ==========================================================
# OVERALL WORKFLOW
# ==========================================================

st.markdown("## Overall Workflow")


def render_workflow():

    st.markdown(
        f"""
        <style>

        .workflow-row {{
            display: flex;
            gap: 16px;
        }}

        .workflow-rail {{
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 40px;
            flex-shrink: 0;
        }}

        .workflow-node {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background-color: {SOFT_RED};
            color: {ARUP_DARK_RED};
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 15px;
            flex-shrink: 0;
        }}

        .workflow-line {{
            width: 2px;
            flex: 1;
            background-color: {ARUP_RED};
            margin: 4px 0;
            min-height: 24px;
        }}

        .workflow-line-hidden {{
            visibility: hidden;
        }}

        .workflow-title {{
            font-size: 16px;
            font-weight: 700;
            color: {CHARCOAL};
            margin: 6px 0 4px 0;
        }}

        .workflow-description {{
            font-size: 14px;
            color: {MID_GREY};
            margin: 0 0 6px 0;
            line-height: 1.5;
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )

    workflow = [

        (
            "01 | Project & Building Setup",
            """
Enter project details and the NCC building classification required
for the assessment.
""",
        ),

        (
            "02 | System Identification",
            """
Fire safety measures are organised into ten categories reflecting the
fire safety engineering framework (Detection, Warning, Egress, First
Aid Fire-Fighting, Structural Fire Protection, Suppression, Smoke
Hazard Management, Fire Brigade Access, Fire Safety Management, and
Special Hazards).
""",
        ),

        (
            "03 | Compliance Pathway Selection",
            """
Each system is marked Not Applicable (N/A), Deemed-to-Satisfy (DtS),
or Manual Override.
""",
        ),

        (
            "04 | Quantity Determination",
            """
Quantities are derived from user input, standards-based rules (e.g.
detector/sprinkler spacing), or system-specific calculators.
""",
        ),

        (
            "05 | Product & Emission Factor Matching",
            """
Quantities are matched to product-level emission factors in the
Carbon Database, drawn from manufacturer EPDs where available,
Australian generic industry-average data where product-specific data
doesn't exist, and mass-based estimates where no other source is
available.
""",
        ),

        (
            "06 | Calculation & Reporting",
            """
Embodied carbon is calculated by lifecycle stage (A1–A3, A4, A5),
aggregated, and summarised through tables, charts and visualisations.
Assessments can be saved as versions for comparing design iterations.
""",
        ),
    ]

    for i, (title, description) in enumerate(workflow):

        is_last = i == len(workflow) - 1
        node_class = "workflow-node"
        line_class = "workflow-line workflow-line-hidden" if is_last else "workflow-line"
        description_html = description.strip().replace("\n", " ")

        st.markdown(
            f"""
            <div class="workflow-row">
                <div class="workflow-rail">
                    <div class="{node_class}">{i + 1}</div>
                    <div class="{line_class}"></div>
                </div>
                <div>
                    <div class="workflow-title">{title.split('| ')[-1]}</div>
                    <div class="workflow-description">{description_html}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


render_workflow()

st.divider()


# ==========================================================
# METHODOLOGY ASSUMPTIONS
# ==========================================================

st.markdown("## Methodology Assumptions")

st.markdown(
    """
- Scope limited to upfront embodied carbon (A1–A5).
- Lifecycle stages include A1–A3 (Product), A4 (Transport) and A5 (Construction & Installation).
- Engineering databases are editable to support future updates.
- Embodied carbon calculations are performed automatically using Python.
"""
)

st.divider()


# ==========================================================
# REFERENCES
# ==========================================================

st.markdown("## References")

st.markdown(
    """
- National Construction Code (NCC)

- Australian Standards

- National Material Emission Factors Database

- NSW Embodied Carbon Databook

- FireCarbonApp Engineering Databases
"""
)

st.divider()


# ==========================================================
# MANAGE VERSIONS
# ==========================================================

st.markdown("## Manage Versions")

st.markdown(
    """
Review and make simple edits to saved project versions — update
version notes, or remove a version that was saved by mistake.
"""
)

projects = get_project_names()

if not projects:
    st.info("No saved projects yet.")
else:
    selected_project = st.selectbox(
        "Select Project",
        projects,
        key="help_manage_versions_project",
    )

    versions = get_project_versions(selected_project)

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

    st.markdown(f"**{selected_project} — {len(versions)} version(s)**")

    for v in versions:

        design_df = pd.DataFrame(v["design"])
        summary = v["summary"]

        with st.expander(
            f"Version {v['version']} — {v['timestamp']}",
            expanded=False,
        ):

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("A1-A3", f"{summary.get('A1-A3', 0):,.2f} kgCO₂e")
            col2.metric("A4", f"{summary.get('A4', 0):,.2f} kgCO₂e")
            col3.metric("A5", f"{summary.get('A5', 0):,.2f} kgCO₂e")
            col4.metric("Total", f"{summary.get('Total', 0):,.2f} kgCO₂e")

            st.markdown("**Design Composition**")

            st.dataframe(
                design_df,
                width="stretch",
                hide_index=True,
            )

            st.markdown("**Version Notes**")

            edited_notes = st.text_area(
                "Edit notes for this version",
                value=v["version_notes"] or "",
                key=f"help_notes_{selected_project}_{v['version']}",
                label_visibility="collapsed",
            )

            button_col1, button_col2, _ = st.columns([1, 1, 4])

            with button_col1:
                save_notes = st.button(
                    "💾 Save Notes",
                    key=f"help_save_{selected_project}_{v['version']}",
                    width="stretch",
                )

            with button_col2:
                confirm_delete = st.checkbox(
                    "Confirm delete",
                    key=f"help_confirm_{selected_project}_{v['version']}",
                )

                delete_this_version = st.button(
                    "🗑️ Delete Version",
                    key=f"help_delete_{selected_project}_{v['version']}",
                    width="stretch",
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

st.divider()


# ==========================================================
# MANAGE DATABASE
# ==========================================================

st.markdown("## Manage Database")

st.markdown(
    """
Download the current version of any engineering database to edit it
offline, then upload it back to update the app. Uploaded files are
checked for the required sheets and columns before being accepted -
anything missing is rejected with a specific reason, so the app can't
be left in a broken state. If an update doesn't work out, revert to
the original default database at any time.
"""
)

for db_key, entry in DATABASE_REGISTRY.items():

    st.markdown(f"### {entry['label']}")

    live_bytes = get_live_bytes(db_key)

    dl_col, revert_col = st.columns([1, 1])

    with dl_col:
        if live_bytes is not None:
            st.download_button(
                label="⬇️ Download Current Database",
                data=live_bytes,
                file_name=entry["live_path"].name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"download_{db_key}",
                width="stretch",
            )
        else:
            st.warning("Current database file not found.")

    with revert_col:
        confirm_revert = st.checkbox(
            "Confirm revert",
            key=f"confirm_revert_{db_key}",
        )
        if st.button(
            "↩️ Revert to Default Database",
            key=f"revert_{db_key}",
            disabled=not confirm_revert,
            width="stretch",
        ):
            ok, message = revert_to_default(db_key)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    uploaded_file = st.file_uploader(
        "Upload replacement database",
        type=["xlsx", "xlsm", "xls"],
        key=f"upload_{db_key}",
    )

    if uploaded_file is not None:
        ok, message = validate_workbook(uploaded_file, db_key)

        if ok:
            st.success("Validation passed - required sheets and columns are all present.")

            if st.button(
                "Confirm Import",
                key=f"confirm_import_{db_key}",
            ):
                uploaded_file.seek(0)
                ok, message = replace_live_database(db_key, uploaded_file)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        else:
            st.error(f"Validation failed: {message}")

    st.divider()

render_footer()