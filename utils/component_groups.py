"""
Generic Component Archetype System

Three reusable archetypes cover almost every apparatus in the tool:

    KIND_INPUT                  - a value (with optional Grid Spacing
                                   toggle) + Product Type. Parameterized
                                   by include_spacing (bool) and units
                                   (list of strings) - this ONE archetype
                                   replaces what used to be five separate
                                   kinds (quantity/area/length/mass_volume/
                                   grid_spacing), since they only ever
                                   differed by these two settings.
    KIND_LINKED_CHILD            - include/exclude + "equal to parent" or
                                    manual override (e.g. Cabinets mirror
                                    Extinguishers, Batteries mirror their
                                    parent device).
    KIND_CROSS_CATEGORY_COUNTER  - checkboxes selecting which already-
                                    calculated apparatus to sum, plus an
                                    optional manual addition (e.g.
                                    Identification Signs counting
                                    Extinguishers + Hose Reels + Hydrants).

Anything with a genuinely different UI shape (Sprinkler Heads' multi-row
hazard table, Extinguishers' AS2444 minimum-rating form) stays as
bespoke, hand-written code elsewhere - these three archetypes are not
meant to force-fit every possible future component, only the ones that
are structurally identical to something already built.
"""

import streamlit as st

from utils.proposed_design_calculations import (
    calculate_equivalent_quantity,
    calculate_component_carbon,
    find_product_carbon_factors_row,
    get_available_product_types,
)

# ==========================================================
# Archetype Constants
# ==========================================================

KIND_INPUT = "input"
KIND_LINKED_CHILD = "linked_child"
KIND_CROSS_CATEGORY_COUNTER = "cross_category_counter"

DETERMINATION_TYPES = {
    "total_quantity": "Total Quantity (Units)",
    "grid_spacing": "Grid Spacing (Side length metres)",
}
DETERMINATION_TYPE_LABELS = {v: k for k, v in DETERMINATION_TYPES.items()}
DETERMINATION_TYPE_OPTIONS = list(DETERMINATION_TYPES.values())

LINKED_CHILD_MODES = ["Equal to Parent", "Quantity Override"]

DEFAULT_UNITS = ["units"]


# ==========================================================
# Component Spec Helper
# ==========================================================

def component_spec(
    key, label, apparatus, kind,
    disclaimer=None,
    parent_key=None,
    linked_mode="choice",
    include_spacing=False,
    units=None,
    counted_apparatus=None,
    manual_allowed=True,
):
    """
    Declares one component.

    key               : unique string within its group/page
    label             : display name
    apparatus         : exact Apparatus name in the Carbon Database
                         (unused for KIND_CROSS_CATEGORY_COUNTER)
    kind              : one of the KIND_* constants above

    -- KIND_INPUT --
    include_spacing   : if True, shows the Determination Type dropdown
                         (Total Quantity / Grid Spacing); if False, just
                         a plain Value field
    units             : list of unit strings for the Value field, e.g.
                         ["m2"] (fixed label) or ["kg", "L"] (selectable
                         toggle). Ignored when include_spacing is True,
                         since the determination type labels already
                         state their own units.

    -- KIND_LINKED_CHILD --
    parent_key        : the apparatus label whose quantity this mirrors.
                         Can be a sibling in the same group, OR any
                         Apparatus label already present in the running
                         results list (enables cross-category linking,
                         e.g. Sprinkler Valves -> "Sprinkler Heads").
    linked_mode       : "choice" (user picks Equal to Parent or
                         Override) or "override_only" (always manual,
                         e.g. Batteries)

    -- KIND_CROSS_CATEGORY_COUNTER --
    counted_apparatus : list of Apparatus labels to offer as checkboxes
    manual_allowed    : whether an additional manual quantity field is
                         also shown

    disclaimer        : optional warning caption shown under the input
    """
    return {
        "key": key,
        "label": label,
        "apparatus": apparatus,
        "kind": kind,
        "disclaimer": disclaimer,
        "parent_key": parent_key,
        "linked_mode": linked_mode,
        "include_spacing": include_spacing,
        "units": units or DEFAULT_UNITS,
        "counted_apparatus": counted_apparatus or [],
        "manual_allowed": manual_allowed,
    }


# ==========================================================
# Cross-Results Helper
# ==========================================================

def get_quantity_by_apparatus(results, apparatus_label):
    """
    Sums the Quantity of every result so far whose "Apparatus" matches
    the given label. Returns None if there's no match (rather than 0),
    so callers can distinguish "not yet calculated" from "genuinely
    zero". Used to resolve KIND_LINKED_CHILD parents that live outside
    the current group (e.g. Sprinkler Valves referencing the Sprinkler
    Heads total from a different, bespoke code path).
    """
    matches = [r["Quantity"] for r in results if r.get("Apparatus") == apparatus_label]
    if not matches:
        return None
    return sum(matches)


# ==========================================================
# State Initialization
# ==========================================================

