import ast
import json
import logging
import os
import re
from pathlib import Path

from app.models.metrics_schema import MetricResult, SecondaryMeasure, Severity
from app.services.metrics.ast_extractor import FileStructure
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
    AVG_METHODS_PER_CLASS_THRESHOLDS,
    DEAD_EXPORTS_JS_THRESHOLDS,
    DEAD_FUNCTIONS_PCT_THRESHOLDS,
    DOC_BY_TYPE_THRESHOLDS,
    DOC_COVERAGE_THRESHOLDS,
    FOLDER_NESTING_THRESHOLDS,
    GOD_CLASSES_THRESHOLDS,
    GOD_MODULES_THRESHOLDS,
    IMPORT_CYCLES_THRESHOLDS,
    INHERITANCE_CYCLES_THRESHOLDS,
    ISOLATED_MODULES_THRESHOLDS,
    LOW_QUALITY_DOCS_THRESHOLDS,
    MAX_CYCLE_LENGTH_THRESHOLDS,
    MAX_INHERITANCE_DEPTH_THRESHOLDS,
    MODULE_DENSITY_THRESHOLDS,
    MULTIPLE_INHERITANCE_THRESHOLDS,
    ORPHANED_MODULES_THRESHOLDS,
    calculate_severity,
)

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Phase 4: AST structure metrics
# ---------------------------------------------------------------------------


def calculate_god_classes(structures: list[FileStructure]) -> list[CategorizedMetric]:
    GOD_THRESHOLD = 20
    gods = [
        (cls, struct.path)
        for struct in structures
        for cls in struct.classes
        if cls.method_count > GOD_THRESHOLD
    ]
    count = len(gods)
    max_methods = max((cls.method_count for cls, _ in gods), default=0)
    details = [
        {"name": f"{path.name}::{cls.name}", "count": cls.method_count, "countLabel": "methods"}
        for cls, path in sorted(gods, key=lambda x: -x[0].method_count)[:50]
    ]
    metric = MetricResult(
        name="God Classes",
        value=count,
        secondary=SecondaryMeasure(value=max_methods, label="max methods") if gods else None,
        severity=calculate_severity(count, GOD_CLASSES_THRESHOLDS),
        description="Classes with more than 20 methods — likely doing too much",
        thresholdInfo="0 excellent, ≤1 good, ≤3 acceptable, ≤6 warning",
        details=details or None,
    )
    return [("Size Distribution", metric)]


def calculate_god_modules(structures: list[FileStructure]) -> list[CategorizedMetric]:
    GOD_THRESHOLD = 30
    gods = [s for s in structures if s.top_level_definitions > GOD_THRESHOLD]
    count = len(gods)
    max_defs = max((s.top_level_definitions for s in gods), default=0)
    details = [
        {"name": s.path.name, "count": s.top_level_definitions, "countLabel": "definitions"}
        for s in sorted(gods, key=lambda x: -x.top_level_definitions)[:50]
    ]
    metric = MetricResult(
        name="God Modules",
        value=count,
        secondary=SecondaryMeasure(value=max_defs, label="max definitions") if gods else None,
        severity=calculate_severity(count, GOD_MODULES_THRESHOLDS),
        description="Files with more than 30 top-level definitions — likely doing too much",
        thresholdInfo="0 excellent, ≤1 good, ≤3 acceptable, ≤6 warning",
        details=details or None,
    )
    return [("Size Distribution", metric)]


def calculate_avg_methods(structures: list[FileStructure]) -> list[CategorizedMetric]:
    all_classes = [cls for s in structures for cls in s.classes]
    if all_classes:
        avg = round(sum(c.method_count for c in all_classes) / len(all_classes), 1)
        max_methods = max(c.method_count for c in all_classes)
    else:
        avg, max_methods = 0.0, 0
    metric = MetricResult(
        name="Avg Methods per Class",
        value=avg,
        secondary=SecondaryMeasure(value=max_methods, label="max"),
        severity=calculate_severity(avg, AVG_METHODS_PER_CLASS_THRESHOLDS),
        description="Average number of methods per class across all source files",
        thresholdInfo="≤7 excellent, ≤10 good, ≤15 acceptable, ≤20 warning",
    )
    return [("Size Distribution", metric)]


