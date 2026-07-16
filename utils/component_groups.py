"""
Generic Component Group System

Reduces per-subcategory boilerplate to a small set of reusable
"component kinds" (quantity, grid_spacing, area, mass_volume, length,
linked_child) plus generic render/calculate/design functions that
work for ANY component matching one of these kinds.

A grouped subcategory (e.g. "Hose Reels", "Cabling") is declared as
an ordered list of component specs - see GROUP_DEFINITIONS in
pages/11_TestUI.py for actual usage. Adding a new grouped category
means adding a list of component_spec(...) entries, not writing new
render/calculate code.
"""

import streamlit as st

from utils.proposed_design_calculations import (
    calculate_equivalent_quantity,
    calculate_component_carbon,
    find_product_carbon_factors_row,
    get_available_product_types,
)

# ==========================================================
# Component Kind Constants
# ==========================================================

KIND_QUANTITY = "quantity"
KIND_GRID_SPACING = "grid_spacing"
KIND_AREA = "area"
KIND_MASS_VOLUME = "mass_volume"
KIND_LENGTH = "length"
KIND_LINKED_CHILD = "linked_child"

DETERMINATION_TYPES = {
    "total_quantity": "Total Quantity (Units)",
    "grid_spacing": "Grid Spacing (Side length metres)",
}
DETERMINATION_TYPE_LABELS = {v: k for k, v in DETERMINATION_TYPES.items()}
DETERMINATION_TYPE_OPTIONS = list(DETERMINATION_TYPES.values())

MASS_VOLUME_UNITS = ["kg", "L"]
LINKED_CHILD_MODES = ["Equal to Parent", "Quantity Override"]


# ==========================================================
# Component Spec Helper
# ==========================================================

def component_spec(key, label, apparatus, kind, disclaimer=None, parent_key=None, unit_label="units", linked_mode="choice"):
    """
    Declares one component within a group.
    key         : unique string within the group (used for state + widget keys)
    label       : display name shown in the UI
    apparatus   : exact Apparatus name in the Carbon Database
    kind        : one of the KIND_* constants above
    disclaimer  : optional warning caption shown under the input
    parent_key  : for KIND_LINKED_CHILD only - which sibling's quantity to mirror
    unit_label  : shown next to the quantity field for KIND_QUANTITY (e.g. "units", "pumps")    
    linked_mode (KIND_LINKED_CHILD only):
        "choice"        - user picks "Equal to Parent" or "Quantity Override" (default)
        "override_only" - always a manual quantity, no "Equal to Parent" option
                           (e.g. batteries, where count doesn't map 1:1 to the parent)
    """

    
    return {
        "key": key,
        "label": label,
        "apparatus": apparatus,
        "kind": kind,
        "disclaimer": disclaimer,
        "parent_key": parent_key,
        "unit_label": unit_label,
        "linked_mode": linked_mode,
    }


# ==========================================================
# State Initialization
# ==========================================================

def init_component_state(spec):
    kind = spec["kind"]
    if kind == KIND_QUANTITY:
        return {"product_type": None, "value": None}
    if kind == KIND_GRID_SPACING:
        return {"determination_type": DETERMINATION_TYPES["grid_spacing"], "value": None, "product_type": None}
    if kind == KIND_AREA:
        return {"product_type": None, "value": None}
    if kind == KIND_MASS_VOLUME:
        return {"unit": "kg", "product_type": None, "value": None}
    if kind == KIND_LENGTH:
        return {"product_type": None, "value": None}
    if kind == KIND_LINKED_CHILD:
        default_mode = "Quantity Override" if spec.get("linked_mode") == "override_only" else "Equal to Parent"
        return {"included": False, "mode": default_mode, "override_value": None, "product_type": None}
    return {}


def init_group_state(specs):
    return {
        "expanded": False,
        "components": {spec["key"]: init_component_state(spec) for spec in specs},
    }


# ==========================================================
# Rendering
# ==========================================================

def _component_quantity(spec, comp_state):
    """Best-effort raw quantity for a component, used to feed linked_child parents."""
    if spec["kind"] in (KIND_QUANTITY, KIND_AREA, KIND_MASS_VOLUME, KIND_LENGTH, KIND_GRID_SPACING):
        return comp_state.get("value")
    return None


