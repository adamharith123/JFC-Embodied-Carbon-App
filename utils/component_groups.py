"""
Generic Component Archetype System

Three reusable archetypes cover almost every apparatus in the tool:

    KIND_INPUT                  - a value + Product Type, with a
                                   configurable set of "modes" (Total
                                   Quantity / Grid Spacing / Coverage
                                   Area / Formula) an engineer can pick
                                   between per component, and an
                                   optional "multiple rows" flag for
                                   components that need to mix several
                                   product types in one system (e.g.
                                   Sprinkler Heads).
    KIND_LINKED_CHILD            - include/exclude + "equal to parent"
                                    or manual override (e.g. Cabinets
                                    mirror Extinguishers).
    KIND_CROSS_CATEGORY_COUNTER  - checkboxes selecting which already-
                                    calculated apparatus to sum, plus
                                    an optional manual addition.

Anything with a genuinely different UI shape (the Extinguisher's
AS2444 minimum-rating form) stays as bespoke, hand-written code
elsewhere - these three archetypes are not meant to force-fit every
possible future component, only ones structurally identical to
something already built.

IMPORTANT: calculate_component() always returns a LIST of result
dicts (possibly empty), not a single dict or None - this is what lets
a multi-row Input component produce several results from one
component. Callers should always do results.extend(...), not
results.append(...).
"""

import streamlit as st
import pandas as pd

from utils.proposed_design_calculations import (
    calculate_component_carbon,
    find_product_carbon_factors_row,
    get_available_product_types,
    get_frl_options,
    resolve_frl_multiplier,
)
from utils.standards_engine import (
    calculate_quantity as evaluate_calc_rules_formula,
    resolve_default_variables,
    get_notes as get_calc_rules_notes,
    get_parameter,
    get_available_condition_values,
    formula_variable_names,
)
import math


STATUS_NA = "N/A"
STATUS_DTS = "DTS"
STATUS_PBD = "PBD"

# ==========================================================
# Archetype Constants
# ==========================================================

KIND_INPUT = "input"
KIND_LINKED_CHILD = "linked_child"
KIND_CROSS_CATEGORY_COUNTER = "cross_category_counter"

MODE_LABELS = {
    "quantity": "Total Quantity (Units)",
    "grid_spacing": "Grid Spacing (Side length metres)",
    "coverage_area": "Coverage Area (m² per unit)",
    "formula": "Formula (AS Calc Sheet)",
}
PROJECT_INFO_ALIASES = {
    "protected_area": "building_area",
    "storeys": "building_storeys",
    "floor_to_floor_height": "building_floor_to_floor_height",
    "risers": "building_risers",
}
MODE_LABEL_TO_KEY = {v: k for k, v in MODE_LABELS.items()}

LINKED_CHILD_MODES = ["Equal to Parent", "Quantity Override"]

DEFAULT_UNITS = ["units"]
DEFAULT_MODES = ["quantity"]


# ==========================================================
# Component Spec Helper
# ==========================================================