def calculate_inheritance(structures: list[FileStructure]) -> list[CategorizedMetric]:
    # Build inheritance map from Python files only (lizard doesn't expose bases for JS/TS)
    inheritance: dict[str, list[str]] = {
        cls.name: cls.bases
        for s in structures
        if s.language == "python"
        for cls in s.classes
    }

    # Max inheritance depth via DFS with memoization
    depths: dict[str, int] = {}

    def get_depth(cls_name: str, visiting: frozenset[str]) -> int:
        if cls_name in depths:
            return depths[cls_name]
        if cls_name not in inheritance or cls_name in visiting:
            return 0
        visiting = visiting | {cls_name}
        base_depths = [get_depth(b, visiting) for b in inheritance[cls_name]]
        d = max(base_depths) + 1 if base_depths else 0
        depths[cls_name] = d
        return d

    all_depths = [get_depth(name, frozenset()) for name in inheritance]
    max_depth = max(all_depths, default=0)
    avg_depth = round(sum(all_depths) / len(all_depths), 1) if all_depths else 0.0

    # Multiple inheritance: Python classes with more than one parent
    multi = [
        (name, bases) for name, bases in inheritance.items() if len(bases) > 1
    ]

    metrics = [
        MetricResult(
            name="Max Inheritance Depth",
            value=max_depth,
            secondary=SecondaryMeasure(value=avg_depth, label="avg depth"),
            severity=calculate_severity(max_depth, MAX_INHERITANCE_DEPTH_THRESHOLDS),
            description="Longest inheritance chain; deep chains make code harder to follow",
            thresholdInfo="≤2 excellent, ≤3 good, ≤5 acceptable, ≤7 warning",
        ),
        MetricResult(
            name="Multiple Inheritance",
            value=len(multi),
            severity=calculate_severity(len(multi), MULTIPLE_INHERITANCE_THRESHOLDS),
            description="Classes with more than one parent (Python only — JS/TS not included)",
            thresholdInfo="0 excellent, ≤2 good, ≤5 acceptable, ≤10 warning",
            details=[
                {"name": name, "count": len(bases), "countLabel": "parents"}
                for name, bases in sorted(multi, key=lambda x: -len(x[1]))[:50]
            ] or None,
        ),
    ]
    return [("Inheritance", m) for m in metrics]


# ---------------------------------------------------------------------------
# Phase 5: Documentation metrics
# ---------------------------------------------------------------------------