def init_component_state(spec):
    kind = spec["kind"]

    if kind == KIND_INPUT:
        state = {"product_type": None, "value": None}
        if spec["include_spacing"]:
            state["determination_type"] = DETERMINATION_TYPES["grid_spacing"]
        elif len(spec["units"]) > 1:
            state["unit"] = spec["units"][0]
        return state

    if kind == KIND_LINKED_CHILD:
        default_mode = "Quantity Override" if spec.get("linked_mode") == "override_only" else "Equal to Parent"
        return {"included": False, "mode": default_mode, "override_value": None, "product_type": None}

    if kind == KIND_CROSS_CATEGORY_COUNTER:
        return {
            "selected": {label: True for label in spec["counted_apparatus"]},
            "manual_quantity": None,
            "product_type": None,
        }

    return {}


def init_group_state(specs):
    return {
        "expanded": False,
        "components": {spec["key"]: init_component_state(spec) for spec in specs},
    }


# ==========================================================
# Rendering
# ==========================================================

def render_component(spec, comp_state, apparatus_output_df, parent_quantity=None, key_prefix="", show_label=True):
    """
    Renders the widgets for a single component and mutates comp_state
    in place. Returns True if anything changed.
    """

    kind = spec["kind"]
    dirty = False

    if kind == KIND_LINKED_CHILD:

        new_included = st.checkbox(
            f"Include {spec['label']}", value=comp_state["included"],
            key=f"{key_prefix}_{spec['key']}_included",
        )
        if new_included != comp_state["included"]:
            comp_state["included"] = new_included
            dirty = True

        if comp_state["included"]:

            product_options = get_available_product_types(apparatus_output_df, spec["apparatus"])

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
                    st.caption(f"Quantity will match parent ({spec['parent_key']}): {parent_quantity:g}")
                else:
                    st.caption(f"Parent ({spec['parent_key']}) quantity not yet available - "
                               f"configure it first, or run Calculate to resolve it.")

        if spec.get("disclaimer"):
            st.caption(f"⚠️ {spec['disclaimer']}")

        return dirty

    if kind == KIND_CROSS_CATEGORY_COUNTER:

        st.caption(
            "Select which already-configured systems should be counted automatically. "
            "If a manual quantity is also entered, the two are added together."
        )

        for label in spec["counted_apparatus"]:
            new_val = st.checkbox(
                f"Count for {label}", value=comp_state["selected"].get(label, True),
                key=f"{key_prefix}_{spec['key']}_count_{label}",
            )
            if new_val != comp_state["selected"].get(label, True):
                comp_state["selected"][label] = new_val
                dirty = True

        product_options = get_available_product_types(apparatus_output_df, spec["apparatus"])

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

        if spec.get("manual_allowed"):
            with col2:
                new_manual = st.number_input(
                    "Additional Manual Quantity (optional)", min_value=0, step=1,
                    value=int(comp_state.get("manual_quantity") or 0),
                    key=f"{key_prefix}_{spec['key']}_manual",
                )
                if new_manual != comp_state.get("manual_quantity"):
                    comp_state["manual_quantity"] = new_manual
                    dirty = True

        resolved_product = None if new_product == "(none selected)" else new_product
        if resolved_product != comp_state.get("product_type"):
            comp_state["product_type"] = resolved_product
            dirty = True

        if spec.get("disclaimer"):
            st.caption(f"⚠️ {spec['disclaimer']}")

        return dirty

    # -------- KIND_INPUT --------

    if show_label:
        st.markdown(f"**{spec['label']}**")

    product_options = get_available_product_types(apparatus_output_df, spec["apparatus"])
    units = spec["units"]

    if spec["include_spacing"]:

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

    elif len(units) > 1:

        col1, col2, col3 = st.columns(3)
        with col1:
            new_unit = st.selectbox(
                "Unit", units, index=units.index(comp_state.get("unit", units[0])),
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
        if (new_unit != comp_state.get("unit") or new_value != comp_state.get("value")
                or resolved_product != comp_state.get("product_type")):
            comp_state["unit"] = new_unit
            comp_state["value"] = new_value
            comp_state["product_type"] = resolved_product
            dirty = True

    else:

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
                f"Quantity ({units[0]})", min_value=0.0, step=1.0,
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


def render_component_group(group_label, specs, group_state, apparatus_output_df, key_prefix, results_so_far=None):
    """
    Renders an expandable group containing multiple components.
    Returns "toggled" if the expand arrow was clicked (caller should
    st.rerun()), or True/False for whether anything inside changed.
    """

    results_so_far = results_so_far or []

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

        # Resolve same-group parent quantities from raw entered
        # values (a live preview only - the authoritative figure
        # comes from Calculate, since KIND_INPUT with include_spacing
        # needs Building Area to convert Grid Spacing to a quantity).
        parent_quantities = {}
        for spec in specs:
            if spec["kind"] == KIND_INPUT:
                comp_state = group_state["components"][spec["key"]]
                if not spec["include_spacing"]:
                    parent_quantities[spec["key"]] = comp_state.get("value")

        for i, spec in enumerate(specs):

            if i > 0:
                st.divider()

            comp_state = group_state["components"][spec["key"]]

            parent_qty = None
            if spec["kind"] == KIND_LINKED_CHILD and spec.get("parent_key"):
                parent_qty = parent_quantities.get(spec["parent_key"])
                if parent_qty is None:
                    parent_qty = get_quantity_by_apparatus(results_so_far, spec["parent_key"])

            changed = render_component(
                spec, comp_state, apparatus_output_df,
                parent_quantity=parent_qty, key_prefix=key_prefix,
            )
            dirty = dirty or changed

    return dirty


def render_single_component(spec, state, apparatus_output_df, key_prefix, results_so_far=None):
    """
    Renders one standalone component directly under its own nav entry
    - for subcategories that don't need a group wrapper. state =
    {"expanded": bool, "component": {...}}.
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
            parent_quantity=get_quantity_by_apparatus(results_so_far or [], spec.get("parent_key")),
            key_prefix=key_prefix, show_label=False,
        )

    return dirty


# ==========================================================
# Calculation
# ==========================================================

def calculate_component(spec, comp_state, apparatus_output_df, building_area_m2=None, parent_quantity=None, results_so_far=None, warnings=None):
    """
    Returns a result dict (Apparatus/Product Type/Quantity/A1-A3/A4/A5/Total)
    or None if this component contributes nothing.
    """

    warnings = warnings if warnings is not None else []
    results_so_far = results_so_far or []
    kind = spec["kind"]

    if kind == KIND_LINKED_CHILD:

        if not comp_state.get("included"):
            return None

        product_type_name = comp_state.get("product_type")

        if comp_state["mode"] == "Equal to Parent":
            quantity = parent_quantity
            if quantity is None:
                quantity = get_quantity_by_apparatus(results_so_far, spec.get("parent_key"))
        else:
            quantity = comp_state.get("override_value")

        if not quantity or quantity <= 0:
            warnings.append(f"{spec['label']}: no quantity available - not included.")
            return None

    elif kind == KIND_CROSS_CATEGORY_COUNTER:

        product_type_name = comp_state.get("product_type")

        auto_count = sum(
            get_quantity_by_apparatus(results_so_far, label) or 0
            for label, is_selected in comp_state["selected"].items() if is_selected
        )
        manual_qty = comp_state.get("manual_quantity") or 0
        quantity = auto_count + manual_qty

        if quantity <= 0:
            return None  # nothing selected/entered - not an error

    else:  # KIND_INPUT

        value = comp_state.get("value")
        product_type_name = comp_state.get("product_type")

        if not value or value <= 0:
            return None

        if spec["include_spacing"]:
            det_key = DETERMINATION_TYPE_LABELS.get(comp_state.get("determination_type"))
            quantity = calculate_equivalent_quantity(det_key, value, building_area_m2)
            if quantity is None:
                warnings.append(f"{spec['label']}: Building Area must be set to use Grid Spacing.")
                return None
        else:
            quantity = value

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


def calculate_component_group(specs, group_state, apparatus_output_df, building_area_m2=None, results_so_far=None, warnings=None):
    """
    Calculates every component in a group, resolving linked_child /
    cross_category_counter references (same-group or elsewhere in
    results_so_far) along the way. Returns a list of result dicts -
    does NOT mutate results_so_far; the caller should extend its own
    results list with the return value between components/groups if
    later components need to reference these.
    """

    warnings = warnings if warnings is not None else []
    results_so_far = list(results_so_far or [])
    group_results = []

    for spec in specs:
        if spec["kind"] in (KIND_LINKED_CHILD, KIND_CROSS_CATEGORY_COUNTER):
            continue
        comp_state = group_state["components"][spec["key"]]
        result = calculate_component(
            spec, comp_state, apparatus_output_df,
            building_area_m2=building_area_m2, results_so_far=results_so_far, warnings=warnings,
        )
        if result:
            group_results.append(result)
            results_so_far.append(result)

    for spec in specs:
        if spec["kind"] not in (KIND_LINKED_CHILD, KIND_CROSS_CATEGORY_COUNTER):
            continue
        comp_state = group_state["components"][spec["key"]]
        result = calculate_component(
            spec, comp_state, apparatus_output_df,
            building_area_m2=building_area_m2, results_so_far=results_so_far, warnings=warnings,
        )
        if result:
            group_results.append(result)
            results_so_far.append(result)

    return group_results


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
        elif kind == KIND_CROSS_CATEGORY_COUNTER:
            selected_labels = ", ".join(l for l, v in comp_state["selected"].items() if v)
            rows.append({
                "Category": cat_name, "Subcategory": spec["label"],
                "Status": f"Counting: {selected_labels or 'none'}",
                "Determination Type": "Auto-count + Manual",
                "Value": comp_state.get("manual_quantity"),
                "Product Type": comp_state.get("product_type"),
                "Hazard Rating": None,
            })
        else:
            rows.append({
                "Category": cat_name, "Subcategory": spec["label"],
                "Status": "Configured" if comp_state.get("value") else "Blank",
                "Determination Type": comp_state.get("determination_type", "Value"),
                "Value": comp_state.get("value"),
                "Product Type": comp_state.get("product_type"),
                "Hazard Rating": None,
            })

    return rows