def component_spec(
    key, label, apparatus, kind,
    disclaimer=None,
    info=None,
    parent_key=None,
    linked_mode="choice",
    modes=None,
    multi_row=False,
    units=None,
    formula_system=None,
    formula_component=None,
    formula_parameters=None,
    counted_apparatus=None,
    manual_allowed=True,
    frl_lookup=False,
):
    """
    Declares one component.

    key, label, apparatus, kind : as before

    -- KIND_INPUT --
    modes             : list of mode keys from MODE_LABELS, in the
                         order they should appear in the dropdown.
                         Only shown as a dropdown if len(modes) > 1;
                         a single-mode component just shows a plain
                         Value field.
    multi_row         : if True, renders as a dynamic table (like
                         Sprinkler Heads) where the engineer can add
                         rows to mix Product Types / determination
                         methods within one system.
    units             : display unit(s) for "Total Quantity" mode
                         (only meaningful when "quantity" is in modes)
    formula_system / formula_component / formula_parameters :
                         where to look up the "Formula" mode's value
                         in the calc_rules sheet - formula_parameters
                         is a list of parameter names, summed together
                         (e.g. ["vertical_riser_formula",
                         "horizontal_pipe_formula"])

    -- KIND_LINKED_CHILD --
    parent_key        : the apparatus label whose quantity this
                         mirrors - can be any Apparatus label already
                         present in the running results list, whether
                         from the same group or elsewhere.
    linked_mode       : "choice" or "override_only"

    -- KIND_CROSS_CATEGORY_COUNTER --
    counted_apparatus : list of Apparatus labels to offer as checkboxes
    manual_allowed    : whether a manual quantity field is also shown

    -- KIND_INPUT, Formula mode --
    A component using Formula mode can also set parent_key - if set,
    two extra variables become available to its formula:
    parent_quantity and parent_spacing_area/spacing_area (the
    referenced parent's calculated quantity, and its area-per-unit
    figure if it used Grid Spacing or Coverage Area mode).

    disclaimer        : optional warning caption shown under the input

    frl_lookup        : (KIND_INPUT, non-multi-row only) if True,
                         renders a separate "Required FRL (min)"
                         selector next to Value/Product Type, and
                         converts the entered quantity into a carbon
                         quantity via the frl_reference sheet before
                         pricing it against Product Type's carbon
                         factor - see get_frl_options/
                         resolve_frl_multiplier in
                         utils/proposed_design_calculations.py. Used
                         by Category 5 Wall Assemblies (Concrete,
                         Masonry, Speed Panel, Fire Resistant
                         Plasterboard). FRL is a direct user override -
                         nothing here derives it from the NCC.
    """
    return {
        "key": key,
        "label": label,
        "apparatus": apparatus,
        "kind": kind,
        "info": info,
        "disclaimer": disclaimer,
        "parent_key": parent_key,
        "linked_mode": linked_mode,
        "modes": modes or DEFAULT_MODES,
        "multi_row": multi_row,
        "units": units or DEFAULT_UNITS,
        "formula_system": formula_system,
        "formula_component": formula_component,
        "formula_parameters": formula_parameters or [],
        "counted_apparatus": counted_apparatus or [],
        "manual_allowed": manual_allowed,
        "frl_lookup": frl_lookup,
    }


# ==========================================================
# Cross-Results Helpers
# ==========================================================

def get_quantity_by_apparatus(results, apparatus_label):
    """
    Sums the Quantity of every result so far whose "Apparatus" matches
    the given label. Returns None (not 0) if there's no match, so
    callers can distinguish "not yet calculated" from "genuinely zero".
    """
    if not apparatus_label:
        return None
    matches = [r["Quantity"] for r in results if r.get("Apparatus") == apparatus_label]
    if not matches:
        return None
    return sum(matches)


def get_spacing_area_by_apparatus(results, apparatus_label):
    """
    Returns the first available "area per unit" figure reported by a
    Grid Spacing or Coverage Area calculation for the given apparatus
    label. Used by Formula-mode components that need to reference
    another component's spacing (e.g. Sprinkler Pipework referencing
    Sprinkler Heads). If the parent has multiple rows with different
    spacing values, the first one found is used - a simplification
    for the common case of a single hazard classification per system.
    """
    if not apparatus_label:
        return None
    for r in results:
        if r.get("Apparatus") == apparatus_label and r.get("SpacingArea") is not None:
            return r["SpacingArea"]
    return None


# ==========================================================
# State Initialization
# ==========================================================

def _empty_multi_row_table():
    return pd.DataFrame(columns=["Determination Type", "Value", "Product Type"])


def init_component_state(spec):
    kind = spec["kind"]

    if kind == KIND_INPUT:
        if spec["multi_row"]:
            return {"table": _empty_multi_row_table()}
        return {
            "status": STATUS_NA,
            "determination_type": MODE_LABELS[spec["modes"][0]],
            "value": None,
            "product_type": None,
            "frl_min": None,
        }

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

