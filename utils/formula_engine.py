"""
Formula Engine

Evaluates the free-text formulas in ui_structure's "Formula" column
(e.g. "number_of_storey * floor_area_per_storey / smoke_detector_coverage_area",
"MAX (room_number, number_of_storey * floor_area_per_storey / speaker_coverage_area)",
"IF(effective_height > 25, 1 , 0)").

This is the ONLY formula mechanism in the app now - the old calc_rules
system/component/parameter indirection (utils/standards_engine.py's
get_parameter / evaluate_calc_rules_formula / etc.) has been retired
from the standardized Input panel. standards_engine.py itself is left
alone because the hand-built Extinguisher UI in the Fire Design page
still uses its AS2444 hazard/rating tables (get_extinguisher_requirement,
calculate_quantity) - a separate, bespoke feature this rework doesn't
touch.

Design:
  - A formula string is parsed with Python's own `ast` module (NOT
    `eval` on raw text) so it can be validated before anything runs -
    only a small whitelist of node types and function names is
    allowed. Excel/AS-style names read as valid Python syntax already
    (IF/MAX/MIN look like ordinary function calls, comparisons like
    "effective_height > 25" are valid Python), so no text rewriting is
    needed beyond that whitelist check.
  - Supported functions: MAX, MIN, IF(cond, a, b), ROUND, ROUNDUP,
    ROUNDDOWN (Excel-style: rounds away from zero, unlike Python's
    round-half-to-even).
  - A blank/missing formula is NOT handled here - that's a
    component_groups.py policy decision (Case B/C use a Value ==
    Declared Unit identity instead of calling this module at all).
"""

import ast
import math


class FormulaError(Exception):
    """Raised when a formula string fails validation (unknown function,
    disallowed syntax). Never raised for a merely-unresolvable variable -
    that returns None instead, since a project simply not having filled
    in a Building Input yet is an expected, non-exceptional state."""
    pass


def _roundup(value, digits=0):
    factor = 10 ** int(digits)
    if value >= 0:
        return math.ceil(value * factor) / factor
    return math.floor(value * factor) / factor


def _rounddown(value, digits=0):
    factor = 10 ** int(digits)
    if value >= 0:
        return math.floor(value * factor) / factor
    return math.ceil(value * factor) / factor


def _round(value, digits=0):
    return round(value, int(digits))


def _if(condition, if_true, if_false):
    return if_true if condition else if_false


# Function names usable inside a Formula cell, mapped to their Python
# implementation. Add new ones here (and to _ALLOWED_NODES if a new
# kind of syntax is needed) rather than anywhere else.
_FUNCTIONS = {
    "MAX": lambda *args: max(args),
    "MIN": lambda *args: min(args),
    "IF": _if,
    "ROUND": _round,
    "ROUNDUP": _roundup,
    "ROUNDDOWN": _rounddown,
    "SQRT": math.sqrt,
}

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.Call, ast.Name, ast.Load, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
    ast.And, ast.Or,
    ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq,
)


def _parse(formula_text):
    """Parses + validates a formula string, raising FormulaError on
    anything outside the whitelist. Returns the compiled ast tree."""
    text = str(formula_text).strip()
    if text.upper().startswith("FORMULA:"):
        text = text[len("FORMULA:"):].strip()
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Formula text isn't valid syntax: {e}")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise FormulaError(f"Disallowed syntax in formula: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
                func_name = getattr(node.func, "id", None) or ast.dump(node.func)
                raise FormulaError(f"Unknown function in formula: {func_name}")
    return tree


def extract_formula_variables(formula_text):
    """
    Returns the set of bare variable names referenced in a formula
    string (function names like MAX/IF excluded). Used to split a
    formula's variables into "Building Inputs" vs "the one design
    parameter" - see component_groups._classify_input_case.
    """
    if not formula_text or not str(formula_text).strip():
        return set()
    tree = _parse(formula_text)
    return {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in _FUNCTIONS
    }


def evaluate_formula(formula_text, variables):
    """
    Evaluates a Formula-column string against a dict of resolved
    variable values. Returns None (never raises) if the formula is
    blank, a referenced variable is missing/None, or evaluation
    otherwise fails for a reason that isn't a formula-authoring bug -
    e.g. a project that simply hasn't filled in every Building Input
    yet. Raises FormulaError only for a malformed/unsafe formula
    string itself, since that IS worth surfacing loudly (a data-entry
    mistake in ui_structure, not a normal missing-input state).
    """
    if not formula_text or not str(formula_text).strip():
        return None

    tree = _parse(formula_text)

    for name in extract_formula_variables(formula_text):
        if variables.get(name) is None:
            return None

    code = compile(tree, "<formula>", "eval")
    try:
        result = eval(code, {"__builtins__": {}}, {**_FUNCTIONS, **variables})
    except (ZeroDivisionError, ValueError, TypeError, OverflowError):
        return None

    if isinstance(result, bool) or not isinstance(result, (int, float)):
        return None
    return float(result)


def solve_formula_for_variable(formula_text, variables, target_name, target_value,
                                lo=1e-6, hi=1e9, tol=1e-6, max_iter=100):
    """
    Numerically back-solves a formula for one missing variable
    (target_name) given a desired output (target_value) - e.g. "what
    Coverage Area gives exactly 20 detectors?". Used for Manual
    Override's two-way Value <-> Declared Unit(x) entry (Case i /
    "Case A" apparatus).

    Assumes the formula is monotonic in target_name over [lo, hi],
    which holds for every current ui_structure Formula (all are a
    building-input product divided by the design parameter) - plain
    bisection, so it needs no assumption about the *shape* of the
    formula beyond that direction not reversing. Returns None if it
    can't bracket a root (target_value is out of reachable range, or
    the formula doesn't resolve at all) rather than raising, since an
    engineer typing an unreachable number is an expected input, not a
    bug.
    """
    if not formula_text or not str(formula_text).strip():
        return None

    def f(x):
        trial = dict(variables)
        trial[target_name] = x
        value = evaluate_formula(formula_text, trial)
        if value is None:
            return None
        return value - target_value

    f_lo, f_hi = f(lo), f(hi)
    if f_lo is None or f_hi is None:
        return None
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        # Same sign at both ends - target_value isn't bracketed in
        # [lo, hi], so there's no root to find in a sane range.
        return None

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if f_mid is None:
            return None
        if abs(f_mid) < tol or (hi - lo) < tol:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid

    return (lo + hi) / 2