def calculate_documentation(structures: list[FileStructure]) -> list[CategorizedMetric]:
    """Overall Doc Coverage, Documentation by Type, Low Quality Docstrings."""
    type_total: dict[str, int] = {"Module": 0, "Class": 0, "Function": 0, "Method": 0}
    type_documented: dict[str, int] = {"Module": 0, "Class": 0, "Function": 0, "Method": 0}
    low_quality: list[dict] = []

    for struct in structures:
        # Module docstrings — Python only
        if struct.language == "python":
            type_total["Module"] += 1
            doc = struct.docstrings.get("module")
            if doc and doc.strip():
                type_documented["Module"] += 1
                if len(doc.strip()) < 30:
                    low_quality.append(
                        {
                            "name": struct.path.name,
                            "kind": "Module",
                            "count": len(doc.strip()),
                            "countLabel": "chars",
                        }
                    )

        for cls in struct.classes:
            type_total["Class"] += 1
            doc = struct.docstrings.get(f"class:{cls.name}")
            if doc and doc.strip():
                type_documented["Class"] += 1
                if len(doc.strip()) < 30:
                    low_quality.append(
                        {
                            "name": cls.name,
                            "kind": "Class",
                            "count": len(doc.strip()),
                            "countLabel": "chars",
                        }
                    )

        for fn in struct.functions:
            if fn.is_method:
                kind = "Method"
                doc_key = f"func:{fn.class_name}.{fn.name}"
                entity_name = f"{fn.class_name}.{fn.name}"
            else:
                kind = "Function"
                doc_key = f"func:{fn.name}"
                entity_name = fn.name

            type_total[kind] += 1
            doc = struct.docstrings.get(doc_key)
            if doc and doc.strip():
                type_documented[kind] += 1
                if len(doc.strip()) < 30:
                    low_quality.append(
                        {
                            "name": entity_name,
                            "kind": kind,
                            "count": len(doc.strip()),
                            "countLabel": "chars",
                        }
                    )

    total = sum(type_total.values())
    documented = sum(type_documented.values())
    coverage = round(documented / total * 100, 1) if total > 0 else 100.0

    type_breakdowns = sorted(
        [
            {
                "entityType": t,
                "total": type_total[t],
                "documented": type_documented[t],
                "coverage": round(type_documented[t] / type_total[t] * 100, 1)
                if type_total[t] > 0
                else 100.0,
            }
            for t in ("Module", "Class", "Function", "Method")
            if type_total[t] > 0
        ],
        key=lambda x: x["coverage"],  # worst-first
    )
    worst_type_coverage = type_breakdowns[0]["coverage"] if type_breakdowns else 100.0

    lq_count = len(low_quality)
    avg_lq_len = (
        round(sum(d["count"] for d in low_quality) / lq_count, 1) if low_quality else 0.0
    )

    metrics = [
        MetricResult(
            name="Overall Documentation Coverage",
            value=coverage,
            secondary=SecondaryMeasure(value=documented, label="documented"),
            severity=calculate_severity(coverage, DOC_COVERAGE_THRESHOLDS, higher_is_better=True),
            description="Percentage of functions, classes, methods, and modules with docstrings or JSDoc",
            thresholdInfo="≥80 excellent, ≥60 good, ≥40 acceptable, ≥20 warning",
        ),
        MetricResult(
            name="Documentation by Type",
            value=round(worst_type_coverage, 1),
            severity=calculate_severity(
                worst_type_coverage, DOC_BY_TYPE_THRESHOLDS, higher_is_better=True
            ),
            description="Documentation coverage by entity type — worst type drives severity",
            thresholdInfo="≥70 excellent, ≥50 good, ≥30 acceptable, ≥15 warning",
            details=type_breakdowns or None,
        ),
        MetricResult(
            name="Low Quality Docstrings",
            value=lq_count,
            secondary=SecondaryMeasure(value=avg_lq_len, label="avg chars") if low_quality else None,
            severity=calculate_severity(lq_count, LOW_QUALITY_DOCS_THRESHOLDS),
            description="Docstrings or JSDoc comments shorter than 30 characters — likely placeholder or too brief",
            thresholdInfo="0 excellent, ≤5 good, ≤15 acceptable, ≤30 warning",
            details=sorted(low_quality, key=lambda x: x["count"])[:50] or None,
        ),
    ]
    return [("Documentation Quality", m) for m in metrics]


def calculate_inheritance_cycles(structures: list[FileStructure]) -> list[CategorizedMetric]:
    """Detect circular inheritance chains by running Tarjan SCC on the class hierarchy."""
    from app.services.metrics.import_graph import ImportGraph, tarjan_scc

    graph = ImportGraph()
    for struct in structures:
        if struct.language != "python":
            continue  # lizard doesn't expose base classes for JS/TS
        for cls in struct.classes:
            graph.add_node(cls.name)
            for base in cls.bases:
                graph.add_edge(cls.name, base)

    sccs = tarjan_scc(graph)
    cycle_count = sum(len(scc) for scc in sccs)

    details = [
        {"name": cls, "count": len(scc), "countLabel": "hops"}
        for scc in sccs
        for cls in scc
    ][:50]

    metric = MetricResult(
        name="Inheritance Cycles",
        value=cycle_count,
        severity=calculate_severity(cycle_count, INHERITANCE_CYCLES_THRESHOLDS),
        description="Classes involved in circular inheritance chains — always indicates a design error",
        thresholdInfo="0 excellent (any cycle is critical)",
        details=details or None,
    )
    return [("Cyclic Dependencies", metric)]


