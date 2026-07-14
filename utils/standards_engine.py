"""
Standards Calculation Engine

Reads the single-sheet "calc_rules" database and evaluates its
formulas. This is the one place formula syntax is interpreted -
adding a new calculated quantity means adding a row to the
spreadsheet, not writing new Python.

Formula syntax (written in the spreadsheet's "value" column,
prefixed with "="):
    - Variable names refer to whatever is passed into evaluate_formula()
    - Supported functions: SQRT(x), ROUNDUP(x, n), MAX(a, b, ...),
      MIN(a, b, ...), IF(condition, if_true, if_false)
    - Supported operators: + - * / ( )  and comparisons > < >= <= == !=
"""

import ast
import math
import pandas as pd
import streamlit as st
import os

from utils.constants import CALC_RULES_DATABASE_FILE


# ==========================================================
# Loading
# ==========================================================

def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


@st.cache_data
def load_calc_rules(_mtime=None):
    if not CALC_RULES_DATABASE_FILE.exists():
        return pd.DataFrame(
            columns=["system", "component", "parameter", "condition_key", "condition_value", "value", "unit", "notes"]
        )
    return pd.read_excel(CALC_RULES_DATABASE_FILE, sheet_name="calc_rules")


def get_calc_rules():
    return load_calc_rules(_mtime=_file_mtime(CALC_RULES_DATABASE_FILE))


# ==========================================================
# Lookup
# ==========================================================

def get_parameter(system, component, parameter, condition_value=None, default=None):
    """
    Looks up a single parameter's raw value (number or formula
    string) from the calc_rules sheet.

    If condition_value is given, matches rows where condition_value
    equals that value. If not given (or no match), falls back to a
    row with condition_value == "default".
    """

    df = get_calc_rules()

    matches = df[
        (df["system"] == system)
        & (df["component"] == component)
        & (df["parameter"] == parameter)
    ]

    if matches.empty:
        return default

    if condition_value is not None:
        specific = matches[matches["condition_value"] == condition_value]
        if not specific.empty:
            return specific.iloc[0]["value"]

    fallback = matches[matches["condition_value"] == "default"]
    if not fallback.empty:
        return fallback.iloc[0]["value"]

    return matches.iloc[0]["value"]


def get_available_condition_values(system, component, parameter):
    """
    Returns the list of condition_value options available for a
    given parameter - e.g. the hazard classes defined for
    sprinkler_head.spacing_area.
    """
    df = get_calc_rules()

    matches = df[
        (df["system"] == system)
        & (df["component"] == component)
        & (df["parameter"] == parameter)
    ]

    return (
        matches["condition_value"]
        .dropna()
        .astype(str)
        .loc[lambda s: s != "default"]
        .tolist()
    )


# ==========================================================
# Safe Formula Evaluation
# ==========================================================

_ALLOWED_FUNCTIONS = {
    "SQRT": math.sqrt,
    "ROUNDUP": lambda x, n=0: math.ceil(x * (10 ** n)) / (10 ** n),
    "MAX": max,
    "MIN": min,
    "IF": lambda cond, t, f: t if cond else f,
}

_ALLOWED_NODE_TYPES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name,
    ast.Load, ast.Constant, ast.Compare, ast.Add, ast.Sub, ast.Mult,
    ast.Div, ast.USub, ast.UAdd, ast.Gt, ast.Lt, ast.GtE, ast.LtE,
    ast.Eq, ast.NotEq,
)


def _validate_ast(node):
    """
    Walks the parsed formula and raises if it contains anything
    outside a small safe whitelist - prevents a malicious or
    accidental spreadsheet edit from executing arbitrary code.
    """
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_NODE_TYPES):
            raise ValueError(f"Disallowed expression in formula: {type(child).__name__}")
        if isinstance(child, ast.Call):
            if not isinstance(child.func, ast.Name) or child.func.id not in _ALLOWED_FUNCTIONS:
                raise ValueError(f"Disallowed function call in formula: {ast.dump(child)}")


def evaluate_formula(formula_string, variables):
    """
    Evaluates a formula string (e.g. "FORMULA: risers * storeys * height")
    against a dict of variable values. Returns None if any required
    variable is missing or zero/blank, since most of these formulas
    are meaningless with an incomplete input set.

    variables : dict mapping lowercase variable names to numbers
    """

    if not isinstance(formula_string, str) or not formula_string.startswith("FORMULA:"):
        return formula_string  # not a formula, just a plain value

    expression = formula_string[len("FORMULA:"):].strip()

    try:
        tree = ast.parse(expression, mode="eval")
        _validate_ast(tree)
    except (SyntaxError, ValueError):
        return None

    safe_locals = {k.lower(): v for k, v in variables.items()}

    for name_node in ast.walk(tree):
        if isinstance(name_node, ast.Name) and name_node.id not in _ALLOWED_FUNCTIONS:
            if name_node.id not in safe_locals:
                return None  # missing required variable
            if safe_locals[name_node.id] is None:
                return None

    try:
        result = eval(
            compile(tree, "<formula>", "eval"),
            {"__builtins__": {}, **_ALLOWED_FUNCTIONS},
            safe_locals,
        )
    except (ZeroDivisionError, TypeError, ValueError):
        return None

    return result


def calculate_quantity(system, component, parameter, variables, condition_value=None):
    """
    Convenience wrapper: looks up a formula/value and evaluates it
    in one step.
    """
    raw = get_parameter(system, component, parameter, condition_value=condition_value)
    if raw is None:
        return None
    return evaluate_formula(raw, variables)

def get_extinguisher_requirement(hazard_class, fire_class, has_fixed_suppression):
    """
    Returns the minimum acceptable rating and its corresponding
    max-area coverage for a given hazard/fire class/suppression
    combination, read straight from the AS2444 tables in calc_rules.

    fire_class : "A" or "B"
    Returns a dict: {"min_rating": ..., "max_area": ..., "travel_distance": ...}
    or None if no matching row exists.
    """

    min_rating = get_parameter(
        "extinguisher", "portable_extinguisher",
        f"min_rating_class_{fire_class.lower()}",
        condition_value=hazard_class,
    )

    if min_rating is None:
        return None

    suppression_suffix = "with_suppression" if has_fixed_suppression else "no_suppression"

    max_area = get_parameter(
        "extinguisher", "portable_extinguisher",
        f"max_area_class_{fire_class.lower()}_{suppression_suffix}",
        condition_value=f"{hazard_class}|{min_rating}",
    )

    travel_distance = None
    if fire_class.upper() == "B" and not has_fixed_suppression:
        travel_distance = get_parameter(
            "extinguisher", "portable_extinguisher",
            "travel_distance_class_b_no_suppression",
            condition_value=f"{hazard_class}|{min_rating}",
        )

    return {
        "min_rating": min_rating,
        "max_area": max_area,
        "travel_distance": travel_distance,
    }