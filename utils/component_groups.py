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
from utils.formula_engine import (
    extract_formula_variables,
    evaluate_formula,
    solve_formula_for_variable,
    FormulaError,
)
from utils.condition_loader import get_condition_value, parameter_condition_key
import math


STATUS_NA = "N/A"
STATUS_DTS = "DTS"
STATUS_PBD = "PBD"

# Display-only labels for the status radio - comp_state["status"] and
# every comparison/export always uses the STATUS_* constants above
# verbatim; only what's drawn on screen changes here.
STATUS_DISPLAY_LABELS = {
    STATUS_NA: "N/A",
    STATUS_DTS: "DTS",
    STATUS_PBD: "Manual Override",
}

# ==========================================================
# Archetype Constants
# ==========================================================

KIND_INPUT = "input"
KIND_LINKED_CHILD = "linked_child"
KIND_CROSS_CATEGORY_COUNTER = "cross_category_counter"
KIND_UNAVAILABLE = "unavailable"

GRID_SPACING_LABEL = "Grid Spacing (m)"
COVERAGE_AREA_LABEL = "Coverage Area (m²)"
FORMULA_BUILDING_INPUTS_LABEL = "Formula (Building Inputs)"
DIRECT_ENTRY_LABEL = "Direct Entry"

# Formula-column variable name -> the project_info key that variable
# actually resolves to. Building Input widget keys (BUILDING_INPUT_WIDGET_KEYS
# in the Fire Design page) don't match ui_structure's Formula-column
# naming 1:1, so this is the one place that translation happens.
# floor_area_per_storey happens to be spelled the same in both and so
# needs no entry. floor_to_floor_height/exits_per_storey aren't used by
# any current Formula, but are mapped now in case a future formula
# needs them.
BUILDING_INPUT_ALIASES = {
    "number_of_storey": "building_storeys",
    "floor_area_per_storey": "floor_area_per_storey",  # spelled the same in both places
    "effective_height": "building_effective_height",
    "fire_stairs_per_stoery": "building_fire_stairs",  # sic - matches ui_structure's spelling
    "room_number": "building_rooms",
    "floor_to_floor_height": "building_floor_to_floor_height",
    "exits_per_storey": "building_exits_per_storey",
    # Not a Formula-column variable - this is the Condition sheet's
    # "Condition key" value for sprinkler_coverage_area today. Kept
    # here as a synonym purely so a Condition-sheet lookup resolves to
    # the same Building Input as "sprinkler_hazard_classification"
    # would. Fragile: if the Condition sheet ever adds a second
    # differently-spelled key for the same Building Input, or the
    # naming changes, this needs updating by hand - flagged to the
    # team as worth standardizing on one literal name instead.
    "fire_hazard": "sprinkler_hazard_classification",
    "sprinkler_hazard_classification": "sprinkler_hazard_classification",
}

# ==========================================================
# Case classification (Case A/B/C - see _classify_input_case)
# ==========================================================