def _resolve_sheet_default(spec, parameter_name, comp_state, key_prefix, project_info=None, selector_label=None):
    """
    Resolves one named variable to a defensible starting value, in
    priority order: (1) an unconditional AS Calc Sheet default under
    this component's Formula System/Component, (2) if the sheet
    instead defines several named options for it (e.g. hazard class)
    with no single default, renders the selector to choose between
    them, (3) the matching Project Info field, (4) nothing - the
    field starts blank and the user must type a value.

    This is the one lookup behind Coverage Area, Grid Spacing, and
    the Formula-mode variable panel alike.
    """
    system, component = spec.get("formula_system"), spec.get("formula_component")

    if system and component:

        unconditional = get_parameter(system, component, parameter_name)
        if unconditional is not None:
            return unconditional, "AS Calc Sheet default"

        options = get_available_condition_values(system, component, parameter_name)
        if options:
            selectors = comp_state.setdefault("variable_selectors", {})
            chosen = st.selectbox(
                selector_label or f"{parameter_name.replace('_', ' ').title()} — condition", options,
                index=options.index(selectors[parameter_name]) if selectors.get(parameter_name) in options else 0,
                key=f"{key_prefix}_{parameter_name}_selector",
            )
            selectors[parameter_name] = chosen
            return get_parameter(system, component, parameter_name, condition_value=chosen), f"AS Calc Sheet ({chosen})"

    if project_info:
        project_value = project_info.get(PROJECT_INFO_ALIASES.get(parameter_name, parameter_name))
        if project_value:
            return project_value, "Project Info"

    return None, None


def _render_variable_field(spec, parameter_name, comp_state, key_prefix, project_info=None, display_label=None):
    """
    One editable numeric field, pre-filled via _resolve_sheet_default()
    and always freely overridable - whatever's currently in the field
    is what calculation will use. Persists to
    comp_state["variable_values"][parameter_name].
    """
    label = display_label or parameter_name.replace("_", " ").title()
    values = comp_state.setdefault("variable_values", {})

    resolved_default, source = _resolve_sheet_default(
        spec, parameter_name, comp_state, key_prefix,
        project_info=project_info, selector_label=f"{label} — condition",
    )

    seed = values.get(parameter_name)
    if seed is None and resolved_default is not None:
        seed = resolved_default

    new_value = st.number_input(
        label, min_value=0.0, step=0.1,
        value=float(seed or 0.0),
        key=f"{key_prefix}_{parameter_name}_value",
        help=f"{source}: {resolved_default:g}" if resolved_default is not None else "No sheet default found - manual entry.",
    )

    values[parameter_name] = new_value
    return new_value, source

# ==========================================================
# Rendering
# ==========================================================

