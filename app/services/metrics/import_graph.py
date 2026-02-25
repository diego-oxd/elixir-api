import ast
import json
import logging
import sys
from pathlib import Path

from app.services.metrics.tool_runner import run_tool

logger = logging.getLogger(__name__)

_ENTRY_POINTS = {
    "main", "index", "run", "app", "server", "manage",
    "wsgi", "asgi", "setup", "conftest", "__main__", "app",
}

# Directory names that contain migration files — excluded from dead-code checks
# because migrations are standalone by design (run by a framework, not imported).
_MIGRATION_DIRS = {"migrations", "migrate", "alembic", "versions"}


def _is_migration_node(node: str) -> bool:
    """Return True if any path component of the node is a known migration directory."""
    # Handles both dot-notation (app.migrations.0001) and slash-notation (backend/migrations/0001.js)
    parts = {p.lower() for seg in node.split(".") for p in seg.split("/")}
    return bool(parts & _MIGRATION_DIRS)


# ---------------------------------------------------------------------------
# Graph data structure
# ---------------------------------------------------------------------------


class ImportGraph:
    def __init__(self) -> None:
        self.nodes: set[str] = set()
        self.edges: dict[str, set[str]] = {}

    def add_node(self, node: str) -> None:
        self.nodes.add(node)
        self.edges.setdefault(node, set())

    def add_edge(self, src: str, tgt: str) -> None:
        self.add_node(src)
        self.add_node(tgt)
        self.edges[src].add(tgt)

    def merge(self, other: "ImportGraph") -> None:
        for src, targets in other.edges.items():
            for tgt in targets:
                self.add_edge(src, tgt)
        for node in other.nodes:
            self.add_node(node)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self.edges.values())

    def in_degrees(self) -> dict[str, int]:
        result: dict[str, int] = {node: 0 for node in self.nodes}
        for targets in self.edges.values():
            for tgt in targets:
                if tgt in result:
                    result[tgt] += 1
        return result


# ---------------------------------------------------------------------------
# Python import graph builder
# ---------------------------------------------------------------------------


def _path_to_module(path: Path, root: Path) -> tuple[str, bool]:
    """Return (dot.notation.module, is_package)."""
    rel = path.relative_to(root)
    parts = list(rel.parts)
    is_package = parts[-1] == "__init__.py"
    if is_package:
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts), is_package


def _resolve_relative(src: str, is_package: bool, level: int, module: str | None) -> str | None:
    parts = src.split(".")
    n_remove = (level - 1) if is_package else level
    if n_remove > len(parts):
        return None
    base = parts[:-n_remove] if n_remove > 0 else list(parts)
    if module:
        return ".".join(base + module.split("."))
    return ".".join(base) if base else None


def _best_match(target: str, known: set[str]) -> str | None:
    """Find the most specific known module that is a prefix of target."""
    if target in known:
        return target
    parts = target.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in known:
            return prefix
    return None


def build_python_graph(files: list[Path], repo_root: Path) -> ImportGraph:
    graph = ImportGraph()

    module_info: dict[str, bool] = {}
    for f in files:
        mod, is_pkg = _path_to_module(f, repo_root)
        module_info[mod] = is_pkg
        graph.add_node(mod)

    known = set(module_info.keys())
    top_level = {m.split(".")[0] for m in known}

    for f in files:
        src, is_pkg = _path_to_module(f, repo_root)
        try:
            source = f.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            targets: list[str] = []

            if isinstance(node, ast.Import):
                for alias in node.names:
                    targets.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    targets.append(node.module)
                elif node.level > 0:
                    resolved = _resolve_relative(src, is_pkg, node.level, node.module)
                    if resolved:
                        targets.append(resolved)

            for tgt in targets:
                if tgt.split(".")[0] not in top_level:
                    continue
                matched = _best_match(tgt, known)
                if matched and matched != src:
                    graph.add_edge(src, matched)

    return graph