def render_component(spec, comp_state, apparatus_output_df, parent_quantity=None, key_prefix="", show_label=True):
    """
    Renders the widgets for a single component and mutates comp_state
    in place. Returns True if anything changed.
    """

    kind = spec["kind"]
    dirty = False

    product_options = get_available_product_types(apparatus_output_df, spec["apparatus"])

    if kind == KIND_LINKED_CHILD:

        new_included = st.checkbox(
            f"Include {spec['label']}", value=comp_state["included"],
            key=f"{key_prefix}_{spec['key']}_included",
        )
        if new_included != comp_state["included"]:
            comp_state["included"] = new_included
            dirty = True

        if comp_state["included"]:

            new_product = st.selectbox(
                f"{spec['label']} Product Type", ["(none selected)"] + product_options,
                index=(
                    (["(none selected)"] + product_options).index(comp_state.get("product_type"))
                    if comp_state.get("product_type") in product_options else 0
                ),
                key=f"{key_prefix}_{spec['key']}_product",
            )
            resolved_product = None if new_product == "(none selected)" else new_product
            if resolved_product != comp_state.get("product_type"):
                comp_state["product_type"] = resolved_product
                dirty = True

            if spec.get("linked_mode") == "override_only":

                new_override = st.number_input(
                    f"{spec['label']} Quantity", min_value=0, step=1,
                    value=int(comp_state.get("override_value") or 0),
                    key=f"{key_prefix}_{spec['key']}_override",
                )
                if new_override != comp_state.get("override_value"):
                    comp_state["override_value"] = new_override
                    dirty = True

            else:
                new_mode = st.radio(
                    f"{spec['label']} Quantity", LINKED_CHILD_MODES,
                    index=LINKED_CHILD_MODES.index(comp_state["mode"]), horizontal=True,
                    key=f"{key_prefix}_{spec['key']}_mode",
                )
                if new_mode != comp_state["mode"]:
                    comp_state["mode"] = new_mode
                    dirty = True

                if comp_state["mode"] == "Quantity Override":
                    new_override = st.number_input(
                        f"{spec['label']} Quantity", min_value=0, step=1,
                        value=int(comp_state.get("override_value") or 0),
                        key=f"{key_prefix}_{spec['key']}_override",
                    )
                    if new_override != comp_state.get("override_value"):
                        comp_state["override_value"] = new_override
                        dirty = True
                elif parent_quantity is not None:
                    st.caption(f"Quantity will match parent: {parent_quantity:g}")
                elif parent_quantity is None:
                    st.caption("Parent quantity not yet available - configure the parent component first.")

        if spec.get("disclaimer"):
            st.caption(f"⚠️ {spec['disclaimer']}")

        return dirty

    if show_label:
        st.markdown(f"**{spec['label']}**")

    if kind == KIND_QUANTITY:

        col1, col2 = st.columns(2)
        with col1:
            new_product = st.selectbox(
                "Product Type", ["(none selected)"] + product_options,
                index=(
                    (["(none selected)"] + product_options).index(comp_state.get("product_type"))
                    if comp_state.get("product_type") in product_options else 0
                ),
                key=f"{key_prefix}_{spec['key']}_product",
            )
        with col2:
            new_value = st.number_input(
                f"Quantity ({spec['unit_label']})", min_value=0.0, step=1.0,
                value=float(comp_state.get("value") or 0.0),
                key=f"{key_prefix}_{spec['key']}_value",
            )

        resolved_product = None if new_product == "(none selected)" else new_product
        if resolved_product != comp_state.get("product_type") or new_value != comp_state.get("value"):
            comp_state["product_type"] = resolved_product
            comp_state["value"] = new_value
            dirty = True

    elif kind == KIND_GRID_SPACING:

        col1, col2, col3 = st.columns(3)
        with col1:
            new_det = st.selectbox(
                "Determination Type", DETERMINATION_TYPE_OPTIONS,
                index=DETERMINATION_TYPE_OPTIONS.index(comp_state["determination_type"]),
                key=f"{key_prefix}_{spec['key']}_det",
            )
        with col2:
            new_value = st.number_input(
                "Value", min_value=0.0, step=1.0,
                value=float(comp_state.get("value") or 0.0),
                key=f"{key_prefix}_{spec['key']}_value",
            )
        with col3:
            new_product = st.selectbox(
                "Product Type", ["(none selected)"] + product_options,
                index=(
                    (["(none selected)"] + product_options).index(comp_state.get("product_type"))
                    if comp_state.get("product_type") in product_options else 0
                ),
                key=f"{key_prefix}_{spec['key']}_product",
            )

        resolved_product = None if new_product == "(none selected)" else new_product
        if (new_det != comp_state["determination_type"] or new_value != comp_state.get("value")
                or resolved_product != comp_state.get("product_type")):
            comp_state["determination_type"] = new_det
            comp_state["value"] = new_value
            comp_state["product_type"] = resolved_product
            dirty = True

    elif kind == KIND_AREA:

        col1, col2 = st.columns(2)
        with col1:
            new_product = st.selectbox(
                "Product Type", ["(none selected)"] + product_options,
                index=(
                    (["(none selected)"] + product_options).index(comp_state.get("product_type"))
                    if comp_state.get("product_type") in product_options else 0
                ),
                key=f"{key_prefix}_{spec['key']}_product",
            )
        with col2:
            new_value = st.number_input(
                "Area (m²)", min_value=0.0, step=1.0,
                value=float(comp_state.get("value") or 0.0),
                key=f"{key_prefix}_{spec['key']}_value",
            )

        resolved_product = None if new_product == "(none selected)" else new_product
        if resolved_product != comp_state.get("product_type") or new_value != comp_state.get("value"):
            comp_state["product_type"] = resolved_product
            comp_state["value"] = new_value
            dirty = True

    elif kind == KIND_MASS_VOLUME:

        col1, col2, col3 = st.columns(3)
        with col1:
            new_unit = st.selectbox(
                "Unit", MASS_VOLUME_UNITS,
                index=MASS_VOLUME_UNITS.index(comp_state["unit"]),
                key=f"{key_prefix}_{spec['key']}_unit",
            )
        with col2:
            new_value = st.number_input(
                f"Quantity ({new_unit})", min_value=0.0, step=0.1,
                value=float(comp_state.get("value") or 0.0),
                key=f"{key_prefix}_{spec['key']}_value",
            )
        with col3:
            new_product = st.selectbox(
                "Product Type", ["(none selected)"] + product_options,
                index=(
                    (["(none selected)"] + product_options).index(comp_state.get("product_type"))
                    if comp_state.get("product_type") in product_options else 0
                ),
                key=f"{key_prefix}_{spec['key']}_product",
            )

        resolved_product = None if new_product == "(none selected)" else new_product
        if (new_unit != comp_state["unit"] or new_value != comp_state.get("value")
                or resolved_product != comp_state.get("product_type")):
            comp_state["unit"] = new_unit
            comp_state["value"] = new_value
            comp_state["product_type"] = resolved_product
            dirty = True

    elif kind == KIND_LENGTH:

        col1, col2 = st.columns(2)
        with col1:
            new_product = st.selectbox(
                "Product Type", ["(none selected)"] + product_options,
                index=(
                    (["(none selected)"] + product_options).index(comp_state.get("product_type"))
                    if comp_state.get("product_type") in product_options else 0
                ),
                key=f"{key_prefix}_{spec['key']}_product",
            )
        with col2:
            new_value = st.number_input(
                "Length (m)", min_value=0.0, step=1.0,
                value=float(comp_state.get("value") or 0.0),
                key=f"{key_prefix}_{spec['key']}_value",
            )

        resolved_product = None if new_product == "(none selected)" else new_product
        if resolved_product != comp_state.get("product_type") or new_value != comp_state.get("value"):
            comp_state["product_type"] = resolved_product
            comp_state["value"] = new_value
            dirty = True

    if spec.get("disclaimer"):
        st.caption(f"⚠️ {spec['disclaimer']}")

    return dirty