# ---------------------------------------------------------------------------
# Phase 6: Dead code detection
# ---------------------------------------------------------------------------

# Names that are entry points or framework-reserved — never flag as dead code
_DEAD_CODE_EXCLUDE_NAMES = frozenset({
    "main", "run", "handler", "manage", "setup", "teardown",
    "configure", "init", "initialize", "startup", "shutdown",
    "create_app", "get_app", "app", "application",
})
# Callback-style name prefixes — unreferenced by design (event handlers, hooks, etc.)
_CALLBACK_PREFIXES = ("on_", "handle_", "callback_", "dispatch_", "event_", "listener_")

_DUNDER_RE = re.compile(r"^__\w+__$")
_TEST_RE = re.compile(r"^(test_|_test|setUp|tearDown|setUpClass|tearDownClass)")
_VULTURE_RE = re.compile(
    r"^(?P<path>.+):(?P<lineno>\d+): unused (?:function|method) '(?P<name>[^']+)'"
)


def _is_dead_code_excluded(name: str) -> bool:
    return bool(
        _DUNDER_RE.match(name)
        or _TEST_RE.match(name)
        or name.lower() in _DEAD_CODE_EXCLUDE_NAMES
    )


def _is_callback(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(p) for p in _CALLBACK_PREFIXES)


def _count_python_functions(python_files: list[Path]) -> int:
    """Count all function/method definitions across Python files."""
    total = 0
    for f in python_files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total += 1
        except (SyntaxError, OSError):
            continue
    return total


def calculate_dead_code_python(
    repo_path: str, python_files: list[Path]
) -> list[CategorizedMetric]:
    """Run vulture and classify unused Python functions."""
    from app.services.metrics.tool_runner import run_tool

    stdout, stderr, returncode = run_tool(
        ["vulture", repo_path, "--min-confidence", "80"],
        cwd=repo_path,
        timeout=120,
    )

    # vulture exits 1 when it finds issues (not an error); empty stdout = real failure
    if not stdout.strip() and returncode != 0:
        logger.warning("[metrics] vulture failed: %s", stderr[:200])
        return []

    dead_funcs: list[dict] = []
    callback_funcs: list[dict] = []

    for raw_line in stdout.splitlines():
        m = _VULTURE_RE.match(raw_line.strip())
        if not m:
            continue
        name = m.group("name")
        if _is_dead_code_excluded(name):
            continue
        entry = {"name": name, "filePath": m.group("path")}
        if _is_callback(name):
            callback_funcs.append(entry)
        else:
            dead_funcs.append(entry)

    total_fns = _count_python_functions(python_files)
    dead_count = len(dead_funcs)
    dead_pct = round(dead_count / total_fns * 100, 1) if total_fns > 0 else 0.0

    metrics = [
        MetricResult(
            name="Potentially Dead Functions",
            value=dead_count,
            secondary=SecondaryMeasure(value=dead_pct, label="% of total") if total_fns > 0 else None,
            severity=calculate_severity(dead_pct, DEAD_FUNCTIONS_PCT_THRESHOLDS),
            description="Python functions flagged by vulture as likely unused (≥80% confidence), excluding tests, dunders, and known entry points",
            thresholdInfo="≤5% excellent, ≤10% good, ≤20% acceptable, ≤30% warning",
            details=[{"name": d["name"], "filePath": d["filePath"]} for d in dead_funcs[:50]] or None,
        ),
        MetricResult(
            name="Anonymous/Callback Functions",
            value=len(callback_funcs),
            severity=Severity.EXCELLENT,
            description="Vulture-flagged functions matching callback patterns (on_, handle_, etc.) — expected to be registered or called indirectly",
            thresholdInfo="Always excellent — callback-named functions are intentionally unreferenced statically",
            details=[{"name": d["name"]} for d in callback_funcs[:50]] or None,
        ),
    ]
    return [("Dead Code", m) for m in metrics]


