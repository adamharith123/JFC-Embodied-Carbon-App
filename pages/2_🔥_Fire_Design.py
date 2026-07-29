import streamlit as st
import pandas as pd
import copy
import math
import json

from utils.constants import APP_NAME,APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer
from utils.project_store import (
    get_project_names,
    get_project_meta,
    get_project_versions,
    reserve_next_version,
    finalize_version,
    update_existing_version,
    delete_version,
    export_version,
    import_version,
)
from utils.database_loader import (
    load_carbon_database,
    get_building_classes,
    get_building_class_applicability,
)
from utils.calculations import summarise_results
from utils.charts import create_apparatus_pie_chart, create_lifecycle_bar_chart
from utils.proposed_design_calculations import (
    calculate_component_carbon,
    find_product_carbon_factors_row,
    get_available_product_types,
)
from utils.standards_engine import (
    get_frl_reference,
)
from utils.component_groups import (
    component_spec,
    init_group_state,
    init_component_state,
    render_component,
    render_component_group,
    render_single_component,
    calculate_component,
    calculate_component_group,
    component_group_design_rows,
    KIND_INPUT,
    KIND_LINKED_CHILD,
    KIND_CROSS_CATEGORY_COUNTER,
)
from utils.ui_structure_loader import load_ui_structure
from utils.report_generator import generate_fire_design_report
# ==========================================================
# Page Configuration
# ==========================================================

st.set_page_config(
    page_title="Fire Design",
    page_icon="🔥",
    layout="wide",
)

apply_global_styles()