def render_component(spec, comp_state, apparatus_output_df, parent_quantity=None, project_info=None, key_prefix="", show_label=True,
                      frl_reference_df=None):
    """
    Renders the widgets for a single component and mutates comp_state
    in place. Returns True if anything changed.
    """

    kind = spec["kind"]
    dirty = False

    # -------- Linked Child --------

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
        _render_info_panel(spec)

        return dirty

    # -------- Cross-Category Counter --------

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
        _render_info_panel(spec)

        return dirty

    # -------- Input --------

    formula_notes = None

    if not spec["multi_row"]:

        status_options = [STATUS_NA, STATUS_DTS, STATUS_PBD]
        current_status = comp_state.get("status", STATUS_NA)
        if current_status not in status_options:
            current_status = STATUS_NA

        name_col, status_col = st.columns([2, 3])

        with name_col:
            if show_label:
                st.markdown(f"**{spec['label']}**")

        with status_col:
            new_status = st.radio(
                spec["label"], status_options, index=status_options.index(current_status),
                horizontal=True, key=f"{key_prefix}_{spec['key']}_status", label_visibility="collapsed",
            )

        if new_status != comp_state.get("status"):
            comp_state["status"] = new_status
            dirty = True

        if comp_state["status"] == STATUS_NA:
            if spec.get("disclaimer"):
                st.caption(f"⚠️ {spec['disclaimer']}")
            _render_info_panel(spec)
            return dirty

    elif show_label:
        st.markdown(f"**{spec['label']}**")

    product_options = get_available_product_types(apparatus_output_df, spec["apparatus"])
    mode_options = [MODE_LABELS[m] for m in spec["modes"]]
    show_mode_dropdown = len(mode_options) > 1
    is_dts = (not spec["multi_row"]) and comp_state.get("status") == STATUS_DTS

    if spec["multi_row"]:

        column_config = {
            "Determination Type": st.column_config.SelectboxColumn(
                "Determination Type", options=mode_options, required=True,
                disabled=not show_mode_dropdown,
            ),
            "Value": st.column_config.NumberColumn("Value", min_value=0.0, required=True),
            "Product Type": st.column_config.SelectboxColumn(
                "Product Type",
                options=product_options if product_options else ["No products found"],
                required=False,
            ),
        }

        edited = st.data_editor(
            comp_state["table"], use_container_width=True, hide_index=True,
            num_rows="dynamic", column_config=column_config,
            key=f"{key_prefix}_{spec['key']}_table",
        )

        if not edited.equals(comp_state["table"]):
            comp_state["table"] = edited
            dirty = True

    else:

        show_frl = bool(spec.get("frl_lookup"))
        show_det_col = is_dts or show_mode_dropdown
        n_cols = (1 if show_det_col else 0) + 2 + (1 if show_frl else 0)
        cols = st.columns(n_cols)
        col_i = 0

        if is_dts:
            dts_mode_options = [
                m for m in mode_options
                if m != MODE_LABELS["quantity"]
                and not (m == MODE_LABELS["formula"] and not spec.get("formula_system"))
            ] or mode_options
            with cols[col_i]:
                if comp_state.get("determination_type") in dts_mode_options:
                    default_index = dts_mode_options.index(comp_state["determination_type"])
                elif MODE_LABELS["formula"] in dts_mode_options:
                    default_index = dts_mode_options.index(MODE_LABELS["formula"])
                else:
                    default_index = 0
                new_mode = st.selectbox(
                    "Determination Type", dts_mode_options,
                    index=default_index,
                    key=f"{key_prefix}_{spec['key']}_det",
                )
            st.caption("DTS: Total Quantity isn't offered here - every other method traces to an AS Calc Sheet default.")
            col_i += 1
        elif show_mode_dropdown:
            with cols[col_i]:
                new_mode = st.selectbox(
                    "Determination Type", mode_options,
                    index=mode_options.index(comp_state["determination_type"]),
                    key=f"{key_prefix}_{spec['key']}_det",
                )
            col_i += 1
        else:
            new_mode = mode_options[0]

        mode_key = MODE_LABEL_TO_KEY.get(new_mode)
        is_formula = mode_key == "formula"

        with cols[col_i]:
            if is_formula:
                st.number_input(
                    "Value — calculated automatically from AS Calc Sheet", value=0.0, disabled=True,
                    key=f"{key_prefix}_{spec['key']}_value_disabled",
                )
                new_value = comp_state.get("value")
            elif mode_key == "coverage_area":
                unit_label = spec["units"][0] if spec["units"] else "m² per unit"
                new_value, _ = _render_variable_field(
                    spec, "coverage_area", comp_state, key_prefix, project_info=project_info,
                    display_label=f"Coverage Area ({unit_label})",
                )
            elif mode_key == "grid_spacing":
                area_default, area_source = _resolve_sheet_default(
                    spec, "spacing_area", comp_state, key_prefix,
                    project_info=project_info, selector_label="Hazard Classification",
                )
                values = comp_state.setdefault("variable_values", {})
                seed = values.get("grid_spacing_side")
                if seed is None and area_default:
                    seed = math.sqrt(area_default)
                new_value = st.number_input(
                    "Grid Spacing (side length, m)", min_value=0.0, step=0.1,
                    value=float(seed or 0.0), key=f"{key_prefix}_{spec['key']}_value",
                    help=f"{area_source}: {area_default:g} m²/unit" if area_default else "No sheet default found - manual entry.",
                )
                values["grid_spacing_side"] = new_value
            else:
                unit_label = spec["units"][0] if spec["units"] else "units"
                value_label = "Value" if show_det_col else f"Value ({unit_label})"
                new_value = st.number_input(
                    value_label, min_value=0.0, step=1.0,
                    value=float(comp_state.get("value") or 0.0),
                    key=f"{key_prefix}_{spec['key']}_value",
                )
        col_i += 1

        with cols[col_i]:
            new_product = st.selectbox(
                "Product Type", ["(none selected)"] + product_options,
                index=(
                    (["(none selected)"] + product_options).index(comp_state.get("product_type"))
                    if comp_state.get("product_type") in product_options else 0
                ),
                key=f"{key_prefix}_{spec['key']}_product",
            )
        col_i += 1

        resolved_product = None if new_product == "(none selected)" else new_product

        new_frl = comp_state.get("frl_min")
        if show_frl:
            frl_options = get_frl_options(frl_reference_df, spec["apparatus"], resolved_product)
            frl_choices = ["(none selected)"] + [str(f) for f in frl_options]
            current = str(comp_state.get("frl_min")) if comp_state.get("frl_min") is not None else "(none selected)"
            with cols[col_i]:
                new_frl_choice = st.selectbox(
                    "Required FRL (min)", frl_choices,
                    index=frl_choices.index(current) if current in frl_choices else 0,
                    key=f"{key_prefix}_{spec['key']}_frl",
                )
            new_frl = None if new_frl_choice == "(none selected)" else int(new_frl_choice)

        if (new_mode != comp_state.get("determination_type") or new_value != comp_state.get("value")
                or resolved_product != comp_state.get("product_type") or new_frl != comp_state.get("frl_min")):
            comp_state["determination_type"] = new_mode
            comp_state["value"] = new_value
            comp_state["product_type"] = resolved_product
            comp_state["frl_min"] = new_frl
            dirty = True

        if is_formula:
            st.caption(
                f"Formula source: {spec['formula_system']} / {spec['formula_component']} "
                f"({', '.join(spec['formula_parameters'])})"
            )

            needed_vars = set()
            for p in spec["formula_parameters"]:
                raw = get_parameter(spec["formula_system"], spec["formula_component"], p)
                needed_vars |= formula_variable_names(raw)

            implicit_vars = {"parent_quantity", "parent_spacing_area"}
            if spec.get("parent_key"):
                implicit_vars.add("spacing_area")
            needed_vars -= implicit_vars

            formula_notes = [
                (p, get_calc_rules_notes(spec["formula_system"], spec["formula_component"], p))
                for p in spec["formula_parameters"]
            ]

            if needed_vars:
                with st.expander(f"🔢 Formula inputs for {spec['label']}", expanded=is_dts):
                    for var_name in sorted(needed_vars):
                        _render_variable_field(spec, var_name, comp_state, key_prefix, project_info=project_info)

    if spec.get("disclaimer"):
        st.caption(f"⚠️ {spec['disclaimer']}")

    _render_info_panel(spec, formula_notes)

    return dirty