LINKED_CHILD_MODES = ["Equal to Parent", "Quantity Override"]

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
    quantity_unit="units",
    formula_text=None,
    counted_apparatus=None,
    manual_allowed=True,
    frl_lookup=False,
):
    """
    Declares one component.

    key, label, apparatus, kind : as before

    -- KIND_INPUT --
    modes             : list of mode keys ("grid_spacing"/
                         "coverage_area"; "quantity"/"formula" are
                         parsed for backward compatibility but no
                         longer mean anything - see
                         _classify_input_case) - only consulted for a
                         Case A apparatus, to decide whether the
                         engineer can view/enter its one design
                         parameter as a Grid Spacing side length as
                         well as a raw Coverage Area.
    multi_row         : legacy flag from the "Allow Multiple Rows"
                         column - no longer read by the renderer
                         (every Input component now uses the same
                         table; DTS locks to a single row for Case
                         A/B, Manual Override and Case C always allow
                         adding rows). Kept only so old callers/tests
                         passing it don't break.
    quantity_unit     : the EC database's declared unit for this
                         apparatus (e.g. "kg", "m2", "units") - purely
                         a display label for the Declared Unit(x)
                         column.
    formula_text      : the free-text formula from ui_structure's
                         "Formula" column (or None). Drives which of
                         Case A / B / C this apparatus is - see
                         utils/component_groups.py's
                         _classify_input_case() and
                         utils/formula_engine.py.

    -- KIND_LINKED_CHILD --
    parent_key        : the apparatus label whose quantity this
                         mirrors - can be any Apparatus label already
                         present in the running results list, whether
                         from the same group or elsewhere.
    linked_mode       : "choice" or "override_only"

    -- KIND_CROSS_CATEGORY_COUNTER --
    counted_apparatus : list of Apparatus labels to offer as checkboxes
    manual_allowed    : whether a manual quantity field is also shown

    disclaimer        : optional warning caption shown under the input

    frl_lookup        : (KIND_INPUT) if True, adds a "Required FRL
                         (min)" column to the standardized table, and
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
        "quantity_unit": quantity_unit or "units",
        "formula_text": formula_text,
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

def _empty_multi_row_table(include_frl=False):
    columns = ["Determination Type", "Value", "Product Type", "Declared Unit"]
    if include_frl:
        columns.append("Required FRL (min)")
    return pd.DataFrame(columns=columns)


def init_component_state(spec):
    kind = spec["kind"]

    if kind == KIND_UNAVAILABLE:
        return {}

    if kind == KIND_INPUT:
        # Standardized DTS/Manual Override panel - every Input
        # component (regardless of the ui_structure "Allow Multiple
        # Rows" flag), including FRL-based Wall Assemblies, uses this
        # same table shape. See _render_standardized_input_component.
        return {
            "status": STATUS_NA,
            "table": _empty_multi_row_table(include_frl=spec.get("frl_lookup", False)),
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


def _classify_input_case(spec):
    """
    Classifies a KIND_INPUT apparatus per the three-case model:

      "A" - has a Formula, AND that Formula references exactly one
            variable that ISN'T a Building Input (a "design
            parameter", e.g. smoke_detector_coverage_area, resolved
            from the Condition sheet). DTS auto-computes & locks;
            Manual Override lets the design parameter be entered
            either as Value or back-solved from Declared Unit(x).
      "B" - has a Formula, but it's 100% Building Inputs (e.g. Manual
            Call Points: storeys * fire_stairs). DTS auto-computes &
            locks, same as A; Manual Override is a plain override -
            there's no design parameter to solve for, so Value and
            Declared Unit(x) just mirror each other.
      "C" - no Formula at all yet. Plain typed input under both DTS
            and Manual Override - Value and Declared Unit(x) mirror
            each other. This is the expected state for "EC database,
            no Formula yet" apparatus, and the only case where DTS
            doesn't compute anything. A malformed Formula string
            (fails formula_engine's validation - e.g. a missing
            function wrapper) also degrades to Case C rather than
            crashing the page - see the "malformed" flag below.

    Returns (case, design_parameter_name_or_None, malformed_bool).
    A malformed Formula is a real ui_structure data problem worth
    fixing, not a normal in-progress state like a blank Formula cell -
    callers should surface it rather than silently treating it the
    same as "no Formula yet".
    """
    formula_text = spec.get("formula_text")
    if not formula_text:
        return "C", None, False

    try:
        variables = extract_formula_variables(formula_text)
    except FormulaError:
        return "C", None, True

    design_params = sorted(v for v in variables if v not in BUILDING_INPUT_ALIASES)

    if design_params:
        # Every current Formula has at most one - if a future one ever
        # has more, this takes the first (alphabetically, for
        # determinism) rather than crashing; that apparatus's Formula
        # needs revisiting either way.
        return "A", design_params[0], False

    return "B", None, False


def _resolve_building_inputs(project_info):
    """
    Maps every Formula-column Building Input variable name to its
    current project_info value (via BUILDING_INPUT_ALIASES). Missing/
    unset inputs are simply absent from the returned dict -
    evaluate_formula() treats a missing variable as "can't compute
    yet", not an error.
    """
    project_info = project_info or {}
    variables = {name: project_info.get(key) for name, key in BUILDING_INPUT_ALIASES.items()}
    return {k: v for k, v in variables.items() if v is not None}


def _resolve_design_parameter(design_param_name, project_info):
    """
    Resolves a Case A apparatus's design parameter from the Condition
    sheet - unconditioned if it only has a "default" row, otherwise
    keyed off whichever Building Input the Condition sheet says it
    depends on (e.g. Sprinkler Hazard Classification), read straight
    from the already-set project_info value - never a second selector
    rendered here, since that Building Input is already a single,
    shared, project-level field the engineer sets once.

    Returns (value, note_or_None).
    """
    condition_key = parameter_condition_key(design_param_name)
    condition_value = None
    if condition_key:
        project_key = BUILDING_INPUT_ALIASES.get(condition_key, condition_key)
        condition_value = (project_info or {}).get(project_key)
    return get_condition_value(design_param_name, condition_key, condition_value)


def _value_to_design_param(determination_label, value):
    """Converts a Determination-Type-labelled Value cell into the raw
    design-parameter number the formula actually uses. Grid Spacing is
    entered as a side length; the formula wants the area."""
    if value is None:
        return None
    if determination_label == GRID_SPACING_LABEL:
        return value ** 2
    return value


def _design_param_to_value(determination_label, design_param_value):
    """Inverse of _value_to_design_param - what to display in the
    Value cell for a given raw design-parameter number."""
    if design_param_value is None:
        return None
    if determination_label == GRID_SPACING_LABEL:
        return math.sqrt(design_param_value) if design_param_value > 0 else None
    return design_param_value


def _case_a_determination_options(spec):
    """
    Which of Grid Spacing / Coverage Area this apparatus's Modes
    column offers as a way to view/enter its one design parameter -
    defaults to Coverage Area only if Modes doesn't mention either
    (the raw form the Condition sheet stores values in).
    """
    modes = spec.get("modes") or []
    options = []
    if "grid_spacing" in modes:
        options.append(GRID_SPACING_LABEL)
    if "coverage_area" in modes:
        options.append(COVERAGE_AREA_LABEL)
    return options or [COVERAGE_AREA_LABEL]

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

    # -------- Unavailable --------

    if kind == KIND_UNAVAILABLE:
        if show_label:
            st.markdown(f"**{spec['label']}**")
        st.info(spec.get("disclaimer") or "This is not available.")
        return False

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

    # Every Input component - including FRL-based Wall Assemblies -
    # now uses the same standardized N/A / DTS / Manual Override
    # table.
    return _render_standardized_input_component(
        spec, comp_state, apparatus_output_df, project_info, key_prefix, show_label,
        frl_reference_df=frl_reference_df,
    )


def _approx_equal(a, b, tol=1e-9):
    if a is None or b is None:
        return a is b
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if pd.isna(fa) or pd.isna(fb):
        return pd.isna(fa) and pd.isna(fb)
    return math.isclose(fa, fb, rel_tol=tol, abs_tol=tol)


def _blank(v):
    return v is None or (isinstance(v, float) and pd.isna(v))


def _frl_options_all_products(frl_reference_df, apparatus_output_df, spec):
    """
    Every "Required FRL (min)" value valid for at least one Product
    Type of this apparatus (e.g. Plasterboard's board-thickness table
    varies by Product Type). A data-table's Selectbox column can't
    offer per-row options conditioned on that row's own Product Type
    the way a single free-standing selector could, so this offers the
    union of everything valid for any Product Type - the actual
    Product Type + FRL combination for each row is re-validated at
    Calculate time (_apply_frl_lookup): a row pairing an FRL with a
    Product Type that doesn't actually support it gets a warning and
    is excluded, rather than silently mispriced.
    """
    apparatus = spec["apparatus"]
    options = set(get_frl_options(frl_reference_df, apparatus, None))
    for product in get_available_product_types(apparatus_output_df, apparatus):
        options.update(get_frl_options(frl_reference_df, apparatus, product))
    return sorted(options)


def _sync_value_declared_unit(edited, prev_table, case, spec, design_param_name, building_inputs):
    """
    Two-way sync between the Value and Declared Unit(x) columns after
    an edit, matching rows to their previous state by position:

      - Case A: whichever column the engineer just typed into drives
        the other, through the real Formula (Declared Unit(x) ->
        Value back-solves numerically via
        formula_engine.solve_formula_for_variable).
      - Case B/C: no design parameter to solve for - the two columns
        are a plain 1:1 mirror of each other.

    If both columns changed at once on the same row (e.g. a paste, or
    a brand-new row where neither has a previous value to diff
    against), Value is treated as the one that drives Declared Unit(x).
    Mutates and returns `edited`.
    """
    for i in edited.index:
        det_label = edited.at[i, "Determination Type"]
        value = edited.at[i, "Value"]
        declared = edited.at[i, "Declared Unit"]

        prev_value = prev_declared = None
        if prev_table is not None and i in prev_table.index:
            prev_value = prev_table.at[i, "Value"]
            prev_declared = prev_table.at[i, "Declared Unit"]

        value_changed = not _approx_equal(value, prev_value)
        declared_changed = not _approx_equal(declared, prev_declared)

        if _blank(value) and _blank(declared):
            continue

        if case in ("B", "C"):
            if declared_changed and not value_changed:
                edited.at[i, "Value"] = declared
            else:
                edited.at[i, "Declared Unit"] = value
            continue

        # Case A - real back-solve through the Formula.
        if declared_changed and not value_changed and not _blank(declared):
            solved = solve_formula_for_variable(
                spec["formula_text"], building_inputs, design_param_name, float(declared),
            )
            if solved is not None:
                edited.at[i, "Value"] = _design_param_to_value(det_label, solved)
        else:
            design_param = _value_to_design_param(det_label, value)
            variables = dict(building_inputs)
            if design_param is not None:
                variables[design_param_name] = design_param
            computed = evaluate_formula(spec["formula_text"], variables)
            if computed is not None:
                edited.at[i, "Declared Unit"] = computed

    return edited


def _render_standardized_input_component(spec, comp_state, apparatus_output_df, project_info, key_prefix, show_label,
                                          frl_reference_df=None):
    """
    Standardized N/A / DTS / Manual Override panel used by every Input
    component, including FRL-based Wall Assemblies. Always the same 4
    columns - Determination Type / Value / Product Type / Declared
    Unit(x) - plus Required FRL (min) for Wall Assemblies.

    Which of Case A / B / C this apparatus is (see
    _classify_input_case) decides Determination Type's options and
    how Value/Declared Unit(x) relate - never a different table shape:

      Case A (Formula + one design parameter, e.g. Smoke Detectors):
        Determination Type offers Grid Spacing / Coverage Area (which
        unit to view/enter the design parameter in - the same
        parameter either way). DTS resolves the parameter from the
        Condition sheet + Building Inputs and locks the row (single
        row, nothing else to add). Manual Override lets either Value
        or Declared Unit(x) be typed, back-solving the other through
        the real Formula.
      Case B (Formula, but 100% Building Inputs, e.g. Manual Call
        Points): Determination Type is fixed to "Formula (Building
        Inputs)". DTS locks the row the same way as Case A. Manual
        Override is a plain override - Value and Declared Unit(x)
        just mirror each other, since there's no design parameter to
        solve for.
      Case C (no Formula yet): Determination Type is fixed to "Direct
        Entry". DTS is plain typed input too (nothing to compute yet)
        - Value and Declared Unit(x) mirror each other under both
        statuses, and the table stays a normal add/remove-rows table.

    DTS (Case A/B) starts as a single locked, auto-computed row - the
    correct answer with zero typing. Adding a row (the same "+"
    control every apparatus's table has) unlocks the whole table,
    since there's no way to keep one row read-only while another is
    editable in the same column - at that point splitting the total
    across several Product Types becomes the engineer's own typing,
    the same as Manual Override, while the row stays labelled DTS.
    Deleting back down to one row re-locks it to the auto-computed
    figure.
    """

    dirty = False

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
            format_func=lambda s: STATUS_DISPLAY_LABELS.get(s, s),
        )

    if new_status != comp_state.get("status"):
        comp_state["status"] = new_status
        dirty = True

    if comp_state["status"] == STATUS_NA:
        if spec.get("disclaimer"):
            st.caption(f"⚠️ {spec['disclaimer']}")
        _render_info_panel(spec)
        return dirty

    case, design_param_name, malformed = _classify_input_case(spec)
    if malformed:
        st.caption(
            f"⚠️ This apparatus's Formula in ui_structure couldn't be parsed - treating it as "
            f"'no Formula yet' for now. Raw text: `{spec.get('formula_text')}`"
        )
    is_dts = comp_state["status"] == STATUS_DTS
    single_row = len(comp_state["table"]) <= 1
    locked = is_dts and case in ("A", "B") and single_row

    if case == "A":
        det_options = _case_a_determination_options(spec)
    elif case == "B":
        det_options = [FORMULA_BUILDING_INPUTS_LABEL]
    else:
        det_options = [DIRECT_ENTRY_LABEL]

    product_options = get_available_product_types(apparatus_output_df, spec["apparatus"])
    building_inputs = _resolve_building_inputs(project_info)

    table = comp_state["table"]
    if not table.index.equals(pd.RangeIndex(len(table))):
        table = table.reset_index(drop=True)
        comp_state["table"] = table

    if locked:
        # DTS, Case A/B, exactly one row so far: auto-computed,
        # read-only. Adding a row (the "+" control below, same as
        # every other apparatus's table) unlocks the whole table for
        # manual splitting across Product Types - see the note on
        # `locked` above.
        existing = table.iloc[0] if not table.empty else {}
        det_label = existing.get("Determination Type") if existing.get("Determination Type") in det_options else det_options[0]
        product_type = existing.get("Product Type")

        if case == "A":
            design_value, source_note = _resolve_design_parameter(design_param_name, project_info)
            value_display = _design_param_to_value(det_label, design_value)
            variables = dict(building_inputs)
            if design_value is not None:
                variables[design_param_name] = design_value
            declared_unit = evaluate_formula(spec["formula_text"], variables)
        else:
            source_note = None
            declared_unit = evaluate_formula(spec["formula_text"], building_inputs)
            value_display = declared_unit

        row = {"Determination Type": det_label, "Value": value_display, "Product Type": product_type,
               "Declared Unit": declared_unit}
        if spec.get("frl_lookup") and "Required FRL (min)" in table.columns:
            row["Required FRL (min)"] = existing.get("Required FRL (min)")
        table = pd.DataFrame([row], columns=table.columns)
        comp_state["table"] = table

        if declared_unit is None:
            st.caption(
                "⏳ Not yet computed - fill in the Additional Building Inputs "
                + ("and the Condition sheet entry for this apparatus " if case == "A" else "")
                + "for this to auto-fill."
            )
        elif source_note:
            st.caption(f"DTS source: {source_note}")

    column_config = {
        "Determination Type": st.column_config.SelectboxColumn(
            "Determination Type", options=det_options, required=True,
            disabled=locked or len(det_options) <= 1, default=det_options[0],
        ),
        "Value": st.column_config.NumberColumn("Value", min_value=0.0, required=False, disabled=locked),
        "Product Type": st.column_config.SelectboxColumn(
            "Product Type",
            options=product_options if product_options else ["No products found"],
            required=False,
        ),
        "Declared Unit": st.column_config.NumberColumn(
            f"Declared Unit ({spec.get('quantity_unit', 'units')})", min_value=0.0, required=False, disabled=locked,
        ),
    }

    show_frl = bool(spec.get("frl_lookup"))
    if show_frl:
        frl_values = _frl_options_all_products(frl_reference_df, apparatus_output_df, spec)
        column_config["Required FRL (min)"] = st.column_config.SelectboxColumn(
            "Required FRL (min)",
            options=[str(f) for f in frl_values] if frl_values else ["No FRL data found"],
            required=False,
        )

    prev_table = comp_state["table"]

    edited = st.data_editor(
        comp_state["table"], width='stretch', hide_index=True,
        num_rows="dynamic", column_config=column_config,
        key=f"{key_prefix}_{spec['key']}_table",
    )
    edited = edited.reset_index(drop=True)

    row_count_changed = len(edited) != len(prev_table)

    synced_something_new = False
    if not locked:
        before_sync = edited.copy()
        edited = _sync_value_declared_unit(edited, prev_table, case, spec, design_param_name, building_inputs)
        synced_something_new = not edited.equals(before_sync)

    if not edited.equals(comp_state["table"]):
        comp_state["table"] = edited
        dirty = True
        if synced_something_new or row_count_changed:
            # Without this, the synced Value/Declared Unit only shows
            # up after the *next* edit - st.data_editor already told
            # the browser what to draw for this rerun before the sync
            # above ran, so the freshly-computed number sits correctly
            # in comp_state but isn't visible until something forces
            # another pass. This makes that pass happen immediately.
            st.rerun()

    if case == "C" and is_dts:
        st.caption("No Formula configured yet for this apparatus - DTS is a plain typed figure for now.")
    elif case == "A":
        st.caption(
            "Grid Spacing and Coverage Area are the same design parameter, just entered in a different unit."
            + (" Type either Value or Declared Unit - the other back-solves." if not locked else "")
        )
    elif case == "B" and not locked:
        st.caption("This apparatus has no separate design parameter - Value and Declared Unit always match.")

    if spec.get("disclaimer"):
        st.caption(f"⚠️ {spec['disclaimer']}")

    _render_info_panel(spec)

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

    Input archetype (the common case - Smoke Detectors etc., and now
    every standardized DTS/Manual Override table apparatus too, e.g.
    Sprinkler Heads) is a thin pass-through: render_component() now
    owns its own N/A / DTS / PBD status control and collapses itself
    to one line when N/A, so there's nothing extra to do here.

    Any other standalone archetype (Linked Child / Counter) doesn't
    have that built-in collapse, so it keeps the older arrow-expand
    wrapper as a fallback. state = {"expanded": bool, "component": {...}}.
    """

    if spec["kind"] == KIND_INPUT:
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


def _calculate_standardized_row(spec, row, apparatus_output_df, warnings, frl_reference_df=None):
    """
    Prices one row of the standardized Determination Type / Value /
    Product Type / Declared Unit(x) table.

    The quantity priced against the carbon factor is always Declared
    Unit(x) - never Value. For Case A, Value is only the design
    parameter (e.g. a coverage area), not a priceable quantity; for
    Case B/C, Value and Declared Unit(x) are already mirrored to the
    same number, so it makes no difference which is read - Declared
    Unit(x) is the one consistent source across every case.
    """
    quantity = row.get("Declared Unit")
    product_type_name = row.get("Product Type")

    if quantity is None or (isinstance(quantity, float) and pd.isna(quantity)) or quantity <= 0:
        return None

    if spec.get("frl_lookup"):
        frl_min = None
        raw_frl = row.get("Required FRL (min)")
        if raw_frl is not None and str(raw_frl).strip() and not (isinstance(raw_frl, float) and pd.isna(raw_frl)):
            try:
                frl_min = int(float(raw_frl))
            except (TypeError, ValueError):
                frl_min = None
        frl_result = _apply_frl_lookup(spec, quantity, product_type_name, frl_reference_df, frl_min, warnings)
        if frl_result is None:
            return None
        carbon_quantity, frl_detail = frl_result
        return _finalize_result(
            spec, quantity, product_type_name, apparatus_output_df, warnings,
            carbon_quantity=carbon_quantity, frl_min=frl_min, frl_detail=frl_detail,
        )

    return _finalize_result(spec, quantity, product_type_name, apparatus_output_df, warnings)


def _consolidate_by_product_type(results):
    """
    Merges result rows that share the same Product Type (and the same
    Required FRL (min), for Wall Assemblies, since a different FRL is
    a genuinely different construction, not a duplicate) into one
    combined line - Quantity and every carbon column summed together.

    This is what makes adding a row about splitting across DIFFERENT
    Product Types (the actual point of the "+" control), rather than
    something that also lets the same Product Type appear as two
    separate near-identical lines if a row gets split for no reason,
    or if a DTS split (see _render_standardized_input_component)
    happens to land two rows on the same product. Order of first
    appearance is preserved.
    """
    merged = {}
    order = []

    for r in results:
        key = (r["Product Type"], r.get("Required FRL (min)"))
        if key not in merged:
            merged[key] = dict(r)
            order.append(key)
        else:
            existing = merged[key]
            existing["Quantity"] = (existing.get("Quantity") or 0) + (r.get("Quantity") or 0)
            for field in ("A1-A3", "A4", "A5", "Total"):
                existing[field] = (existing.get(field) or 0) + (r.get(field) or 0)
            # SpacingArea/FRL Basis etc. aren't meaningfully summable -
            # whichever row hit this Product Type first keeps its value.

    return [merged[key] for key in order]


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

    if kind == KIND_UNAVAILABLE:
        return []

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

    # KIND_INPUT (standardized N/A / DTS / Manual Override table -
    # see _render_standardized_input_component; applies to every
    # Input component, including FRL-based Wall Assemblies, regardless
    # of the ui_structure "Allow Multiple Rows" flag)

    if comp_state.get("status", STATUS_NA) == STATUS_NA:
        return []

    table = comp_state.get("table")
    if table is None or table.empty:
        return []

    results = []
    for _, row in table.iterrows():
        result = _calculate_standardized_row(spec, row, apparatus_output_df, warnings, frl_reference_df=frl_reference_df)
        if result:
            results.append(result)
    return _consolidate_by_product_type(results)


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

        if kind == KIND_UNAVAILABLE:
            rows.append({
                "Category": cat_name, "Subcategory": spec["label"],
                "Status": "Unavailable", "Determination Type": None,
                "Value": None, "Product Type": None, "Hazard Rating": None,
            })

        elif kind == KIND_LINKED_CHILD:
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
            # Standardized table shape - one row per N/A status, or
            # one row per configured table entry under DTS/Manual
            # Override. "Value" here is the design parameter (Case A)
            # or matches "Declared Unit" (Case B/C) - "Declared Unit"
            # is always the quantity actually priced.
            status = comp_state.get("status", STATUS_NA)
            if status == STATUS_NA:
                rows.append({
                    "Category": cat_name, "Subcategory": spec["label"], "Status": STATUS_NA,
                    "Determination Type": None, "Value": None, "Product Type": None,
                    "Declared Unit": None, "Hazard Rating": None,
                })
            else:
                table = comp_state.get("table")
                if table is None or table.empty:
                    rows.append({
                        "Category": cat_name, "Subcategory": spec["label"], "Status": status,
                        "Determination Type": None, "Value": None, "Product Type": None,
                        "Declared Unit": None, "Hazard Rating": None,
                    })
                else:
                    for _, r in table.iterrows():
                        rows.append({
                            "Category": cat_name, "Subcategory": spec["label"], "Status": status,
                            "Determination Type": r.get("Determination Type"),
                            "Value": r.get("Value"),
                            "Declared Unit": r.get("Declared Unit"),
                            "Product Type": r.get("Product Type"),
                            "Hazard Rating": None,
                        })
    return rows