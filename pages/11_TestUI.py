import streamlit as st
import pandas as pd
import copy

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer
from utils.project_store import (
    get_project_names,
    get_project_meta,
    get_next_version_number,
    save_project_version,
)
from utils.database_loader import load_carbon_database, get_building_classes
from utils.calculations import summarise_results
from utils.charts import create_apparatus_pie_chart, create_lifecycle_bar_chart

from utils.fire_system_config import (
    CATEGORY_NAMES,
    CATEGORY_SUBCATEGORIES,
    DETERMINATION_TYPE_OPTIONS,
    DETERMINATION_TYPE_LABELS,
    get_apparatus_name,
    get_dts_default,
    get_determination_type_label,
    validate_apparatus_names,
)
from utils.proposed_design_calculations import (
    calculate_equivalent_quantity,
    calculate_component_carbon,
    find_carbon_factors_row,
    find_product_carbon_factors_row,
    get_available_product_types,
)

# ==========================================================
# Page Configuration
# ==========================================================

st.set_page_config(
    page_title="TestUI",
    page_icon="🧪",
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

render_header("TestUI", APP_SUBTITLE, APP_STATUS)

# ==========================================================
# Table Templates
# ==========================================================

def empty_display_row():
    return pd.DataFrame(
        [{"Determination Type": None, "Value": None, "Product Type": None}]
    )


def dts_default_row(cat_num, sub_name):
    dts = get_dts_default(cat_num, sub_name)
    label = get_determination_type_label(dts["determination_type"])
    return pd.DataFrame(
        [{"Determination Type": label, "Value": dts["value"], "Product Type": None}]
    )


def pbd_default_row(cat_num, sub_name):
    dts = get_dts_default(cat_num, sub_name)
    label = get_determination_type_label(dts["determination_type"])
    return pd.DataFrame(
        [{"Determination Type": label, "Value": None, "Product Type": None}]
    )


def blank_subcategory_state():
    return {
        "status": "N/A",
        "expanded": False,
        "table": empty_display_row(),
    }


# ==========================================================
# Session State
# ==========================================================

if "test_step" not in st.session_state:
    st.session_state.test_step = 1

if "test_project_info" not in st.session_state:
    st.session_state.test_project_info = {}

if "test_categories" not in st.session_state:
    st.session_state.test_categories = {
        cat_num: {
            "subcategories": {
                sub_name: blank_subcategory_state()
                for sub_name in CATEGORY_SUBCATEGORIES[cat_num]
            }
        }
        for cat_num in CATEGORY_NAMES
    }

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

carbon_db = load_carbon_database()

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
                value=float(project_meta["area"]),
                key="test_building_area_existing",
            )

        assessment_notes = st.text_area(
            "Assessment Notes",
            value=project_meta["notes"],
            key="test_assessment_notes_existing",
        )

        next_version = get_next_version_number(project_name)

        st.info(f"This will be saved as **Version {next_version}** of '{project_name}'.")

    building_classes = get_building_classes()

    building_class = st.selectbox(
        "Building Class (NCC)",
        building_classes if building_classes else ["No building classes found"],
        key="test_building_class",
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
            st.session_state.test_project_info = {
                "project_mode": project_mode,
                "project_name": project_name,
                "building_area": building_area,
                "assessment_notes": assessment_notes,
                "building_class": building_class,
                "version_notes": version_notes,
            }
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
        product_output_df = carbon_db.get("product_output")
        building_area_m2 = st.session_state.test_project_info.get("building_area", 0)

        results = []
        warnings = []

        for cat_num, sub_names in CATEGORY_SUBCATEGORIES.items():
            for sub_name in sub_names:

                sub_state = st.session_state.test_categories[cat_num]["subcategories"][sub_name]
                status = sub_state["status"]

                if status == "N/A":
                    continue

                table = sub_state["table"]

                if table.empty:
                    continue

                row = table.iloc[0]
                determination_label = row.get("Determination Type")
                input_value = row.get("Value")
                product_type_name = row.get("Product Type")

                apparatus_name = get_apparatus_name(cat_num, sub_name)

                if not apparatus_name:
                    warnings.append(f"{sub_name}: no Carbon Database mapping configured yet.")
                    continue

                if input_value is None or pd.isna(input_value) or input_value == 0:
                    warnings.append(
                        f"{sub_name}: Value must be greater than 0 to be included in the calculation."
                    )
                    continue

                determination_type_key = DETERMINATION_TYPE_LABELS.get(determination_label)

                equivalent_quantity = calculate_equivalent_quantity(
                    determination_type_key,
                    input_value,
                    building_area_m2,
                )

                if equivalent_quantity is None:
                    warnings.append(f"{sub_name}: Building Area must be set to use Grid Spacing.")
                    continue

                carbon_factors_row = None

                if isinstance(product_type_name, str) and product_type_name.strip():

                    carbon_factors_row = find_product_carbon_factors_row(
                        product_output_df, apparatus_name, product_type_name
                    )

                    if carbon_factors_row is None:
                        warnings.append(
                            f"{sub_name}: Product Type '{product_type_name}' not found for "
                            f"'{apparatus_name}' - using generic apparatus average instead."
                        )

                if carbon_factors_row is None:
                    carbon_factors_row = find_carbon_factors_row(apparatus_output_df, apparatus_name)

                if carbon_factors_row is None:
                    warnings.append(f"{sub_name}: '{apparatus_name}' not found in Carbon Database.")
                    continue

                carbon_result = calculate_component_carbon(equivalent_quantity, carbon_factors_row)

                results.append(
                    {
                        "Apparatus": sub_name,
                        "Product Type": product_type_name if isinstance(product_type_name, str) and product_type_name.strip() else "(Generic average)",
                        "Quantity": equivalent_quantity,
                        "A1-A3": carbon_result["A1-A3"],
                        "A4": carbon_result["A4"],
                        "A5": carbon_result["A5"],
                        "Total": carbon_result["Total"],
                    }
                )

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

                sub_state = st.session_state.test_categories[cat_num]["subcategories"][sub_name]
                status = sub_state["status"]
                table = sub_state["table"]

                if status == "N/A" or table.empty:
                    rows.append(
                        {
                            "Category": cat_name,
                            "Subcategory": sub_name,
                            "Status": status,
                            "Determination Type": None,
                            "Value": None,
                            "Product Type": None,
                        }
                    )
                else:
                    r = table.iloc[0]
                    rows.append(
                        {
                            "Category": cat_name,
                            "Subcategory": sub_name,
                            "Status": status,
                            "Determination Type": r.get("Determination Type"),
                            "Value": r.get("Value"),
                            "Product Type": r.get("Product Type"),
                        }
                    )

        return pd.DataFrame(rows)


    def perform_save():
        """
        Runs calculation regardless of input state, then saves a new
        version. Returns the new version number.
        """

        project_name = info.get("project_name")

        run_calculation()

        version_number = save_project_version(
            project_name=project_name,
            area=info.get("building_area"),
            notes=info.get("assessment_notes"),
            version_notes=info.get("version_notes"),
            design_df=build_design_dataframe(),
            results_df=st.session_state.test_results_df,
            summary=st.session_state.test_summary,
        )

        st.session_state.test_dirty = False
        st.session_state.test_last_saved_snapshot = copy.deepcopy(st.session_state.test_categories)

        return version_number


    def discard_changes():
        """
        Reverts all category/subcategory data back to the last saved
        snapshot, discarding anything changed since.
        """
        st.session_state.test_categories = copy.deepcopy(st.session_state.test_last_saved_snapshot)
        st.session_state.test_dirty = False


    # ==========================================================
    # Unsaved Changes Dialog
    # ==========================================================

    @st.dialog("Unsaved Changes")
    def unsaved_changes_dialog():

        st.write(
            "You have unsaved changes to this design. "
            "Do you want to save them before leaving, or discard them?"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("💾 Save", use_container_width=True):
                project_name = info.get("project_name")
                if not project_name:
                    st.error("Please enter or select a project name before saving.")
                else:
                    version_number = perform_save()
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

    st.caption(
        f"**{info['project_name']}** · {info['building_area']:,.0f} m² · "
        f"{info['building_class']}"
    )

    back = st.button("← Back to Project Information")

    if back:
        if st.session_state.test_dirty:
            st.session_state.test_show_unsaved_dialog = True
            st.rerun()
        else:
            st.session_state.test_step = 1
            st.rerun()

    # ==========================================================
    # Database Name Validation
    # ==========================================================

    mismatches = validate_apparatus_names(carbon_db.get("apparatus_output"))

    if mismatches:
        mismatch_text = ", ".join(
            f"'{sub_name}' expects '{apparatus_name}'" for sub_name, apparatus_name in mismatches
        )
        st.warning(
            f"Some configured systems don't match any Apparatus name in the "
            f"Carbon Database, so they won't calculate correctly: {mismatch_text}"
        )

    st.divider()

    nav_col, body_col = st.columns([1, 3])

    # ------------------------------------------------------
    # Left: Category Navigation
    # ------------------------------------------------------

    def get_category_status_word(cat_num):
        subs = st.session_state.test_categories[cat_num]["subcategories"]
        if not subs:
            return "na"
        statuses = [s["status"] for s in subs.values()]
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
                clicked = st.button(
                    label,
                    key=f"cat_nav_button_{i}",
                    use_container_width=True,
                )

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

        if not subcats:

            st.info(
                f"'{CATEGORY_NAMES[selected]}' has not been configured yet. "
                "Let me know its subcategories and determination logic and "
                "I'll build it out the same way as Detection."
            )

        for sub_name in subcats:

            sub_state = st.session_state.test_categories[selected]["subcategories"][sub_name]

            st.divider()

            arrow_col, name_col, toggle_col = st.columns([0.5, 2, 3])

            with arrow_col:
                arrow_label = "▼" if sub_state["expanded"] else "▶"
                toggle_expand = st.button(
                    arrow_label,
                    key=f"expand_btn_{selected}_{sub_name}",
                )

            with name_col:
                st.markdown(f"**{sub_name}**")

            with toggle_col:
                new_status = st.radio(
                    "Determination Method",
                    ["N/A", "DTS", "PBD"],
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

                if new_status == "DTS":
                    sub_state["table"] = dts_default_row(selected, sub_name)
                elif new_status == "PBD":
                    sub_state["table"] = pbd_default_row(selected, sub_name)
                else:
                    sub_state["table"] = empty_display_row()

                st.session_state.test_categories[selected]["subcategories"][sub_name] = sub_state
                st.session_state.test_dirty = True
                st.rerun()

            if sub_state["expanded"]:

                apparatus_name = get_apparatus_name(selected, sub_name)

                if sub_state["status"] == "N/A":

                    st.dataframe(
                        empty_display_row(),
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.caption("The embodied carbon for this system is not considered.")

                elif sub_state["status"] == "DTS":

                    st.data_editor(
                        sub_state["table"],
                        use_container_width=True,
                        hide_index=True,
                        disabled=True,
                        num_rows="fixed",
                        column_config={
                            "Determination Type": st.column_config.TextColumn("Determination Type"),
                            "Value": st.column_config.NumberColumn("Value"),
                            "Product Type": st.column_config.TextColumn("Product Type"),
                        },
                        key=f"table_dts_{selected}_{sub_name}",
                    )

                else:  # PBD

                    product_options = get_available_product_types(
                        carbon_db.get("product_output"), apparatus_name
                    )

                    edited = st.data_editor(
                        sub_state["table"],
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "Determination Type": st.column_config.SelectboxColumn(
                                "Determination Type",
                                options=DETERMINATION_TYPE_OPTIONS,
                                required=True,
                            ),
                            "Value": st.column_config.NumberColumn(
                                "Value",
                                min_value=0.0,
                                required=True,
                            ),
                            "Product Type": st.column_config.SelectboxColumn(
                                "Product Type",
                                options=product_options if product_options else ["No products found"],
                                required=False,
                            ),
                        },
                        key=f"table_pbd_{selected}_{sub_name}",
                    )

                    if not edited.equals(sub_state["table"]):
                        st.session_state.test_categories[selected]["subcategories"][sub_name]["table"] = edited
                        st.session_state.test_dirty = True

    # ==========================================================
    # Calculate Button
    # ==========================================================

    st.divider()

    calculate = st.button(
        "Calculate Embodied Carbon",
        use_container_width=True,
    )

    if calculate:
        run_calculation()

    # ==========================================================
    # Save Version
    # ==========================================================

    st.divider()

    save_version = st.button(
        "💾 Save This Version",
        use_container_width=True,
    )

    if save_version:

        project_name = info.get("project_name")

        if not project_name:
            st.error("Please enter or select a project name before saving.")
        else:
            version_number = perform_save()
            st.success(
                f"Saved as Version {version_number} of '{project_name}'."
            )

    # ==========================================================
    # Results
    # ==========================================================

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

        st.dataframe(
            st.session_state.test_results_df,
            use_container_width=True,
            hide_index=True,
        )

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