def _render_info_panel(spec, formula_notes=None):
    """
    Collapsed-by-default panel showing the plain-English explanation
    from ui_structure's "Info" column, plus - for Formula-mode
    components - the calc_rules "notes" behind each parameter it
    pulls. Both are spreadsheet-maintained; nothing here is hardcoded
    per apparatus.
    """
    has_info = bool(spec.get("info"))
    has_notes = bool(formula_notes)
    if not has_info and not has_notes:
        return
    with st.expander("ℹ️ About this calculation", expanded=False):
        if has_info:
            st.markdown(spec["info"])
        if has_notes:
            if has_info:
                st.divider()
            for param_name, note in formula_notes:
                if note:
                    st.caption(f"**{param_name}**: {note}")

def render_component_group(group_label, specs, group_state, apparatus_output_df, key_prefix, results_so_far=None, project_info=None,
                            frl_reference_df=None):
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

        for i, spec in enumerate(specs):

            if i > 0:
                st.divider()

            comp_state = group_state["components"][spec["key"]]

            parent_qty = None
            if spec["kind"] == KIND_LINKED_CHILD and spec.get("parent_key"):
                parent_qty = get_quantity_by_apparatus(results_so_far, spec["parent_key"])

            changed = render_component(
                spec, comp_state, apparatus_output_df,
                parent_quantity=parent_qty, project_info=project_info, key_prefix=key_prefix,
                frl_reference_df=frl_reference_df,
            )
            dirty = dirty or changed

    return dirty


