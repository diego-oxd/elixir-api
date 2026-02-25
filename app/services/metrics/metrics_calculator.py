import os
from pathlib import Path

from app.models.metrics_schema import MetricResult, SecondaryMeasure
from app.services.metrics.file_walker import IGNORE_DIRS
from app.services.metrics.import_graph import (
    ImportGraph,
    get_density,
    get_isolated,
    get_orphans,
    tarjan_scc,
)
from app.services.metrics.severity import (
    AVG_INSTABILITY_THRESHOLDS,
    FOLDER_NESTING_THRESHOLDS,
    IMPORT_CYCLES_THRESHOLDS,
    ISOLATED_MODULES_THRESHOLDS,
    MAX_CYCLE_LENGTH_THRESHOLDS,
    MODULE_DENSITY_THRESHOLDS,
    ORPHANED_MODULES_THRESHOLDS,
    calculate_severity,
)

# Internal type: (category_name, MetricResult)
CategorizedMetric = tuple[str, MetricResult]


def calculate_folder_nesting(repo_path: str) -> list[CategorizedMetric]:
    root = Path(repo_path)
    all_depths: list[int] = []
    leaf_depths: list[int] = []

    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")
        ]
        try:
            depth = len(Path(dirpath).relative_to(root).parts)
        except ValueError:
            continue

        all_depths.append(depth)
        if not dirnames:
            leaf_depths.append(depth)

    max_depth = max(all_depths) if all_depths else 0
    avg_depth = round(sum(leaf_depths) / len(leaf_depths), 1) if leaf_depths else 0.0

    metric = MetricResult(
        name="Folder Nesting Depth",
        value=max_depth,
        secondary=SecondaryMeasure(value=avg_depth, label="avg depth"),
        severity=calculate_severity(max_depth, FOLDER_NESTING_THRESHOLDS),
        description="Maximum directory depth from the project root, excluding build artifacts",
        thresholdInfo="≤3 excellent, ≤5 good, ≤7 acceptable, ≤10 warning",
    )
    return [("Size Distribution", metric)]


# ---------------------------------------------------------------------------
# Phase 3: Import graph metrics
# ---------------------------------------------------------------------------


def calculate_cyclic_dependencies(graph: ImportGraph) -> list[CategorizedMetric]:
    sccs = tarjan_scc(graph)

    modules_in_cycles: set[str] = set()
    for scc in sccs:
        modules_in_cycles.update(scc)

    cycle_count = len(modules_in_cycles)
    max_cycle_len = max((len(scc) for scc in sccs), default=0)

    details = [
        {"name": mod, "count": len(scc), "countLabel": "hops"}
        for scc in sccs
        for mod in scc
    ][:50]

    metrics = [
        MetricResult(
            name="Import Cycles",
            value=cycle_count,
            severity=calculate_severity(cycle_count, IMPORT_CYCLES_THRESHOLDS),
            description="Number of modules involved in at least one circular import chain",
            thresholdInfo="0 excellent, ≤2 good, ≤5 acceptable, ≤10 warning",
            details=details or None,
        ),
        MetricResult(
            name="Max Cycle Length",
            value=max_cycle_len,
            severity=calculate_severity(max_cycle_len, MAX_CYCLE_LENGTH_THRESHOLDS),
            description="Length in hops of the longest circular import chain found",
            thresholdInfo="0 excellent, ≤2 good, ≤4 acceptable, ≤6 warning",
        ),
    ]
    return [("Cyclic Dependencies", m) for m in metrics]


def calculate_graph_connectivity(graph: ImportGraph) -> list[CategorizedMetric]:
    density = get_density(graph)
    isolated = get_isolated(graph)

    metrics = [
        MetricResult(
            name="Module Graph Density",
            value=density,
            severity=calculate_severity(density, MODULE_DENSITY_THRESHOLDS),
            description="Ratio of import edges to maximum possible edges (0=sparse, 1=fully connected)",
            thresholdInfo="≤0.1 excellent, ≤0.2 good, ≤0.3 acceptable, ≤0.5 warning",
        ),
        MetricResult(
            name="Isolated Modules",
            value=len(isolated),
            severity=calculate_severity(len(isolated), ISOLATED_MODULES_THRESHOLDS),
            description="Modules with no import edges in either direction",
            thresholdInfo="0 excellent, ≤2 good, ≤5 acceptable, ≤10 warning",
            details=[{"name": m} for m in isolated[:50]] or None,
        ),
    ]
    return [("Graph Connectivity", m) for m in metrics]


def calculate_orphaned_modules(graph: ImportGraph) -> list[CategorizedMetric]:
    orphans = get_orphans(graph)

    metric = MetricResult(
        name="Orphaned Modules",
        value=len(orphans),
        severity=calculate_severity(len(orphans), ORPHANED_MODULES_THRESHOLDS),
        description="Modules not imported by any other module and not a known entry point",
        thresholdInfo="0 excellent, ≤2 good, ≤5 acceptable, ≤10 warning",
        details=[{"name": m} for m in orphans[:50]] or None,
    )
    return [("Dead Code", metric)]


def calculate_coupling(graph: ImportGraph) -> list[CategorizedMetric]:
    in_deg = graph.in_degrees()

    instabilities: list[float] = []
    for node in graph.nodes:
        ce = len(graph.edges.get(node, set()))
        ca = in_deg.get(node, 0)
        total = ce + ca
        if total > 0:
            instabilities.append(ce / total)

    avg_i = round(sum(instabilities) / len(instabilities), 3) if instabilities else 0.0
    max_i = round(max(instabilities), 3) if instabilities else 0.0

    metric = MetricResult(
        name="Average Module Instability",
        value=avg_i,
        secondary=SecondaryMeasure(value=max_i, label="max"),
        severity=calculate_severity(avg_i, AVG_INSTABILITY_THRESHOLDS),
        description="Average instability Ce/(Ce+Ca) across all modules. 0=stable, 1=unstable",
        thresholdInfo="≤0.3 excellent, ≤0.5 good, ≤0.7 acceptable, ≤0.85 warning",
    )
    return [("Coupling & Cohesion", metric)]