# ---------------------------------------------------------------------------
# JS/TS/Vue import graph builder (via madge)
# ---------------------------------------------------------------------------


def build_js_graph(repo_path: str) -> ImportGraph:
    graph = ImportGraph()

    stdout, stderr, returncode = run_tool(
        ["npx", "--yes", "madge", "--json", "."],
        cwd=repo_path,
        timeout=60,
    )

    if returncode != 0 or not stdout.strip():
        logger.warning("[import_graph] madge failed (rc=%d): %s", returncode, stderr[:300])
        return graph

    try:
        data: dict[str, list[str]] = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.warning("[import_graph] madge returned invalid JSON: %s", e)
        return graph

    for source, targets in data.items():
        graph.add_node(source)
        for tgt in targets:
            graph.add_edge(source, tgt)

    return graph


# ---------------------------------------------------------------------------
# Combined graph (Python + JS in one pass)
# ---------------------------------------------------------------------------


def build_combined_graph(
    repo_path: str, files: dict[str, list[Path]], languages: set[str]
) -> ImportGraph:
    combined = ImportGraph()
    root = Path(repo_path)

    if "python" in languages and files.get("python"):
        logger.info("[import_graph] building Python graph (%d files)", len(files["python"]))
        py_graph = build_python_graph(files["python"], root)
        combined.merge(py_graph)
        logger.info(
            "[import_graph] Python: %d nodes, %d edges", len(py_graph.nodes), py_graph.edge_count
        )

    if ("js_ts" in languages or "vue" in languages) and (
        files.get("js_ts") or files.get("vue")
    ):
        logger.info("[import_graph] building JS/TS graph via madge")
        js_graph = build_js_graph(repo_path)
        combined.merge(js_graph)
        logger.info(
            "[import_graph] JS/TS: %d nodes, %d edges", len(js_graph.nodes), js_graph.edge_count
        )

    return combined


# ---------------------------------------------------------------------------
# Graph algorithms
# ---------------------------------------------------------------------------


def tarjan_scc(graph: ImportGraph) -> list[list[str]]:
    """Return all strongly connected components with size > 1 (cycles)."""
    index_counter = [0]
    stack: list[str] = []
    lowlink: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True

        for w in graph.edges.get(v, set()):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w, False):
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1:
                sccs.append(scc)

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, len(graph.nodes) * 3 + 1000))
    try:
        for v in list(graph.nodes):
            if v not in index:
                strongconnect(v)
    finally:
        sys.setrecursionlimit(old_limit)

    return sccs


def get_density(graph: ImportGraph) -> float:
    n = len(graph.nodes)
    if n < 2:
        return 0.0
    return round(graph.edge_count / (n * (n - 1)), 4)


def get_isolated(graph: ImportGraph) -> list[str]:
    """Modules with zero incoming AND zero outgoing edges, excluding migrations."""
    in_deg = graph.in_degrees()
    return sorted(
        node
        for node in graph.nodes
        if in_deg.get(node, 0) == 0
        and not graph.edges.get(node)
        and not _is_migration_node(node)
    )


def get_orphans(graph: ImportGraph) -> list[str]:
    """Modules with no incoming edges, excluding entry points and package init nodes."""
    in_deg = graph.in_degrees()
    node_list = list(graph.nodes)

    # Package nodes: any node that is a dot-prefix of another node
    package_nodes: set[str] = set()
    for node in node_list:
        prefix = node + "."
        if any(other.startswith(prefix) for other in node_list):
            package_nodes.add(node)

    orphans = []
    for node in node_list:
        if in_deg.get(node, 0) > 0:
            continue
        if node in package_nodes:
            continue
        if _is_migration_node(node):
            continue
        # Last component handles both dot-notation (app.db) and path-notation (src/db.ts)
        base = node.split(".")[-1].split("/")[-1].lower()
        if base in {e.lower() for e in _ENTRY_POINTS}:
            continue
        orphans.append(node)

    return sorted(orphans)
