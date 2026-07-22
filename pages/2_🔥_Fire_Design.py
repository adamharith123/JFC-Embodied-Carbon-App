import streamlit as st
import pandas as pd
import copy
import math
import json

from utils.constants import APP_SUBTITLE, APP_STATUS
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
    get_parameter,
    calculate_quantity,
    get_available_condition_values,
    get_extinguisher_requirement,
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

render_header("Fire Design", APP_SUBTITLE, APP_STATUS)

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
# that sheet, not this file.
#
# The ONLY genuinely bespoke thing left is Extinguishers, because its
# UI shape (AS2444 minimum-rating form with hazard/class checkboxes)
# doesn't reduce to the generic archetypes. Everything else - all 10
# categories' names, structure, and components, including previously-
# unavailable Category 10 and previously-hardcoded Category 3 - is
# spreadsheet-driven.

_ui = load_ui_structure()

CATEGORY_NAMES = dict(_ui["category_names"])

CATEGORY_SUBCATEGORIES = {cat_num: list(subs) for cat_num, subs in _ui["category_subcategories"].items()}

CATEGORY_SUBCATEGORIES.setdefault(4, [])
if "Portable Extinguishers" not in CATEGORY_SUBCATEGORIES[4]:
    CATEGORY_SUBCATEGORIES[4].append("Portable Extinguishers")

for _cat_num in range(1, 11):
    CATEGORY_NAMES.setdefault(_cat_num, f"Category {_cat_num}")
    CATEGORY_SUBCATEGORIES.setdefault(_cat_num, [])

CATEGORY_APPARATUS_MAP = dict(_ui["apparatus_map"])

CATEGORY_APPARATUS_MAP.update({
    (4, "Portable Extinguishers"): "Portable Extinguisher",
    (4, "Extinguisher Brackets"): "Bracket",
    (4, "Extinguisher Cabinets"): "Cabinet",
})

GROUP_DEFINITIONS = dict(_ui["group_definitions"])

SINGLE_COMPONENT_DEFINITIONS = dict(_ui["single_component_definitions"])

SUBCATEGORY_KIND = dict(_ui["subcategory_kind"])

SUBCATEGORY_KIND.update({
    (4, "Portable Extinguishers"): "extinguisher",
})


def get_apparatus_name(cat_num, sub_name):
    return CATEGORY_APPARATUS_MAP.get((cat_num, sub_name))


def get_subcategory_kind(cat_num, sub_name):
    return SUBCATEGORY_KIND.get((cat_num, sub_name), "simple")


# ==========================================================
# Determination Types (legacy "simple" kind - still used by
# Category 3's Illuminated/Directional Exit Signs, which default
# here since they have no SUBCATEGORY_KIND entry)
# ==========================================================

EXTINGUISHER_DETERMINATION_TYPES = {
    "quantity": "Quantity",
    "coverage_area": "Coverage Area (m² per extinguisher)",
}
EXTINGUISHER_DETERMINATION_LABELS = {label: key for key, label in EXTINGUISHER_DETERMINATION_TYPES.items()}
EXTINGUISHER_DETERMINATION_OPTIONS = list(EXTINGUISHER_DETERMINATION_TYPES.values())

BRACKET_CABINET_MODE_OPTIONS = ["Equal to Extinguishers", "Quantity Override"]