def render_single_component(spec, state, apparatus_output_df, key_prefix, results_so_far=None, project_info=None, frl_reference_df=None):
    """
    Renders one standalone component directly under its own nav entry.

    Input archetype, non-multi-row (the common case - Smoke Detectors
    etc.) is a thin pass-through: render_component() now owns its own
    N/A / DTS / PBD status control and collapses itself to one line
    when N/A, so there's nothing extra to do here.

    Any other standalone archetype (Linked Child / Counter, or a
    multi-row Input) doesn't have that built-in collapse, so it keeps
    the older arrow-expand wrapper as a fallback. state =
    {"expanded": bool, "component": {...}}.
    """

    if spec["kind"] == KIND_INPUT and not spec["multi_row"]:
        return render_component(
            spec, state["component"], apparatus_output_df,
            parent_quantity=get_quantity_by_apparatus(results_so_far or [], spec.get("parent_key")),
            project_info=project_info, key_prefix=key_prefix, show_label=True,
            frl_reference_df=frl_reference_df,
        )

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
            project_info=project_info, key_prefix=key_prefix, show_label=False,
            frl_reference_df=frl_reference_df,
        )

    return dirty


# ==========================================================
# Calculation
# ==========================================================

def _finalize_result(spec, quantity, product_type_name, apparatus_output_df, warnings, spacing_area=None,
                      carbon_quantity=None, frl_min=None, frl_detail=None):

    if not isinstance(product_type_name, str) or not product_type_name.strip():
        warnings.append(f"{spec['label']}: no Product Type selected - not included.")
        return None

    carbon_factors_row = find_product_carbon_factors_row(apparatus_output_df, spec["apparatus"], product_type_name)

    if carbon_factors_row is None:
        warnings.append(f"{spec['label']}: Product Type '{product_type_name}' not found for '{spec['apparatus']}'.")
        return None

    carbon_result = calculate_component_carbon(
        carbon_quantity if carbon_quantity is not None else quantity, carbon_factors_row
    )

    result = {
        "Apparatus": spec["label"],
        "Product Type": product_type_name,
        "Quantity": quantity,
        "SpacingArea": spacing_area,
        "A1-A3": carbon_result["A1-A3"],
        "A4": carbon_result["A4"],
        "A5": carbon_result["A5"],
        "Total": carbon_result["Total"],
    }

    if frl_min is not None:
        result["Required FRL (min)"] = frl_min
    if frl_detail:
        result["FRL Basis"] = frl_detail

    return result


def _apply_frl_lookup(spec, quantity, product_type_name, frl_reference_df, frl_min, warnings):
    """
    For a Wall Assembly component (spec["frl_lookup"] is True), turns
    the entered wall area into the quantity the carbon factor
    actually expects, using the frl_reference sheet. Returns
    (carbon_quantity, frl_detail_text), or None if it can't be
    resolved (a warning is appended in that case).
    """

    if frl_min is None:
        warnings.append(f"{spec['label']}: select a Required FRL (min) - not included.")
        return None

    resolved = resolve_frl_multiplier(frl_reference_df, spec["apparatus"], product_type_name, frl_min)

    if resolved is None:
        warnings.append(
            f"{spec['label']}: no FRL reference data for FRL {frl_min} with the selected Product Type - not included."
        )
        return None

    multiplier, detail = resolved
    return quantity * multiplier, detail


