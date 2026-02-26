from typing import Union

from app.models.metrics_schema import SEVERITY_SCORES, Severity


def calculate_severity(
    value: Union[int, float],
    thresholds: dict[str, Union[int, float]],
    higher_is_better: bool = False,
) -> Severity:
    """Compute severity from a measured value and threshold breakpoints.

    thresholds maps severity name -> boundary value.
    Keys must be a subset of: "excellent", "good", "acceptable", "warning".
    Anything beyond "warning" is CRITICAL.

    lower_is_better (default): value <= threshold[sev] → that severity.
    higher_is_better: value >= threshold[sev] → that severity.
    """
    order = [Severity.EXCELLENT, Severity.GOOD, Severity.ACCEPTABLE, Severity.WARNING]

    for sev in order:
        boundary = thresholds.get(sev.value)
        if boundary is None:
            continue
        if higher_is_better:
            if value >= boundary:
                return sev
        else:
            if value <= boundary:
                return sev

    return Severity.CRITICAL


def severity_score(sev: Severity) -> int:
    return SEVERITY_SCORES[sev.value]


# ---------------------------------------------------------------------------
# Threshold constants for all 21 metrics
# ---------------------------------------------------------------------------

# Cyclic Dependencies
IMPORT_CYCLES_THRESHOLDS = {"excellent": 0, "good": 2, "acceptable": 5, "warning": 10}
MAX_CYCLE_LENGTH_THRESHOLDS = {"excellent": 0, "good": 2, "acceptable": 4, "warning": 6}
# Inheritance cycles: any is a bug — 0 → excellent, 1+ → critical
INHERITANCE_CYCLES_THRESHOLDS = {"excellent": 0}

# God Classes/Modules
GOD_CLASSES_THRESHOLDS = {"excellent": 0, "good": 1, "acceptable": 3, "warning": 6}
GOD_MODULES_THRESHOLDS = {"excellent": 0, "good": 1, "acceptable": 3, "warning": 6}
HUB_FUNCTIONS_THRESHOLDS = {"excellent": 0, "good": 2, "acceptable": 5, "warning": 10}

# Inheritance Quality
MAX_INHERITANCE_DEPTH_THRESHOLDS = {
    "excellent": 2,
    "good": 3,
    "acceptable": 5,
    "warning": 7,
}
MULTIPLE_INHERITANCE_THRESHOLDS = {
    "excellent": 0,
    "good": 2,
    "acceptable": 5,
    "warning": 10,
}

# Dead Code
DEAD_FUNCTIONS_PCT_THRESHOLDS = {
    "excellent": 5.0,
    "good": 10.0,
    "acceptable": 20.0,
    "warning": 30.0,
}
# Count-based threshold for JS/TS dead exports (knip doesn't give us total function count)
DEAD_EXPORTS_JS_THRESHOLDS = {"excellent": 0, "good": 5, "acceptable": 15, "warning": 30}
ORPHANED_MODULES_THRESHOLDS = {
    "excellent": 0,
    "good": 2,
    "acceptable": 5,
    "warning": 10,
}

# Coupling & Cohesion
AVG_INSTABILITY_THRESHOLDS = {
    "excellent": 0.3,
    "good": 0.5,
    "acceptable": 0.7,
    "warning": 0.85,
}
LOW_COHESION_PCT_THRESHOLDS = {
    "excellent": 10.0,
    "good": 20.0,
    "acceptable": 35.0,
    "warning": 50.0,
}

# Size Distribution
AVG_METHODS_PER_CLASS_THRESHOLDS = {
    "excellent": 7.0,
    "good": 10.0,
    "acceptable": 15.0,
    "warning": 20.0,
}
FOLDER_NESTING_THRESHOLDS = {"excellent": 3, "good": 5, "acceptable": 7, "warning": 10}

# Documentation Quality
DOC_COVERAGE_THRESHOLDS = {"excellent": 80, "good": 60, "acceptable": 40, "warning": 20}
DOC_BY_TYPE_THRESHOLDS = {"excellent": 70, "good": 50, "acceptable": 30, "warning": 15}
UNDOCUMENTED_APIS_THRESHOLDS = {
    "excellent": 0,
    "good": 3,
    "acceptable": 10,
    "warning": 20,
}
LOW_QUALITY_DOCS_THRESHOLDS = {
    "excellent": 0,
    "good": 5,
    "acceptable": 15,
    "warning": 30,
}

# Graph Connectivity
MODULE_DENSITY_THRESHOLDS = {
    "excellent": 0.1,
    "good": 0.2,
    "acceptable": 0.3,
    "warning": 0.5,
}
ISOLATED_MODULES_THRESHOLDS = {
    "excellent": 0,
    "good": 2,
    "acceptable": 5,
    "warning": 10,
}