st.markdown(
    """
    <style>
    [class*="st-key-cat_nav_na_"] button {
        background-color: #9E9E9E !important;
        color: white !important;
        border: none !important;
    }
    [class*="st-key-cat_nav_dts_"] button {
        background-color: #2E7D32 !important;
        color: white !important;
        border: none !important;
    }
    [class*="st-key-cat_nav_pbd_"] button {
        background-color: #C62828 !important;
        color: white !important;
        border: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_header(APP_NAME, APP_SUBTITLE, APP_STATUS)

# ==========================================================
# Category / Subcategory Taxonomy
# ==========================================================
# This is the single hand-maintained source of truth for the app's
# structure. Apparatus names here are best-guess and MUST be checked
# against the actual Carbon Database - rename freely, this is the
# only place that needs updating.

# ==========================================================
# Spreadsheet-Driven Structure
# ==========================================================
# Everything is declared in the "ui_structure" sheet and loaded here
# - adding, removing, or renaming an apparatus means editing a row in
# that sheet, not this file. Extinguishers (Category 4) used to be a
# bespoke hand-built exception (an AS 2444 minimum-rating form with
# its own hazard/suppression/rating logic) - it's now driven entirely
# by ui_structure + the Condition sheet's 3-key lookup, same as every
# other apparatus.

_ui = load_ui_structure()

CATEGORY_NAMES = dict(_ui["category_names"])

CATEGORY_SUBCATEGORIES = {cat_num: list(subs) for cat_num, subs in _ui["category_subcategories"].items()}

for _cat_num in range(1, 11):
    CATEGORY_NAMES.setdefault(_cat_num, f"Category {_cat_num}")
    CATEGORY_SUBCATEGORIES.setdefault(_cat_num, [])

CATEGORY_APPARATUS_MAP = dict(_ui["apparatus_map"])

GROUP_DEFINITIONS = dict(_ui["group_definitions"])

SINGLE_COMPONENT_DEFINITIONS = dict(_ui["single_component_definitions"])

SUBCATEGORY_KIND = dict(_ui["subcategory_kind"])


def get_apparatus_name(cat_num, sub_name):
    return CATEGORY_APPARATUS_MAP.get((cat_num, sub_name))


def get_subcategory_kind(cat_num, sub_name):
    return SUBCATEGORY_KIND.get((cat_num, sub_name), "simple")


def blank_subcategory_state(cat_num, sub_name):

    kind = get_subcategory_kind(cat_num, sub_name)

    if kind == "component_group":
        return init_group_state(GROUP_DEFINITIONS[(cat_num, sub_name)])

    if kind == "single_component":
        spec = SINGLE_COMPONENT_DEFINITIONS[(cat_num, sub_name)]
        return {"expanded": False, "component": init_component_state(spec)}

    # "unavailable" (or any unrecognized kind) - minimal defensive fallback
    return {"status": "N/A", "expanded": False}


def fresh_categories():
    return {
        cat_num: {
            "subcategories": {
                sub_name: blank_subcategory_state(cat_num, sub_name)
                for sub_name in CATEGORY_SUBCATEGORIES[cat_num]
            }
        }
        for cat_num in CATEGORY_NAMES
    }


def get_subcategory_color_status(cat_num, sub_name, sub_state):
    kind = get_subcategory_kind(cat_num, sub_name)
    if kind == "component_group":
        member_statuses = [
            comp.get("status", "PBD" if (comp.get("value") or comp.get("included")) else "N/A")
            for comp in sub_state.get("components", {}).values()
        ]
        if "PBD" in member_statuses:
            return "PBD"
        if "DTS" in member_statuses:
            return "DTS"
        return "N/A"
    if kind == "single_component":
        return sub_state.get("component", {}).get("status", "N/A")
    return "N/A"


def load_categories_from_design_rows(design_rows):
    """
    Reconstructs the test_categories structure from a previously
    saved version's design data, so an existing version can be
    reopened for editing exactly as it was left.

    Neither current archetype (component_group, single_component) has
    a state shape that's fully reconstructable from the flat
    design-row format used for saving, so every subcategory is reset
    to a fresh blank state rather than risk building a malformed one.
    Restoring exact prior inputs on "Edit Version" is a known
    limitation - the saved Results/Summary are still shown
    read-only regardless.
    """

    return fresh_categories()


def version_summary_label(v):
    first_line = (v["version_notes"] or "").strip().splitlines()
    note_preview = first_line[0][:60] if first_line else "No notes"
    status_tag = " (Draft — incomplete)" if v["status"] == "draft" else ""
    return f"Version {v['version']} — {note_preview}{status_tag}"


# Maps the keys used in a version's saved "building_inputs" dict to the
# Streamlit widget keys of the "Additional Building Inputs" fields, so
# a saved version's figures can be used to pre-fill those widgets.
BUILDING_INPUT_WIDGET_KEYS = {
    "floor_area_per_storey": "test_floor_area_per_storey",
    "building_storeys": "test_building_storeys",
    "building_effective_height": "test_building_effective_height",
    "building_floor_to_floor_height": "test_building_ftf_height",
    "building_fire_stairs": "test_building_fire_stairs",
    "building_rooms": "test_building_rooms",
    "building_exits_per_storey": "test_building_exits_per_storey",
    "fire_hazard": "test_fire_hazard",
}


def prefill_building_input_widgets(saved_inputs, building_classes):
    """
    Sets the Additional Building Inputs widget session-state keys from
    a previously saved building_inputs dict, so the widgets render
    with those values already filled in. A key is only set when a
    saved value actually exists - an unset key just lets the widget
    fall back to its own default, which matters for versions saved
    before building_inputs was tracked.
    """

    for info_key, widget_key in BUILDING_INPUT_WIDGET_KEYS.items():
        if saved_inputs.get(info_key) is not None:
            st.session_state[widget_key] = saved_inputs[info_key]

    saved_building_class = saved_inputs.get("building_class")

    if saved_building_class and saved_building_class in building_classes:
        st.session_state["test_building_class"] = saved_building_class


def extract_building_inputs(info):
    """
    Pulls the "Additional Building Inputs" + Building Classification
    fields out of a test_project_info dict, for saving alongside a
    version (see project_store.reserve_next_version / finalize_version
    / update_existing_version). Excludes project-level fields
    (project_name, assessment_notes, etc.) that are already stored
    elsewhere.
    """

    keys = list(BUILDING_INPUT_WIDGET_KEYS.keys()) + ["building_class"]
    return {key: info.get(key) for key in keys}


# ==========================================================
# Session State
# ==========================================================

if "test_step" not in st.session_state:
    st.session_state.test_step = 1

if "test_project_info" not in st.session_state:
    st.session_state.test_project_info = {}

if "test_categories" not in st.session_state:
    st.session_state.test_categories = fresh_categories()

if "test_selected_category" not in st.session_state:
    st.session_state.test_selected_category = 1

if "test_results_df" not in st.session_state:
    st.session_state.test_results_df = pd.DataFrame()

if "test_summary" not in st.session_state:
    st.session_state.test_summary = {}

if "test_dirty" not in st.session_state:
    st.session_state.test_dirty = False

if "test_last_saved_snapshot" not in st.session_state:
    st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)

if "test_show_unsaved_dialog" not in st.session_state:
    st.session_state.test_show_unsaved_dialog = False

if "test_editing_mode" not in st.session_state:
    st.session_state.test_editing_mode = None

if "test_editing_version_number" not in st.session_state:
    st.session_state.test_editing_version_number = None

if "test_is_new_unsaved_draft" not in st.session_state:
    st.session_state.test_is_new_unsaved_draft = False

carbon_db = load_carbon_database()
frl_reference_df = get_frl_reference()

# ==========================================================
# STEP 1: Project Information
# ==========================================================

if st.session_state.test_step == 1:

    st.markdown(
        """
    Set up the proposed design assessment by entering building details below,
    then proceed to select and configure fire safety systems.
    """
    )

    st.divider()

    st.subheader("Project Information")

    project_mode = st.radio(
        "Project Type",
        ["New Project", "Existing Project"],
        horizontal=True,
        key="test_project_mode",
    )

    with st.expander("📥 Import Project / Version"):

        st.caption(
            "Import a version exported from this app (via **Export Version**, below). "
            "It's added as a new version - it never overwrites anything already saved."
        )

        uploaded_export = st.file_uploader(
            "Export file", type=["json"], key="test_import_uploader",
        )

        import_target_name = st.text_input(
            "Import into project name (leave blank to use the file's original project name)",
            key="test_import_target_name",
        )

        if st.button("Import", key="test_import_button", disabled=uploaded_export is None):
            try:
                payload = json.loads(uploaded_export.read().decode("utf-8"))
                imported_project, imported_version = import_version(
                    payload, target_project_name=import_target_name.strip() or None,
                )
                st.success(f"Imported as **{imported_project}**, version {imported_version}.")
                st.rerun()
            except (ValueError, json.JSONDecodeError) as e:
                st.error(f"Couldn't import this file: {e}")


    show_next_button = True
    selected_existing_version = None

    if project_mode == "New Project":

        project_name = st.text_input(
            "Project Name",
            placeholder="Example: ABC Office Fitout",
            key="test_project_name_new",
        )

        assessment_notes = st.text_area(
            "Assessment Notes",
            placeholder="Optional project notes...",
            key="test_assessment_notes_new",
        )

    else:

        existing_projects = get_project_names()

        if not existing_projects:
            st.info("No existing projects found yet. Create a New Project first.")
            st.stop()

        project_name = st.selectbox(
            "Select Project",
            existing_projects,
            key="test_project_name_existing",
        )

        project_meta = get_project_meta(project_name)

        # Building Area is no longer a direct input - it's derived from
        # Floor Area per Storey x Number of Storeys further down. This
        # fallback is only used to seed session state when re-opening a
        # locked version for editing (see "Edit Version" below), before
        # the user re-enters storey figures.
        existing_project_area = float(project_meta["area"]) if project_meta and project_meta["area"] else 0.0

        assessment_notes = st.text_area(
            "Assessment Notes",
            value=project_meta["notes"] if project_meta else "",
            key="test_assessment_notes_existing",
        )

        versions = get_project_versions(project_name)

        version_options = ["+ New Version"] + [version_summary_label(v) for v in versions]

        selected_version_label = st.selectbox(
            "Select Version",
            version_options,
            key="test_version_choice",
        )

        if selected_version_label == "+ New Version" and versions:

            # Starting a fresh version - pre-fill the Additional
            # Building Inputs from the most recent saved version as a
            # starting point, so the user isn't re-typing the same
            # storey figures every version. Guarded by a marker so
            # this only runs once per project selection - otherwise
            # it would overwrite the user's own edits on every rerun
            # (e.g. typing in Assessment Notes) while this project
            # stays selected.
            prefill_marker_key = "test_new_version_prefill_project"

            if st.session_state.get(prefill_marker_key) != project_name:
                prefill_building_input_widgets(versions[0].get("building_inputs") or {}, get_building_classes())
                st.session_state[prefill_marker_key] = project_name

        if selected_version_label != "+ New Version":

            selected_index = version_options.index(selected_version_label) - 1
            selected_existing_version = versions[selected_index]

            show_next_button = False

            st.divider()

            st.info("🔒 This version is locked. Click **Edit Version** below to make changes.")

            summary = selected_existing_version["summary"]

            if summary:
                col1, col2 = st.columns(2)

                col1.metric("A1-A3", f"{summary['A1-A3']:,.2f} kgCO₂e")
                col2.metric("A4", f"{summary['A4']:,.2f} kgCO₂e")

                col3, col4 = st.columns(2)

                col3.metric("A5", f"{summary['A5']:,.2f} kgCO₂e")
                col4.metric("Total", f"{summary['Total']:,.2f} kgCO₂e")

            if selected_existing_version["version_notes"]:
                st.markdown("**Version Notes**")
                st.text(selected_existing_version["version_notes"])

            design_rows = selected_existing_version["design"]

            if design_rows:
                st.markdown("**Design Composition**")
                st.dataframe(
                    pd.DataFrame(design_rows),
                    width='stretch',
                    hide_index=True,
                )

            edit_col, export_col = st.columns(2)

            with edit_col:
                edit_version_clicked = st.button(
                    "✏️ Edit Version",
                    width='stretch',
                )

            with export_col:
                export_payload = export_version(project_name, selected_existing_version["version"])
                st.download_button(
                    "⬇️ Export Version",
                    data=json.dumps(export_payload, indent=2),
                    file_name=f"{project_name}_v{selected_existing_version['version']}.json",
                    mime="application/json",
                    width='stretch',
                )

            if edit_version_clicked:

                building_classes = get_building_classes()

                saved_inputs = selected_existing_version.get("building_inputs") or {}

                # Pre-fill the Additional Building Inputs widgets with
                # what was saved for this version, so "Back to Project
                # Information" shows real figures instead of blanks.
                prefill_building_input_widgets(saved_inputs, building_classes)

                saved_building_class = saved_inputs.get("building_class")
                building_class_valid = saved_building_class and saved_building_class in building_classes

                saved_floor_area = saved_inputs.get("floor_area_per_storey")
                saved_storeys = saved_inputs.get("building_storeys")

                if saved_floor_area is not None and saved_storeys is not None:
                    building_area_for_edit = saved_floor_area * saved_storeys
                else:
                    building_area_for_edit = existing_project_area

                st.session_state.test_project_info = {
                    "project_mode": project_mode,
                    "project_name": project_name,
                    "building_area": building_area_for_edit,
                    "assessment_notes": assessment_notes,
                    "building_class": saved_building_class if building_class_valid else (building_classes[0] if building_classes else ""),
                    "version_notes": selected_existing_version["version_notes"] or "",
                    "floor_area_per_storey": saved_floor_area,
                    "building_storeys": saved_storeys,
                    "building_effective_height": saved_inputs.get("building_effective_height"),
                    "building_floor_to_floor_height": saved_inputs.get("building_floor_to_floor_height"),
                    "building_fire_stairs": saved_inputs.get("building_fire_stairs"),
                    "building_rooms": saved_inputs.get("building_rooms"),
                    "building_exits_per_storey": saved_inputs.get("building_exits_per_storey"),
                    "fire_hazard": saved_inputs.get("fire_hazard") or saved_inputs.get("sprinkler_hazard_classification"),
                }

                st.session_state.test_categories = load_categories_from_design_rows(design_rows)
                st.session_state.test_results_df = pd.DataFrame(selected_existing_version["results"])
                st.session_state.test_summary = selected_existing_version["summary"]

                st.session_state.test_editing_mode = "edit"
                st.session_state.test_editing_version_number = selected_existing_version["version"]
                st.session_state.test_is_new_unsaved_draft = False

                st.session_state.test_dirty = False
                st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)

                st.session_state.test_step = 2
                st.rerun()

    if show_next_button:

        building_classes = get_building_classes()

        building_class = st.selectbox(
            "Building Classification (NCC)",
            building_classes if building_classes else ["No building classes found"],
            key="test_building_class",
        )

        with st.expander(
            "Additional Building Inputs (from User Input List)",
            expanded=True,
        ):

            row1_col1, row1_col2, row1_col3 = st.columns(3)

            with row1_col1:
                floor_area_per_storey = st.number_input(
                    "Floor Area per Storey (m²)",
                    min_value=0.0,
                    step=1.0,
                    key="test_floor_area_per_storey",
                )

            with row1_col2:
                building_storeys = st.number_input(
                    "Number of Storeys",
                    min_value=0,
                    step=1,
                    key="test_building_storeys",
                )

            with row1_col3:
                building_effective_height = st.number_input(
                    "Effective Height (m)",
                    min_value=0.0,
                    step=0.1,
                    key="test_building_effective_height",
                )

            building_area = floor_area_per_storey * building_storeys

            row2_col1, row2_col2, row2_col3 = st.columns(3)

            with row2_col1:
                building_floor_to_floor_height = st.number_input(
                    "Floor-to-Floor Height (m)",
                    min_value=0.0,
                    step=0.1,
                    key="test_building_ftf_height",
                )

            with row2_col2:
                building_fire_stairs = st.number_input(
                    "Number of Fire Stairs per Storey",
                    min_value=0,
                    step=1,
                    key="test_building_fire_stairs",
                )

            with row2_col3:
                building_rooms = st.number_input(
                    "Number of Rooms",
                    min_value=0,
                    step=1,
                    key="test_building_rooms",
                )

            row3_col1, row3_col2 = st.columns(2)

            with row3_col1:
                building_exits_per_storey = st.number_input(
                    "Number of Exits per Storey",
                    min_value=0,
                    step=1,
                    key="test_building_exits_per_storey",
                )

            with row3_col2:
                fire_hazard = st.selectbox(
                    "Fire Hazard",
                    [
                        "Light Hazard",
                        "Ordinary Hazard",
                        "High Hazard",
                        "User-defined",
                    ],
                    index=2,
                    key="test_fire_hazard",
                )


        version_notes = st.text_area(
            "Version Notes",
            placeholder="Describe what changed in this design iteration...",
            key=f"test_version_notes_{project_mode}_{project_name}",
        )

        st.divider()

        next_step = st.button(
            "Next: Configure Fire Safety Systems →",
            width='stretch',
        )

        if next_step:

            if not project_name:
                st.error("Please enter or select a project name before continuing.")
            else:
                new_project_info = {
                    "project_mode": project_mode,
                    "project_name": project_name,
                    "building_area": building_area,
                    "assessment_notes": assessment_notes,
                    "building_class": building_class,
                    "version_notes": version_notes,
                    "floor_area_per_storey": floor_area_per_storey,
                    "building_storeys": building_storeys,
                    "building_effective_height": building_effective_height,
                    "building_floor_to_floor_height": building_floor_to_floor_height,
                    "building_fire_stairs": building_fire_stairs,
                    "building_rooms": building_rooms,
                    "building_exits_per_storey": building_exits_per_storey,
                    "fire_hazard": fire_hazard,
                }

                reserved_version = reserve_next_version(
                    project_name, building_area, assessment_notes,
                    building_inputs=extract_building_inputs(new_project_info),
                )

                st.session_state.test_project_info = new_project_info

                st.session_state.test_categories = fresh_categories()
                st.session_state.test_results_df = pd.DataFrame()
                st.session_state.test_summary = {}

                st.session_state.test_editing_mode = "new"
                st.session_state.test_editing_version_number = reserved_version
                st.session_state.test_is_new_unsaved_draft = True

                st.session_state.test_step = 2
                st.session_state.test_dirty = False
                st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)
                st.rerun()

    render_footer()

# ==========================================================
# STEP 2: Fire Safety System Configuration
# ==========================================================

else:

    info = st.session_state.test_project_info

    # ==========================================================
    # Calculation Logic
    # ==========================================================

    def run_calculation():

        apparatus_output_df = carbon_db["apparatus_output"]
        building_area_m2 = info.get("building_area", 0)

        results = []
        warnings = []

        for cat_num, sub_names in CATEGORY_SUBCATEGORIES.items():
            for sub_name in sub_names:

                kind = get_subcategory_kind(cat_num, sub_name)
                sub_state = st.session_state.test_categories[cat_num]["subcategories"][sub_name]
                apparatus_name = get_apparatus_name(cat_num, sub_name)

                if kind == "component_group":

                    specs = GROUP_DEFINITIONS[(cat_num, sub_name)]

                    group_results = calculate_component_group(
                        specs, sub_state, apparatus_output_df,
                        project_info=info, results_so_far=results, warnings=warnings,
                        frl_reference_df=frl_reference_df,
                    )

                    results.extend(group_results)

                elif kind == "single_component":

                    spec = SINGLE_COMPONENT_DEFINITIONS[(cat_num, sub_name)]

                    new_results = calculate_component(
                        spec, sub_state["component"], apparatus_output_df,
                        project_info=info, results_so_far=results, warnings=warnings,
                        frl_reference_df=frl_reference_df,
                    )

                    results.extend(new_results)

                # ------------------------------------------------
                # "not_implemented" kind - skipped silently
                # ------------------------------------------------
                else:
                    continue

        for w in warnings:
            st.warning(w)

        results_df = pd.DataFrame(results)
        summary = summarise_results(results_df)

        st.session_state.test_results_df = results_df
        st.session_state.test_summary = summary

        return not results_df.empty


    def build_design_dataframe():

        rows = []

        for cat_num, cat_name in CATEGORY_NAMES.items():
            for sub_name in CATEGORY_SUBCATEGORIES[cat_num]:

                kind = get_subcategory_kind(cat_num, sub_name)
                sub_state = st.session_state.test_categories[cat_num]["subcategories"][sub_name]

                if kind == "component_group":

                    specs = GROUP_DEFINITIONS[(cat_num, sub_name)]
                    rows.extend(component_group_design_rows(cat_name, specs, sub_state))

                elif kind == "single_component":

                    spec = SINGLE_COMPONENT_DEFINITIONS[(cat_num, sub_name)]
                    fake_group_state = {"components": {spec["key"]: sub_state["component"]}}
                    rows.extend(component_group_design_rows(cat_name, [spec], fake_group_state))

                else:
                    # "unavailable" (or any unrecognized kind) - nothing to record
                    rows.append({
                        "Category": cat_name, "Subcategory": sub_name, "Status": "N/A",
                        "Determination Type": None, "Value": None,
                        "Product Type": None, "Hazard Rating": None,
                    })

        return pd.DataFrame(rows)


    def perform_save():

        project_name = info.get("project_name")
        version_number = st.session_state.test_editing_version_number

        run_calculation()

        if st.session_state.test_editing_mode == "edit":
            update_existing_version(
                project_name=project_name, version_number=version_number,
                area=info.get("building_area"), notes=info.get("assessment_notes"),
                version_notes=info.get("version_notes"),
                design_df=build_design_dataframe(),
                results_df=st.session_state.test_results_df,
                summary=st.session_state.test_summary,
                building_inputs=extract_building_inputs(info),
            )
        else:
            finalize_version(
                project_name=project_name, version_number=version_number,
                area=info.get("building_area"), notes=info.get("assessment_notes"),
                version_notes=info.get("version_notes"),
                design_df=build_design_dataframe(),
                results_df=st.session_state.test_results_df,
                summary=st.session_state.test_summary,
                building_inputs=extract_building_inputs(info),
            )
            st.session_state.test_is_new_unsaved_draft = False

        st.session_state.test_dirty = False
        st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)

        return version_number


    def discard_changes():
        st.session_state.test_categories = copy.deepcopy(st.session_state.test_last_saved_snapshot)
        st.session_state.test_dirty = False

        if st.session_state.test_editing_mode == "new" and st.session_state.test_is_new_unsaved_draft:
            delete_version(info["project_name"], st.session_state.test_editing_version_number)


    # ==========================================================
    # Unsaved Changes Dialog
    # ==========================================================

    @st.dialog("Unsaved Changes")
    def unsaved_changes_dialog():

        st.write("You have unsaved changes to this design. Save them before leaving, or discard them?")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("💾 Save", width='stretch'):
                if not info.get("project_name"):
                    st.error("Please enter or select a project name before saving.")
                else:
                    perform_save()
                    st.session_state.test_show_unsaved_dialog = False
                    st.session_state.test_step = 1
                    st.rerun()

        with col2:
            if st.button("🗑️ Discard", width='stretch'):
                discard_changes()
                st.session_state.test_show_unsaved_dialog = False
                st.session_state.test_step = 1
                st.rerun()

        with col3:
            if st.button("Cancel", width='stretch'):
                st.session_state.test_show_unsaved_dialog = False
                st.rerun()


    if st.session_state.test_show_unsaved_dialog:
        unsaved_changes_dialog()

    # ==========================================================
    # Header / Back Button
    # ==========================================================

    editing_tag = " (editing)" if st.session_state.test_editing_mode == "edit" else ""

    st.caption(
        f"**{info['project_name']}** · Version {st.session_state.test_editing_version_number}{editing_tag} · "
        f"{info['building_area']:,.0f} m² · {info['building_class']}"
    )

    applicability = get_building_class_applicability(info.get("building_class"))

    if applicability:
        with st.expander("ℹ️ NCC Building Class Applicability"):
            for system_name, requirement in applicability.items():
                st.caption(f"**{system_name}**: {requirement}")

    back = st.button("← Back to Project Information")

    if back:
        if st.session_state.test_dirty:
            st.session_state.test_show_unsaved_dialog = True
            st.rerun()
        else:
            if st.session_state.test_editing_mode == "new" and st.session_state.test_is_new_unsaved_draft:
                delete_version(info["project_name"], st.session_state.test_editing_version_number)
            st.session_state.test_step = 1
            st.rerun()

    st.divider()

    nav_col, body_col = st.columns([1, 3])

    # ------------------------------------------------------
    # Left: Category Navigation
    # ------------------------------------------------------

    def get_category_status_word(cat_num):
        subs = st.session_state.test_categories[cat_num]["subcategories"]
        if not subs:
            return "na"
        statuses = [
            get_subcategory_color_status(cat_num, sub_name, sub_state)
            for sub_name, sub_state in subs.items()
        ]
        if "PBD" in statuses:
            return "pbd"
        if "DTS" in statuses:
            return "dts"
        return "na"

    with nav_col:

        st.markdown("**Fire Safety Systems**")

        for i in range(1, 11):

            status_word = get_category_status_word(i)

            label = f"{i}. {CATEGORY_NAMES[i]}"
            if i == st.session_state.test_selected_category:
                label = f"▶ {label}"

            with st.container(key=f"cat_nav_{status_word}_{i}"):
                clicked = st.button(label, key=f"cat_nav_button_{i}", width='stretch')

            if clicked:
                st.session_state.test_selected_category = i
                st.rerun()

    # ------------------------------------------------------
    # Right: Category Detail Body
    # ------------------------------------------------------

    with body_col:

        selected = st.session_state.test_selected_category
        subcats = CATEGORY_SUBCATEGORIES[selected]

        st.markdown(f"### {CATEGORY_NAMES[selected]}")

        for sub_name in subcats:

            kind = get_subcategory_kind(selected, sub_name)
            sub_state = st.session_state.test_categories[selected]["subcategories"][sub_name]
            apparatus_name = get_apparatus_name(selected, sub_name)

            st.divider()

            if kind == "unavailable":

                st.markdown(f"**{sub_name}**")
                st.info("This is not available.")
                continue

            if kind == "component_group":

                specs = GROUP_DEFINITIONS[(selected, sub_name)]

                result = render_component_group(
                    sub_name, specs, sub_state, carbon_db.get("apparatus_output"),
                    key_prefix=f"group_{selected}_{sub_name}",
                    results_so_far=st.session_state.test_results_df.to_dict("records") if not st.session_state.test_results_df.empty else [],
                    project_info=info,
                    frl_reference_df=frl_reference_df,
                    )

                if result == "toggled":
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()
                elif result:
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.session_state.test_dirty = True

                continue

            if kind == "single_component":

                spec = SINGLE_COMPONENT_DEFINITIONS[(selected, sub_name)]

                result = render_single_component(
                    spec, sub_state, carbon_db.get("apparatus_output"),
                    key_prefix=f"single_{selected}_{sub_name}",
                    results_so_far=st.session_state.test_results_df.to_dict("records") if not st.session_state.test_results_df.empty else [],
                    project_info=info,
                    frl_reference_df=frl_reference_df,
                )

                if result == "toggled":
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()
                elif result:
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.session_state.test_dirty = True

                continue

            # Defensive fallback - should be unreachable since every
            # subcategory in CATEGORY_SUBCATEGORIES now comes from a
            # recognized archetype in the ui_structure sheet.
            st.markdown(f"**{sub_name}**")
            st.warning(f"Unrecognized configuration kind '{kind}' for this subcategory.")

    # ==========================================================
    # Calculate / Save / Results
    # ==========================================================

    st.divider()

    calculate = st.button("Calculate Embodied Carbon", width='stretch')

    if calculate:
        run_calculation()

    st.divider()

    save_label = "💾 Update Version" if st.session_state.test_editing_mode == "edit" else "💾 Save This Version"
    save_version = st.button(save_label, width='stretch')

    if save_version:
        if not info.get("project_name"):
            st.error("Please enter or select a project name before saving.")
        else:
            version_number = perform_save()
            if st.session_state.test_editing_mode == "edit":
                st.success(f"Version {version_number} of '{info['project_name']}' updated.")
            else:
                st.success(f"Saved as Version {version_number} of '{info['project_name']}'.")

    if not st.session_state.test_results_df.empty:

        summary = st.session_state.test_summary

        st.divider()
        st.subheader("Embodied Carbon Summary")
        col1, col2 = st.columns(2)

        col1.metric("A1-A3", f"{summary['A1-A3']:,.2f} kgCO₂e")
        col2.metric("A4", f"{summary['A4']:,.2f} kgCO₂e")

        col3, col4 = st.columns(2)

        col3.metric("A5", f"{summary['A5']:,.2f} kgCO₂e")
        col4.metric("Total", f"{summary['Total']:,.2f} kgCO₂e")
        

        st.divider()
        st.subheader("Calculation Results")
        st.dataframe(st.session_state.test_results_df, width='stretch', hide_index=True)

        st.divider()
        st.subheader("Carbon Analysis Dashboard")

        left, right = st.columns(2)
        with left:
            fig = create_apparatus_pie_chart(st.session_state.test_results_df)
            if fig is not None:
                st.plotly_chart(fig, width='stretch')
        with right:
            fig = create_lifecycle_bar_chart(st.session_state.test_summary)
            if fig is not None:
                st.plotly_chart(fig, width='stretch')

        st.divider()
        st.subheader("Export Results")

        apparatus_fig = create_apparatus_pie_chart(st.session_state.test_results_df)
        lifecycle_fig = create_lifecycle_bar_chart(st.session_state.test_summary)

        pdf_bytes = generate_fire_design_report(
            project_name=info.get("project_name", "Unnamed Project"),
            summary=st.session_state.test_summary,
            results_df=st.session_state.test_results_df,
            apparatus_figure=apparatus_fig,
            lifecycle_figure=lifecycle_fig,
        )

        safe_project_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in info.get("project_name", "project")
        ).strip("_") or "project"

        st.download_button(
            "⬇️ Download PDF Report",
            data=pdf_bytes,
            file_name=f"{safe_project_name}_fire_design_report.pdf",
            mime="application/pdf",
            width="stretch",
        )

    
    render_footer()