def _calculate_input_row(spec, determination_label, value, product_type_name, apparatus_output_df,
                          project_info, results_so_far, warnings, variable_values=None,
                          frl_reference_df=None, frl_min=None):

    mode_key = MODE_LABEL_TO_KEY.get(determination_label)

    if mode_key == "formula":

        variables = dict(project_info)
        for var_name, project_key in PROJECT_INFO_ALIASES.items():
            variables.setdefault(var_name, project_info.get(project_key))

        if spec.get("parent_key"):
            variables["parent_quantity"] = get_quantity_by_apparatus(results_so_far, spec["parent_key"])
            parent_spacing = get_spacing_area_by_apparatus(results_so_far, spec["parent_key"])
            variables["parent_spacing_area"] = parent_spacing
            variables["spacing_area"] = parent_spacing

        variables.update({k: v for k, v in (variable_values or {}).items() if v})

        variables = resolve_default_variables(spec["formula_system"], spec["formula_component"], variables)

        parts = []
        for param_name in spec["formula_parameters"]:
            part = evaluate_calc_rules_formula(spec["formula_system"], spec["formula_component"], param_name, variables)
            if part is None:
                warnings.append(
                    f"{spec['label']}: could not evaluate formula parameter '{param_name}' - check required "
                    f"inputs (Building Area, Storeys, Floor-to-Floor Height, Risers, or the referenced "
                    f"parent component)."
                )
                return None
            parts.append(part)

        if not parts:
            return None

        quantity = sum(parts)
        spacing_area_out = None

    else:

        if not value or value <= 0:
            return None

        building_area_m2 = project_info.get("building_area")
        spacing_area_out = None

        if mode_key == "quantity":
            quantity = value

        elif mode_key == "grid_spacing":
            if not building_area_m2 or building_area_m2 <= 0:
                warnings.append(f"{spec['label']}: Building Area must be set to use Grid Spacing.")
                return None
            quantity = building_area_m2 / (value ** 2)
            spacing_area_out = value ** 2

        elif mode_key == "coverage_area":
            if not building_area_m2 or building_area_m2 <= 0:
                warnings.append(f"{spec['label']}: Building Area must be set to use Coverage Area.")
                return None
            quantity = building_area_m2 / value
            spacing_area_out = value

        else:
            return None

    if spec.get("frl_lookup"):
        frl_result = _apply_frl_lookup(spec, quantity, product_type_name, frl_reference_df, frl_min, warnings)
        if frl_result is None:
            return None
        carbon_quantity, frl_detail = frl_result
        return _finalize_result(
            spec, quantity, product_type_name, apparatus_output_df, warnings,
            spacing_area=spacing_area_out, carbon_quantity=carbon_quantity, frl_min=frl_min, frl_detail=frl_detail,
        )

    return _finalize_result(spec, quantity, product_type_name, apparatus_output_df, warnings, spacing_area=spacing_area_out)