def blank_subcategory_state(cat_num, sub_name):

    kind = get_subcategory_kind(cat_num, sub_name)

    if kind == "extinguisher":
        return {
            "status": "N/A",
            "expanded": False,
            "hazard_class": "Ordinary",
            "fire_class_a": True,
            "fire_class_b": False,
            "has_fixed_suppression": False,
            "electronics_present": False,
            "product_type": None,
            "determination_type": "Quantity",
            "override_value": None,
            "bracket_included": False,
            "bracket_mode": "Equal to Extinguishers",
            "bracket_quantity_override": None,
            "bracket_product_type": None,
            "cabinet_included": False,
            "cabinet_mode": "Equal to Extinguishers",
            "cabinet_quantity_override": None,
            "cabinet_product_type": None,
        }

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
    if kind == "extinguisher":
        return sub_state.get("status", "N/A")
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

    None of the current archetypes (component_group, single_component,
    extinguisher) have a state shape that's fully reconstructable from
    the flat design-row format used for saving, so every subcategory
    is reset to a fresh blank state rather than risk building a
    malformed one. Restoring exact prior inputs on "Edit Version" is a
    known limitation - the saved Results/Summary are still shown
    read-only regardless.
    """

    return fresh_categories()


def version_summary_label(v):
    first_line = (v["version_notes"] or "").strip().splitlines()
    note_preview = first_line[0][:60] if first_line else "No notes"
    status_tag = " (Draft — incomplete)" if v["status"] == "draft" else ""
    return f"Version {v['version']} — {note_preview}{status_tag}"


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

        col1, col2 = st.columns(2)

        with col1:
            project_name = st.text_input(
                "Project Name",
                placeholder="Example: ABC Office Fitout",
                key="test_project_name_new",
            )

        with col2:
            building_area = st.number_input(
                "Building Area (m²)",
                min_value=0.0,
                step=1.0,
                key="test_building_area_new",
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

        col1, col2 = st.columns(2)

        with col1:
            project_name = st.selectbox(
                "Select Project",
                existing_projects,
                key="test_project_name_existing",
            )

        project_meta = get_project_meta(project_name)

        with col2:
            building_area = st.number_input(
                "Building Area (m²)",
                min_value=0.0,
                step=1.0,
                value=float(project_meta["area"]) if project_meta and project_meta["area"] else 0.0,
                key="test_building_area_existing",
            )

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

        if selected_version_label != "+ New Version":

            selected_index = version_options.index(selected_version_label) - 1
            selected_existing_version = versions[selected_index]

            show_next_button = False

            st.divider()

            st.info("🔒 This version is locked. Click **Edit Version** below to make changes.")

            summary = selected_existing_version["summary"]

            if summary:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("A1-A3", f"{summary.get('A1-A3', 0):,.2f} kgCO₂e")
                col2.metric("A4", f"{summary.get('A4', 0):,.2f} kgCO₂e")
                col3.metric("A5", f"{summary.get('A5', 0):,.2f} kgCO₂e")
                col4.metric("Total", f"{summary.get('Total', 0):,.2f} kgCO₂e")

            if selected_existing_version["version_notes"]:
                st.markdown("**Version Notes**")
                st.text(selected_existing_version["version_notes"])

            design_rows = selected_existing_version["design"]

            if design_rows:
                st.markdown("**Design Composition**")
                st.dataframe(
                    pd.DataFrame(design_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            edit_col, export_col = st.columns(2)

            with edit_col:
                edit_version_clicked = st.button(
                    "✏️ Edit Version",
                    use_container_width=True,
                )

            with export_col:
                export_payload = export_version(project_name, selected_existing_version["version"])
                st.download_button(
                    "⬇️ Export Version",
                    data=json.dumps(export_payload, indent=2),
                    file_name=f"{project_name}_v{selected_existing_version['version']}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            if edit_version_clicked:

                building_classes = get_building_classes()

                st.session_state.test_project_info = {
                    "project_mode": project_mode,
                    "project_name": project_name,
                    "building_area": building_area,
                    "assessment_notes": assessment_notes,
                    "building_class": building_classes[0] if building_classes else "",
                    "version_notes": selected_existing_version["version_notes"] or "",
                    "floor_area_per_storey": None,
                    "building_storeys": None,
                    "building_effective_height": None,
                    "building_floor_to_floor_height": None,
                    "building_risers": None,
                    "building_exits_per_storey": None,
                    "sprinkler_hazard_classification": None,
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
                    value=float(building_area) if building_area else 0.0,
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

            row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)

            with row2_col1:
                building_floor_to_floor_height = st.number_input(
                    "Floor-to-Floor Height (m)",
                    min_value=0.0,
                    step=0.1,
                    key="test_building_ftf_height",
                )

            with row2_col2:
                building_risers = st.number_input(
                    "Number of Risers",
                    min_value=0,
                    step=1,
                    key="test_building_risers",
                )

            with row2_col3:
                building_exits_per_storey = st.number_input(
                    "Number of Exits per Storey",
                    min_value=0,
                    step=1,
                    key="test_building_exits_per_storey",
                )

            with row2_col4:
                sprinkler_hazard_classification = st.selectbox(
                    "Sprinkler Hazard Classification",
                    [
                        "Light Hazard",
                        "Ordinary Hazard",
                        "High Hazard",
                        "User-defined",
                    ],
                    index=2,
                    key="test_sprinkler_hazard_classification",
                )


        version_notes = st.text_area(
            "Version Notes",
            placeholder="Describe what changed in this design iteration...",
            key=f"test_version_notes_{project_mode}_{project_name}",
        )

        st.divider()

        next_step = st.button(
            "Next: Configure Fire Safety Systems →",
            use_container_width=True,
        )

        if next_step:

            if not project_name:
                st.error("Please enter or select a project name before continuing.")
            else:
                reserved_version = reserve_next_version(project_name, building_area, assessment_notes)

                st.session_state.test_project_info = {
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
                    "building_risers": building_risers,
                    "building_exits_per_storey": building_exits_per_storey,
                    "sprinkler_hazard_classification": sprinkler_hazard_classification,
                }

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

                elif kind == "extinguisher":

                    if sub_state["status"] == "N/A":
                        continue

                    product_type_name = sub_state.get("product_type")

                    if not isinstance(product_type_name, str) or not product_type_name.strip():
                        warnings.append(f"{sub_name}: no Product Type selected for Extinguishers - not included.")
                        continue

                    extinguisher_quantity = None

                    if sub_state["status"] == "DTS":

                        candidate_quantities = []

                        if sub_state.get("fire_class_a"):
                            req_a = get_extinguisher_requirement(sub_state["hazard_class"], "A", sub_state["has_fixed_suppression"])
                            if req_a and req_a["max_area"]:
                                qty_a = calculate_quantity(
                                    "extinguisher", "portable_extinguisher", "quantity_formula",
                                    {"storeys": info.get("building_storeys"), "floor_area": building_area_m2, "max_area": req_a["max_area"]},
                                )
                                if qty_a is not None:
                                    candidate_quantities.append(qty_a)

                        if sub_state.get("fire_class_b"):
                            req_b = get_extinguisher_requirement(sub_state["hazard_class"], "B", sub_state["has_fixed_suppression"])
                            if req_b and req_b["max_area"]:
                                qty_b = calculate_quantity(
                                    "extinguisher", "portable_extinguisher", "quantity_formula",
                                    {"storeys": info.get("building_storeys"), "floor_area": building_area_m2, "max_area": req_b["max_area"]},
                                )
                                if qty_b is not None:
                                    candidate_quantities.append(qty_b)

                        if candidate_quantities:
                            extinguisher_quantity = max(candidate_quantities)  # conservative: more onerous class governs

                    else:  # PBD

                        det_key = EXTINGUISHER_DETERMINATION_LABELS.get(sub_state["determination_type"])
                        override_value = sub_state.get("override_value")

                        if not override_value or override_value <= 0:
                            warnings.append(f"{sub_name}: enter a Value greater than 0 for Extinguishers.")
                        elif det_key == "quantity":
                            extinguisher_quantity = override_value
                        elif det_key == "coverage_area":
                            extinguisher_quantity = calculate_quantity(
                                "extinguisher", "portable_extinguisher", "quantity_formula",
                                {"storeys": info.get("building_storeys"), "floor_area": building_area_m2, "max_area": override_value},
                            )
                            if extinguisher_quantity is None:
                                warnings.append(f"{sub_name}: Building Area and Storeys must be set to use Coverage Area.")

                    if extinguisher_quantity and extinguisher_quantity > 0:

                        carbon_factors_row = find_product_carbon_factors_row(
                            apparatus_output_df, apparatus_name, product_type_name
                        )

                        if carbon_factors_row is None:
                            warnings.append(f"Extinguishers: Product Type '{product_type_name}' not found for '{apparatus_name}'.")
                        else:
                            carbon_result = calculate_component_carbon(extinguisher_quantity, carbon_factors_row)
                            results.append({
                                "Apparatus": "Portable Extinguishers",
                                "Product Type": product_type_name,
                                "Quantity": extinguisher_quantity,
                                "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                            })
                    else:
                        warnings.append(
                            f"{sub_name}: insufficient inputs to calculate an extinguisher quantity."
                        )

                    # ---- Brackets ----

                    bracket_active = (sub_state["status"] == "DTS") or sub_state.get("bracket_included")

                    if bracket_active and extinguisher_quantity:

                        bracket_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Brackets"))
                        bracket_product = sub_state.get("bracket_product_type")

                        if sub_state["status"] == "DTS" or sub_state.get("bracket_mode") == "Equal to Extinguishers":
                            bracket_qty = extinguisher_quantity
                        else:
                            bracket_qty = sub_state.get("bracket_quantity_override")

                        if not bracket_product:
                            warnings.append("Brackets: no Product Type selected - not included.")
                        elif not bracket_qty or bracket_qty <= 0:
                            warnings.append("Brackets: quantity must be greater than 0 - not included.")
                        else:
                            carbon_factors_row = find_product_carbon_factors_row(
                                apparatus_output_df, bracket_apparatus, bracket_product
                            )
                            if carbon_factors_row is None:
                                warnings.append(f"Brackets: Product Type '{bracket_product}' not found for '{bracket_apparatus}'.")
                            else:
                                carbon_result = calculate_component_carbon(bracket_qty, carbon_factors_row)
                                results.append({
                                    "Apparatus": "Extinguisher Brackets",
                                    "Product Type": bracket_product,
                                    "Quantity": bracket_qty,
                                    "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                    "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                                })

                    # ---- Cabinets ----

                    cabinet_active = (sub_state["status"] == "DTS") or sub_state.get("cabinet_included")

                    if cabinet_active and extinguisher_quantity:

                        cabinet_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Cabinets"))
                        cabinet_product = sub_state.get("cabinet_product_type")

                        if sub_state["status"] == "DTS" or sub_state.get("cabinet_mode") == "Equal to Extinguishers":
                            cabinet_qty = extinguisher_quantity
                        else:
                            cabinet_qty = sub_state.get("cabinet_quantity_override")

                        if not cabinet_product:
                            warnings.append("Cabinets: no Product Type selected - not included.")
                        elif not cabinet_qty or cabinet_qty <= 0:
                            warnings.append("Cabinets: quantity must be greater than 0 - not included.")
                        else:
                            carbon_factors_row = find_product_carbon_factors_row(
                                apparatus_output_df, cabinet_apparatus, cabinet_product
                            )
                            if carbon_factors_row is None:
                                warnings.append(f"Cabinets: Product Type '{cabinet_product}' not found for '{cabinet_apparatus}'.")
                            else:
                                carbon_result = calculate_component_carbon(cabinet_qty, carbon_factors_row)
                                results.append({
                                    "Apparatus": "Extinguisher Cabinets",
                                    "Product Type": cabinet_product,
                                    "Quantity": cabinet_qty,
                                    "A1-A3": carbon_result["A1-A3"], "A4": carbon_result["A4"],
                                    "A5": carbon_result["A5"], "Total": carbon_result["Total"],
                                })
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

                elif kind == "extinguisher":

                    rows.append({
                        "Category": cat_name, "Subcategory": sub_name,
                        "Status": sub_state.get("status", "N/A"),
                        "Determination Type": f"Hazard: {sub_state.get('hazard_class')}, "
                                               f"Class A: {sub_state.get('fire_class_a')}, "
                                               f"Class B: {sub_state.get('fire_class_b')}, "
                                               f"Suppression: {sub_state.get('has_fixed_suppression')}, "
                                               f"Extinguisher determination: {sub_state.get('determination_type')}",
                        "Value": sub_state.get("override_value"),
                        "Product Type": sub_state.get("product_type"),
                        "Hazard Rating": sub_state.get("hazard_class"),
                    })
                    if sub_state.get("bracket_included") or sub_state.get("status") == "DTS":
                        rows.append({
                            "Category": cat_name, "Subcategory": "Extinguisher Brackets",
                            "Status": sub_state.get("bracket_mode"),
                            "Determination Type": sub_state.get("bracket_mode"),
                            "Value": sub_state.get("bracket_quantity_override"),
                            "Product Type": sub_state.get("bracket_product_type"),
                            "Hazard Rating": None,
                        })
                    if sub_state.get("cabinet_included") or sub_state.get("status") == "DTS":
                        rows.append({
                            "Category": cat_name, "Subcategory": "Extinguisher Cabinets",
                            "Status": sub_state.get("cabinet_mode"),
                            "Determination Type": sub_state.get("cabinet_mode"),
                            "Value": sub_state.get("cabinet_quantity_override"),
                            "Product Type": sub_state.get("cabinet_product_type"),
                            "Hazard Rating": None,
                        })

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
            )
        else:
            finalize_version(
                project_name=project_name, version_number=version_number,
                area=info.get("building_area"), notes=info.get("assessment_notes"),
                version_notes=info.get("version_notes"),
                design_df=build_design_dataframe(),
                results_df=st.session_state.test_results_df,
                summary=st.session_state.test_summary,
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
            if st.button("💾 Save", use_container_width=True):
                if not info.get("project_name"):
                    st.error("Please enter or select a project name before saving.")
                else:
                    perform_save()
                    st.session_state.test_show_unsaved_dialog = False
                    st.session_state.test_step = 1
                    st.rerun()

        with col2:
            if st.button("🗑️ Discard", use_container_width=True):
                discard_changes()
                st.session_state.test_show_unsaved_dialog = False
                st.session_state.test_step = 1
                st.rerun()

        with col3:
            if st.button("Cancel", use_container_width=True):
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
                clicked = st.button(label, key=f"cat_nav_button_{i}", use_container_width=True)

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

            if kind == "extinguisher":

                arrow_col, name_col, toggle_col = st.columns([0.5, 2, 3])

                with arrow_col:
                    arrow_label = "▼" if sub_state["expanded"] else "▶"
                    toggle_expand = st.button(arrow_label, key=f"expand_btn_{selected}_{sub_name}")

                with name_col:
                    st.markdown(f"**{sub_name}**")

                with toggle_col:
                    new_status = st.radio(
                        "Determination Method", ["N/A", "DTS", "PBD"],
                        index=["N/A", "DTS", "PBD"].index(sub_state["status"]),
                        horizontal=True,
                        key=f"status_toggle_{selected}_{sub_name}",
                        label_visibility="collapsed",
                    )

                if toggle_expand:
                    sub_state["expanded"] = not sub_state["expanded"]
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.rerun()

                if new_status != sub_state["status"]:
                    sub_state["status"] = new_status
                    st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                    st.session_state.test_dirty = True
                    st.rerun()

                if sub_state["expanded"]:

                    if sub_state["status"] == "N/A":

                        st.caption("The embodied carbon for this system is not considered.")

                    else:

                        is_dts = sub_state["status"] == "DTS"

                        # ==================================================
                        # Extinguishers
                        # ==================================================

                        st.markdown("##### Extinguishers")

                        col1, col2 = st.columns(2)

                        with col1:
                            new_hazard = st.selectbox(
                                "Hazard Classification", ["Light", "Ordinary", "High"],
                                index=["Light", "Ordinary", "High"].index(sub_state["hazard_class"]),
                                key=f"ext_hazard_{selected}_{sub_name}",
                            )
                            new_class_a = st.checkbox(
                                "Class A Fire Risk Present", value=sub_state["fire_class_a"],
                                key=f"ext_class_a_{selected}_{sub_name}",
                            )
                            new_class_b = st.checkbox(
                                "Class B Fire Risk Present", value=sub_state["fire_class_b"],
                                key=f"ext_class_b_{selected}_{sub_name}",
                            )

                        with col2:
                            new_suppression = st.checkbox(
                                "Fixed Automatic Fire Suppression Present in This Area",
                                value=sub_state["has_fixed_suppression"],
                                key=f"ext_suppression_{selected}_{sub_name}",
                            )
                            new_electronics = st.checkbox(
                                "Electrical / Electronics Equipment Present (aggravating factor)",
                                value=sub_state["electronics_present"],
                                key=f"ext_electronics_{selected}_{sub_name}",
                            )

                        for key, new_val in [
                            ("hazard_class", new_hazard), ("fire_class_a", new_class_a),
                            ("fire_class_b", new_class_b), ("has_fixed_suppression", new_suppression),
                            ("electronics_present", new_electronics),
                        ]:
                            if sub_state[key] != new_val:
                                sub_state[key] = new_val
                                st.session_state.test_dirty = True

                        # ---- Requirement warning (informational, both DTS and PBD) ----

                        requirement_lines = []

                        if new_class_a:
                            req_a = get_extinguisher_requirement(new_hazard, "A", new_suppression)
                            if req_a:
                                requirement_lines.append(
                                    f"Class A: minimum rating **{req_a['min_rating']}** "
                                    f"(covers up to {req_a['max_area']:,.0f} m² per extinguisher)"
                                )

                        if new_class_b:
                            req_b = get_extinguisher_requirement(new_hazard, "B", new_suppression)
                            if req_b:
                                travel_note = f", travel distance {req_b['travel_distance']} m" if req_b["travel_distance"] else ""
                                requirement_lines.append(
                                    f"Class B: minimum rating **{req_b['min_rating']}** "
                                    f"(covers up to {req_b['max_area']:,.0f} m² per extinguisher{travel_note})"
                                )

                        if new_electronics:
                            requirement_lines.append(
                                "Electronics/electrical equipment present: an **(E)-rated** "
                                "extinguisher is additionally required for use on live electrical equipment."
                            )

                        if requirement_lines:
                            st.warning(
                                "**Minimum extinguisher requirement for this circumstance:**\n\n"
                                + "\n\n".join(f"- {line}" for line in requirement_lines)
                                + "\n\nThis cannot be automatically verified against the selected "
                                "Product Type below - please confirm the chosen product meets or "
                                "exceeds these ratings."
                            )

                        extinguisher_products = get_available_product_types(
                            carbon_db.get("apparatus_output"), apparatus_name
                        )

                        new_product = st.selectbox(
                            "Product Type", ["(none selected)"] + extinguisher_products,
                            index=(
                                (["(none selected)"] + extinguisher_products).index(sub_state.get("product_type"))
                                if sub_state.get("product_type") in extinguisher_products else 0
                            ),
                            key=f"ext_product_{selected}_{sub_name}",
                        )
                        resolved_product = None if new_product == "(none selected)" else new_product
                        if resolved_product != sub_state.get("product_type"):
                            sub_state["product_type"] = resolved_product
                            st.session_state.test_dirty = True

                        if sub_state["status"] == "PBD":

                            det_col, val_col = st.columns(2)

                            with det_col:
                                new_det_type = st.selectbox(
                                    "Determination Type", EXTINGUISHER_DETERMINATION_OPTIONS,
                                    index=EXTINGUISHER_DETERMINATION_OPTIONS.index(sub_state["determination_type"]),
                                    key=f"ext_det_type_{selected}_{sub_name}",
                                )

                            with val_col:
                                new_override_value = st.number_input(
                                    "Value", min_value=0.0, step=1.0,
                                    value=float(sub_state.get("override_value") or 0.0),
                                    key=f"ext_override_value_{selected}_{sub_name}",
                                )

                            if new_det_type != sub_state["determination_type"] or new_override_value != sub_state.get("override_value"):
                                sub_state["determination_type"] = new_det_type
                                sub_state["override_value"] = new_override_value
                                st.session_state.test_dirty = True

                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                        # ==================================================
                        # Brackets
                        # ==================================================

                        st.divider()
                        st.markdown("##### Brackets")

                        new_bracket_included = st.checkbox(
                            "Include Brackets", value=sub_state["bracket_included"],
                            disabled=is_dts,
                            key=f"bracket_included_{selected}_{sub_name}",
                        )
                        if new_bracket_included != sub_state["bracket_included"] and not is_dts:
                            sub_state["bracket_included"] = new_bracket_included
                            st.session_state.test_dirty = True

                        if is_dts or new_bracket_included:

                            bracket_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Brackets"))
                            bracket_products = get_available_product_types(carbon_db.get("apparatus_output"), bracket_apparatus)

                            new_bracket_product = st.selectbox(
                                "Bracket Product Type", ["(none selected)"] + bracket_products,
                                index=(
                                    (["(none selected)"] + bracket_products).index(sub_state.get("bracket_product_type"))
                                    if sub_state.get("bracket_product_type") in bracket_products else 0
                                ),
                                key=f"bracket_product_{selected}_{sub_name}",
                            )
                            resolved_bracket_product = None if new_bracket_product == "(none selected)" else new_bracket_product
                            if resolved_bracket_product != sub_state.get("bracket_product_type"):
                                sub_state["bracket_product_type"] = resolved_bracket_product
                                st.session_state.test_dirty = True

                            if not is_dts:
                                new_bracket_mode = st.radio(
                                    "Bracket Quantity", BRACKET_CABINET_MODE_OPTIONS,
                                    index=BRACKET_CABINET_MODE_OPTIONS.index(sub_state["bracket_mode"]),
                                    horizontal=True,
                                    key=f"bracket_mode_{selected}_{sub_name}",
                                )
                                if new_bracket_mode != sub_state["bracket_mode"]:
                                    sub_state["bracket_mode"] = new_bracket_mode
                                    st.session_state.test_dirty = True

                                if sub_state["bracket_mode"] == "Quantity Override":
                                    new_bracket_qty = st.number_input(
                                        "Bracket Quantity", min_value=0, step=1,
                                        value=int(sub_state.get("bracket_quantity_override") or 0),
                                        key=f"bracket_qty_{selected}_{sub_name}",
                                    )
                                    if new_bracket_qty != sub_state.get("bracket_quantity_override"):
                                        sub_state["bracket_quantity_override"] = new_bracket_qty
                                        st.session_state.test_dirty = True
                            else:
                                st.caption("DTS: bracket quantity is set equal to the extinguisher quantity.")

                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                        # ==================================================
                        # Cabinets
                        # ==================================================

                        st.divider()
                        st.markdown("##### Cabinets")

                        new_cabinet_included = st.checkbox(
                            "Include Cabinets", value=sub_state["cabinet_included"],
                            disabled=is_dts,
                            key=f"cabinet_included_{selected}_{sub_name}",
                        )
                        if new_cabinet_included != sub_state["cabinet_included"] and not is_dts:
                            sub_state["cabinet_included"] = new_cabinet_included
                            st.session_state.test_dirty = True

                        if is_dts or new_cabinet_included:

                            cabinet_apparatus = CATEGORY_APPARATUS_MAP.get((4, "Extinguisher Cabinets"))
                            cabinet_products = get_available_product_types(carbon_db.get("apparatus_output"), cabinet_apparatus)

                            new_cabinet_product = st.selectbox(
                                "Cabinet Product Type", ["(none selected)"] + cabinet_products,
                                index=(
                                    (["(none selected)"] + cabinet_products).index(sub_state.get("cabinet_product_type"))
                                    if sub_state.get("cabinet_product_type") in cabinet_products else 0
                                ),
                                key=f"cabinet_product_{selected}_{sub_name}",
                            )
                            resolved_cabinet_product = None if new_cabinet_product == "(none selected)" else new_cabinet_product
                            if resolved_cabinet_product != sub_state.get("cabinet_product_type"):
                                sub_state["cabinet_product_type"] = resolved_cabinet_product
                                st.session_state.test_dirty = True

                            if not is_dts:
                                new_cabinet_mode = st.radio(
                                    "Cabinet Quantity", BRACKET_CABINET_MODE_OPTIONS,
                                    index=BRACKET_CABINET_MODE_OPTIONS.index(sub_state["cabinet_mode"]),
                                    horizontal=True,
                                    key=f"cabinet_mode_{selected}_{sub_name}",
                                )
                                if new_cabinet_mode != sub_state["cabinet_mode"]:
                                    sub_state["cabinet_mode"] = new_cabinet_mode
                                    st.session_state.test_dirty = True

                                if sub_state["cabinet_mode"] == "Quantity Override":
                                    new_cabinet_qty = st.number_input(
                                        "Cabinet Quantity", min_value=0, step=1,
                                        value=int(sub_state.get("cabinet_quantity_override") or 0),
                                        key=f"cabinet_qty_{selected}_{sub_name}",
                                    )
                                    if new_cabinet_qty != sub_state.get("cabinet_quantity_override"):
                                        sub_state["cabinet_quantity_override"] = new_cabinet_qty
                                        st.session_state.test_dirty = True
                            else:
                                st.caption("DTS: cabinet quantity is set equal to the extinguisher quantity.")

                        st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state

                continue

            # Defensive fallback - should be unreachable since every
            # subcategory in CATEGORY_SUBCATEGORIES now comes from a
            # recognized archetype (ui_structure sheet) or the
            # Extinguisher special case.
            st.markdown(f"**{sub_name}**")
            st.warning(f"Unrecognized configuration kind '{kind}' for this subcategory.")

    # ==========================================================
    # Calculate / Save / Results
    # ==========================================================

    st.divider()

    calculate = st.button("Calculate Embodied Carbon", use_container_width=True)

    if calculate:
        run_calculation()

    st.divider()

    save_label = "💾 Update Version" if st.session_state.test_editing_mode == "edit" else "💾 Save This Version"
    save_version = st.button(save_label, use_container_width=True)

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

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("A1-A3", f"{summary['A1-A3']:,.2f} kgCO₂e")
        col2.metric("A4", f"{summary['A4']:,.2f} kgCO₂e")
        col3.metric("A5", f"{summary['A5']:,.2f} kgCO₂e")
        col4.metric("Total", f"{summary['Total']:,.2f} kgCO₂e")

        st.divider()
        st.subheader("Calculation Results")
        st.dataframe(st.session_state.test_results_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Carbon Analysis Dashboard")

        left, right = st.columns(2)
        with left:
            fig = create_apparatus_pie_chart(st.session_state.test_results_df)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
        with right:
            fig = create_lifecycle_bar_chart(st.session_state.test_summary)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

    render_footer()