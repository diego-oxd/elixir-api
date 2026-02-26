import logging

from app.db import PostgresDatabase, add_item, get_item_by_composite_key, update_item
from app.models.metrics_schema import MetricsSnapshot
from app.services.metrics.detector import detect_languages
from app.services.metrics.file_walker import discover_files
from app.services.metrics.metrics_calculator import (
    calculate_avg_methods,
    calculate_coupling,
    calculate_cyclic_dependencies,
    calculate_dead_code_js,
    calculate_dead_code_python,
    calculate_documentation,
    calculate_folder_nesting,
    calculate_god_classes,
    calculate_god_modules,
    calculate_graph_connectivity,
    calculate_inheritance,
    calculate_inheritance_cycles,
    calculate_orphaned_modules,
)
from app.services.metrics.snapshot_builder import build_snapshot

logger = logging.getLogger(__name__)


def _run(name: str, fn, results: list) -> None:
    """Run one calculator, log the outcome, swallow exceptions."""
    try:
        items = fn()
        results.extend(items)
        logger.info("[metrics] '%s' → %d metric(s)", name, len(items))
    except Exception:
        logger.exception("[metrics] '%s' failed, skipping", name)


def run_metrics(repo_path: str, project_id: str = "") -> MetricsSnapshot:
    """Run all metric calculators against repo_path and return a MetricsSnapshot.

    No database access — safe to call from CLI or tests.
    """
    files = discover_files(repo_path)
    languages = detect_languages(repo_path)
    logger.info(
        "[metrics] repo=%s languages=%s files=%s",
        repo_path,
        languages,
        {k: len(v) for k, v in files.items()},
    )

    all_categorized: list = []

    # Phase 2: Filesystem
    _run("folder_nesting", lambda: calculate_folder_nesting(repo_path), all_categorized)

    # Phase 3: Import graph (4 metrics sharing one graph)
    _run_import_graph_phase(repo_path, files, languages, all_categorized)

    # Phase 4: AST structure (5 metrics sharing one extraction pass)
    _run_ast_phase(files, all_categorized)

    # Phase 6: Dead code detection
    _run_dead_code_phase(repo_path, files, languages, all_categorized)

    return build_snapshot(project_id, all_categorized)


def _run_import_graph_phase(repo_path: str, files: dict, languages: set, results: list) -> None:
    from app.services.metrics.import_graph import build_combined_graph

    try:
        graph = build_combined_graph(repo_path, files, languages)
        logger.info(
            "[metrics] graph built: %d nodes, %d edges", len(graph.nodes), graph.edge_count
        )
    except Exception:
        logger.exception("[metrics] import graph build failed, skipping phase 3")
        return

    _run("cyclic_dependencies", lambda: calculate_cyclic_dependencies(graph), results)
    _run("graph_connectivity", lambda: calculate_graph_connectivity(graph), results)
    _run("orphaned_modules", lambda: calculate_orphaned_modules(graph), results)
    _run("coupling", lambda: calculate_coupling(graph), results)


def _run_ast_phase(files: dict, results: list) -> None:
    from app.services.metrics.ast_extractor import extract_all

    try:
        structures = extract_all(files)
        logger.info("[metrics] AST extracted: %d file structures", len(structures))
    except Exception:
        logger.exception("[metrics] AST extraction failed, skipping phase 4")
        return

    _run("god_classes", lambda: calculate_god_classes(structures), results)
    _run("god_modules", lambda: calculate_god_modules(structures), results)
    _run("avg_methods", lambda: calculate_avg_methods(structures), results)
    _run("inheritance", lambda: calculate_inheritance(structures), results)
    _run("documentation", lambda: calculate_documentation(structures), results)
    _run("inheritance_cycles", lambda: calculate_inheritance_cycles(structures), results)


def _run_dead_code_phase(repo_path: str, files: dict, languages: set, results: list) -> None:
    if "python" in languages and files.get("python"):
        _run(
            "dead_code_python",
            lambda: calculate_dead_code_python(repo_path, files["python"]),
            results,
        )
    if "js_ts" in languages or "vue" in languages:
        _run("dead_code_js", lambda: calculate_dead_code_js(repo_path), results)


def save_metrics(
    db: PostgresDatabase, project_id: str, snapshot: MetricsSnapshot
) -> None:
    """Persist a MetricsSnapshot to the pages table under name='metrics'."""
    content = snapshot.model_dump(mode="json")
    existing = get_item_by_composite_key(db, "pages", project_id, "metrics")

    if existing:
        update_item(db, "pages", existing["_id"], {"content": content})
        logger.info("[metrics] updated existing page for project %s", project_id)
    else:
        add_item(
            db,
            "pages",
            {
                "project_id": project_id,
                "name": "metrics",
                "title": "Code Quality Metrics",
                "content": content,
                "markdown_content": None,
            },
        )
        logger.info("[metrics] created new page for project %s", project_id)


def generate_metrics(project_id: str, repo_path: str, db: PostgresDatabase) -> None:
    """Orchestrator for the background task: run metrics and save to DB."""
    logger.info("[metrics] starting for project %s, repo: %s", project_id, repo_path)
    try:
        snapshot = run_metrics(repo_path, project_id)
        save_metrics(db, project_id, snapshot)
        logger.info("[metrics] completed for project %s", project_id)
    except Exception:
        logger.exception("[metrics] failed for project %s", project_id)