def calculate_component(spec, comp_state, apparatus_output_df, project_info=None, parent_quantity=None, results_so_far=None, warnings=None,
                         frl_reference_df=None):
    """
    Always returns a LIST of result dicts (possibly empty) - see
    module docstring. Callers should use results.extend(...).
    """

    warnings = warnings if warnings is not None else []
    results_so_far = results_so_far or []
    project_info = project_info or {}
    kind = spec["kind"]

    if kind == KIND_LINKED_CHILD:

        if not comp_state.get("included"):
            return []

        product_type_name = comp_state.get("product_type")

        if comp_state["mode"] == "Equal to Parent":
            quantity = parent_quantity
            if quantity is None:
                quantity = get_quantity_by_apparatus(results_so_far, spec.get("parent_key"))
        else:
            quantity = comp_state.get("override_value")

        if not quantity or quantity <= 0:
            warnings.append(f"{spec['label']}: no quantity available - not included.")
            return []

        result = _finalize_result(spec, quantity, product_type_name, apparatus_output_df, warnings)
        return [result] if result else []

    if kind == KIND_CROSS_CATEGORY_COUNTER:

        product_type_name = comp_state.get("product_type")

        auto_count = sum(
            get_quantity_by_apparatus(results_so_far, label) or 0
            for label, is_selected in comp_state["selected"].items() if is_selected
        )
        manual_qty = comp_state.get("manual_quantity") or 0
        quantity = auto_count + manual_qty

        if quantity <= 0:
            return []

        result = _finalize_result(spec, quantity, product_type_name, apparatus_output_df, warnings)
        return [result] if result else []

    # KIND_INPUT
    if not spec["multi_row"] and comp_state.get("status", STATUS_NA) == STATUS_NA:
        return []
    if spec["multi_row"]:

        table = comp_state.get("table")
        if table is None or table.empty:
            return []

        results = []
        for _, row in table.iterrows():
            result = _calculate_input_row(
                spec, row.get("Determination Type"), row.get("Value"), row.get("Product Type"),
                apparatus_output_df, project_info, results_so_far, warnings,
                frl_reference_df=frl_reference_df, frl_min=row.get("Required FRL (min)") if "Required FRL (min)" in table.columns else None,
            )
            if result:
                results.append(result)
        return results

    result = _calculate_input_row(
        spec, comp_state.get("determination_type"), comp_state.get("value"), comp_state.get("product_type"),
        apparatus_output_df, project_info, results_so_far, warnings,
        variable_values=comp_state.get("variable_values"),
        frl_reference_df=frl_reference_df, frl_min=comp_state.get("frl_min"),
    )
    return [result] if result else []


def calculate_component_group(specs, group_state, apparatus_output_df, project_info=None, results_so_far=None, warnings=None,
                               frl_reference_df=None):
    """
    Calculates every component in a group, IN SPEC ORDER, threading a
    growing results list so later components can reference earlier
    ones (Linked Child parents, Formula mode parents/spacing) whether
    they're in the same group or not.

    IMPORTANT: declare parent components BEFORE their children in the
    specs list (e.g. Sprinkler Heads before Sprinkler Pipework/Valves)
    - each component can only reference ones already calculated.
    """

    warnings = warnings if warnings is not None else []
    running_results = list(results_so_far or [])
    group_results = []

    for spec in specs:

        comp_state = group_state["components"][spec["key"]]

        parent_qty = None
        if spec["kind"] == KIND_LINKED_CHILD and spec.get("parent_key"):
            parent_qty = get_quantity_by_apparatus(running_results, spec["parent_key"])

        new_results = calculate_component(
            spec, comp_state, apparatus_output_df,
            project_info=project_info, parent_quantity=parent_qty,
            results_so_far=running_results, warnings=warnings,
            frl_reference_df=frl_reference_df,
        )

        group_results.extend(new_results)
        running_results.extend(new_results)

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

        elif spec["multi_row"]:
            table = comp_state.get("table")
            if table is None or table.empty:
                rows.append({
                    "Category": cat_name, "Subcategory": spec["label"], "Status": "Blank",
                    "Determination Type": None, "Value": None, "Product Type": None, "Hazard Rating": None,
                })
            else:
                for _, r in table.iterrows():
                    rows.append({
                        "Category": cat_name, "Subcategory": spec["label"], "Status": "Configured",
                        "Determination Type": r.get("Determination Type"),
                        "Value": r.get("Value"),
                        "Product Type": r.get("Product Type"),
                        "Hazard Rating": None,
                    })

        else:
            rows.append({
                "Category": cat_name, "Subcategory": spec["label"],
                "Status": comp_state.get("status", "N/A"),
                "Determination Type": comp_state.get("determination_type"),
                "Value": comp_state.get("value"),
                "Product Type": comp_state.get("product_type"),
                "Hazard Rating": None,
            })
    return rows