def _find_js_package_roots(repo_path: str) -> list[Path]:
    """Find directories with package.json, skipping node_modules and build dirs."""
    root = Path(repo_path)
    roots: list[Path] = []
    for pkg in root.rglob("package.json"):
        if any(part in IGNORE_DIRS for part in pkg.parts):
            continue
        roots.append(pkg.parent)
    return roots


def _parse_knip_issues(stdout: str, dead_exports: list, callback_exports: list) -> None:
    """Parse knip JSON output and populate dead/callback export lists in-place."""
    # knip sometimes outputs error text to stdout before or instead of JSON
    stripped = stdout.strip()
    json_start = next((i for i, c in enumerate(stripped) if c in "{["), -1)
    if json_start < 0:
        logger.info("[metrics] knip produced no JSON output (skipping)")
        return
    try:
        data = json.loads(stripped[json_start:])
    except json.JSONDecodeError as e:
        logger.info("[metrics] knip output could not be parsed: %s", e)
        return

    issues: list = []
    if isinstance(data, dict):
        raw = data.get("issues", [])
        issues = list(raw.values()) if isinstance(raw, dict) else raw
    elif isinstance(data, list):
        issues = data

    for file_issues in issues:
        if not isinstance(file_issues, dict):
            continue
        file_path = file_issues.get("file", "")

        for key in ("exports", "types", "nsExports", "nsTypes"):
            for item in file_issues.get(key, []):
                name = item.get("name", "") if isinstance(item, dict) else str(item)
                if not name or _is_dead_code_excluded(name):
                    continue
                entry = {"name": name, "filePath": file_path}
                (callback_exports if _is_callback(name) else dead_exports).append(entry)

        for members in file_issues.get("classMembers", {}).values():
            if not isinstance(members, list):
                continue
            for item in members:
                name = item.get("name", "") if isinstance(item, dict) else str(item)
                if not name or _is_dead_code_excluded(name):
                    continue
                entry = {"name": name, "filePath": file_path}
                (callback_exports if _is_callback(name) else dead_exports).append(entry)


def calculate_dead_code_js(repo_path: str) -> list[CategorizedMetric]:
    """Run knip from each JS package root and aggregate unused exports."""
    from app.services.metrics.tool_runner import run_tool

    pkg_roots = _find_js_package_roots(repo_path)
    if not pkg_roots:
        logger.info("[metrics] no package.json found anywhere, skipping knip")
        return []

    dead_exports: list[dict] = []
    callback_exports: list[dict] = []

    for pkg_root in pkg_roots[:5]:  # cap at 5 packages to bound runtime
        stdout, stderr, returncode = run_tool(
            ["npx", "--yes", "knip", "--reporter", "json"],
            cwd=str(pkg_root),
            timeout=120,
        )
        if not stdout.strip():
            logger.warning(
                "[metrics] knip no output for %s (rc=%d): %s",
                pkg_root.name, returncode, stderr[:200],
            )
            continue
        _parse_knip_issues(stdout, dead_exports, callback_exports)

    dead_count = len(dead_exports)
    metrics = [
        MetricResult(
            name="Potentially Dead Exports",
            value=dead_count,
            severity=calculate_severity(dead_count, DEAD_EXPORTS_JS_THRESHOLDS),
            description="Unused JS/TS exports and class members detected by knip",
            thresholdInfo="0 excellent, ≤5 good, ≤15 acceptable, ≤30 warning",
            details=[{"name": d["name"], "filePath": d["filePath"]} for d in dead_exports[:50]] or None,
        ),
        MetricResult(
            name="Anonymous/Callback Exports",
            value=len(callback_exports),
            severity=Severity.EXCELLENT,
            description="Unused exports matching callback patterns — expected to be passed or registered indirectly",
            thresholdInfo="Always excellent — callback-named exports are intentionally unreferenced statically",
            details=[{"name": d["name"]} for d in callback_exports[:50]] or None,
        ),
    ]
    return [("Dead Code", m) for m in metrics]