def render_component_group(group_label, specs, group_state, apparatus_output_df, key_prefix):
    """
    Renders an expandable group containing multiple components.
    Returns "toggled" if the expand arrow was clicked (caller should
    st.rerun()), or True/False for whether anything inside changed.
    """

    arrow_col, name_col = st.columns([0.5, 4])

    with arrow_col:
        arrow_label = "▼" if group_state["expanded"] else "▶"
        toggle_expand = st.button(arrow_label, key=f"{key_prefix}_expand")

    with name_col:
        st.markdown(f"**{group_label}**")

    if toggle_expand:
        group_state["expanded"] = not group_state["expanded"]
        return "toggled"

    dirty = False

    if group_state["expanded"]:

        parent_quantities = {}
        for spec in specs:
            if spec["kind"] != KIND_LINKED_CHILD:
                comp_state = group_state["components"][spec["key"]]
                parent_quantities[spec["key"]] = _component_quantity(spec, comp_state)

        for i, spec in enumerate(specs):

            if i > 0:
                st.divider()

            comp_state = group_state["components"][spec["key"]]

            parent_qty = None
            if spec["kind"] == KIND_LINKED_CHILD and spec.get("parent_key"):
                parent_qty = parent_quantities.get(spec["parent_key"])

            changed = render_component(
                spec, comp_state, apparatus_output_df,
                parent_quantity=parent_qty, key_prefix=key_prefix,
            )
            dirty = dirty or changed

    return dirty


# ==========================================================
# Calculation
# ==========================================================

def calculate_component(spec, comp_state, apparatus_output_df, building_area_m2=None, parent_quantity=None, warnings=None):
    """
    Returns a result dict (Apparatus/Product Type/Quantity/A1-A3/A4/A5/Total)
    or None if this component contributes nothing - either because it
    was intentionally left blank, or because required inputs are
    missing (in which case a warning is appended).
    """

    warnings = warnings if warnings is not None else []
    kind = spec["kind"]

    if kind == KIND_LINKED_CHILD:

        if not comp_state.get("included"):
            return None

        product_type_name = comp_state.get("product_type")

        quantity = parent_quantity if comp_state["mode"] == "Equal to Parent" else comp_state.get("override_value")

        if not quantity or quantity <= 0:
            warnings.append(f"{spec['label']}: no quantity available - not included.")
            return None

    elif kind == KIND_GRID_SPACING:

        value = comp_state.get("value")
        product_type_name = comp_state.get("product_type")

        if not value or value <= 0:
            return None

        det_key = DETERMINATION_TYPE_LABELS.get(comp_state.get("determination_type"))
        quantity = calculate_equivalent_quantity(det_key, value, building_area_m2)

        if quantity is None:
            warnings.append(f"{spec['label']}: Building Area must be set to use Grid Spacing.")
            return None

    else:  # KIND_QUANTITY, KIND_AREA, KIND_MASS_VOLUME, KIND_LENGTH

        value = comp_state.get("value")
        product_type_name = comp_state.get("product_type")
        quantity = value

        if not quantity or quantity <= 0:
            return None

    if not isinstance(product_type_name, str) or not product_type_name.strip():
        warnings.append(f"{spec['label']}: no Product Type selected - not included.")
        return None

    carbon_factors_row = find_product_carbon_factors_row(
        apparatus_output_df, spec["apparatus"], product_type_name
    )

    if carbon_factors_row is None:
        warnings.append(f"{spec['label']}: Product Type '{product_type_name}' not found for '{spec['apparatus']}'.")
        return None

    carbon_result = calculate_component_carbon(quantity, carbon_factors_row)

    return {
        "Apparatus": spec["label"],
        "Product Type": product_type_name,
        "Quantity": quantity,
        "A1-A3": carbon_result["A1-A3"],
        "A4": carbon_result["A4"],
        "A5": carbon_result["A5"],
        "Total": carbon_result["Total"],
    }

def render_single_component(spec, state, apparatus_output_df, key_prefix):
    """
    Renders one standalone component directly under its own nav entry
    - for subcategories that don't need a group wrapper (e.g. "Fire-
    Resistant Mastic" on its own, rather than several components
    under one dropdown). state = {"expanded": bool, "component": {...}}.
    """

    arrow_col, name_col = st.columns([0.5, 4])

    with arrow_col:
        arrow_label = "▼" if state["expanded"] else "▶"
        toggle_expand = st.button(arrow_label, key=f"{key_prefix}_expand")

    with name_col:
        st.markdown(f"**{spec['label']}**")

    if toggle_expand:
        state["expanded"] = not state["expanded"]
        return "toggled"

    dirty = False

    if state["expanded"]:
        dirty = render_component(
            spec, state["component"], apparatus_output_df,
            parent_quantity=None, key_prefix=key_prefix, show_label=False,
        )

    return dirty

def calculate_component_group(specs, group_state, apparatus_output_df, building_area_m2=None, warnings=None):
    """
    Calculates every component in a group, resolving linked_child
    parent quantities along the way. Returns a list of result dicts.
    """

    warnings = warnings if warnings is not None else []
    results = []
    resolved_quantities = {}

    for spec in specs:
        if spec["kind"] == KIND_LINKED_CHILD:
            continue
        comp_state = group_state["components"][spec["key"]]
        result = calculate_component(spec, comp_state, apparatus_output_df, building_area_m2=building_area_m2, warnings=warnings)
        if result:
            results.append(result)
            resolved_quantities[spec["key"]] = result["Quantity"]

    for spec in specs:
        if spec["kind"] != KIND_LINKED_CHILD:
            continue
        comp_state = group_state["components"][spec["key"]]
        parent_qty = resolved_quantities.get(spec.get("parent_key"))
        result = calculate_component(spec, comp_state, apparatus_output_df, building_area_m2=building_area_m2, parent_quantity=parent_qty, warnings=warnings)
        if result:
            results.append(result)

    return results


# ==========================================================
# Design Dataframe Rows
# ==========================================================

def component_group_design_rows(cat_name, specs, group_state):

    rows = []

    for spec in specs:

        comp_state = group_state["components"][spec["key"]]
        kind = spec["kind"]

        if kind == KIND_LINKED_CHILD:
            rows.append({
                "Category": cat_name, "Subcategory": spec["label"],
                "Status": "Included" if comp_state.get("included") else "Excluded",
                "Determination Type": comp_state.get("mode"),
                "Value": comp_state.get("override_value"),
                "Product Type": comp_state.get("product_type"),
                "Hazard Rating": None,
            })
        else:
            rows.append({
                "Category": cat_name, "Subcategory": spec["label"],
                "Status": "Configured" if comp_state.get("value") else "Blank",
                "Determination Type": comp_state.get("determination_type", kind),
                "Value": comp_state.get("value"),
                "Product Type": comp_state.get("product_type"),
                "Hazard Rating": None,
            })

    return rows