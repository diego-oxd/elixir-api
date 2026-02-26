import ast
import logging
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import lizard as _lizard

    _LIZARD_AVAILABLE = True
except ImportError:
    _LIZARD_AVAILABLE = False
    logger.warning("[ast_extractor] lizard not installed; JS/TS structure metrics skipped")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ClassInfo:
    name: str
    method_count: int
    bases: list[str]
    line: int


@dataclass
class FunctionInfo:
    name: str
    line: int
    is_method: bool
    class_name: str | None


@dataclass
class FileStructure:
    path: Path
    language: str
    classes: list[ClassInfo] = field(default_factory=list)
    top_level_definitions: int = 0
    functions: list[FunctionInfo] = field(default_factory=list)
    # entity_key -> docstring text or None; populated in Phase 5
    docstrings: dict[str, str | None] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Python extractor
# ---------------------------------------------------------------------------


def _attr_name(node: ast.Attribute) -> str:
    """Reconstruct dotted name from an ast.Attribute node."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def extract_python(file: Path) -> FileStructure:
    try:
        source = file.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return FileStructure(path=file, language="python")

    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []
    docstrings: dict[str, str | None] = {"module": ast.get_docstring(tree)}
    top_level_count = 0

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            top_level_count += 1
            bases: list[str] = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(_attr_name(base))

            methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(child)
                    functions.append(
                        FunctionInfo(
                            name=child.name,
                            line=child.lineno,
                            is_method=True,
                            class_name=node.name,
                        )
                    )
                    docstrings[f"func:{node.name}.{child.name}"] = ast.get_docstring(child)

            classes.append(
                ClassInfo(
                    name=node.name,
                    method_count=len(methods),
                    bases=bases,
                    line=node.lineno,
                )
            )
            docstrings[f"class:{node.name}"] = ast.get_docstring(node)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level_count += 1
            functions.append(
                FunctionInfo(
                    name=node.name,
                    line=node.lineno,
                    is_method=False,
                    class_name=None,
                )
            )
            docstrings[f"func:{node.name}"] = ast.get_docstring(node)

    return FileStructure(
        path=file,
        language="python",
        classes=classes,
        top_level_definitions=top_level_count,
        functions=functions,
        docstrings=docstrings,
    )


# ---------------------------------------------------------------------------
# JS/TS/Vue extractor (lizard-based)
# ---------------------------------------------------------------------------


def _extract_script_block(vue_source: str) -> tuple[str, str]:
    """Return (script_content, extension) from a Vue SFC.

    Handles <script>, <script setup>, and lang attributes.
    Extension is '.ts' if lang="ts" is declared, otherwise '.js'.
    """
    match = re.search(
        r"<script(\s[^>]*)?>(.+?)</script>",
        vue_source,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return "", ".js"
    attrs = match.group(1) or ""
    content = match.group(2)
    ext = ".ts" if re.search(r'lang=["\']ts["\']', attrs) else ".js"
    return content, ext


def _scan_jsdoc(lines: list[str]) -> dict[int, str]:
    """Return {close_line_1indexed: jsdoc_text} for each /** ... */ block found.

    close_line_1indexed is the 1-indexed line number of the closing '*/' line.
    """
    result: dict[int, str] = {}
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()
        if stripped.startswith("/**"):
            block = [stripped]
            if "*/" in stripped[3:]:  # single-line: /** ... */
                result[i + 1] = stripped
                i += 1
                continue
            j = i + 1
            while j < n:
                block.append(lines[j].strip())
                if "*/" in lines[j]:
                    result[j + 1] = "\n".join(block)
                    i = j + 1
                    break
                j += 1
            else:
                i = n  # unterminated block — skip
        else:
            i += 1
    return result


def _find_jsdoc(jsdoc_map: dict[int, str], target_line: int) -> str | None:
    """Return the JSDoc text whose closing line is within 3 lines before target_line."""
    for offset in range(1, 5):
        doc = jsdoc_map.get(target_line - offset)
        if doc is not None:
            return doc
    return None


def extract_js_ts(file: Path, language: str = "js_ts") -> FileStructure:
    if not _LIZARD_AVAILABLE:
        return FileStructure(path=file, language=language)

    # Read source once; for Vue, extract the <script> block for both lizard and JSDoc scanning.
    file_text = file.read_text(encoding="utf-8", errors="ignore")
    if language == "vue":
        jsdoc_source, ext = _extract_script_block(file_text)
        if not jsdoc_source.strip():
            return FileStructure(path=file, language=language)
    else:
        jsdoc_source = file_text
        ext = file.suffix

    tmp_path: Path | None = None
    try:
        if language == "vue":
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=ext, delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(jsdoc_source)
                tmp_path = Path(tmp.name)
            result = _lizard.analyze_file(str(tmp_path))
        else:
            result = _lizard.analyze_file(str(file))
    except Exception:
        logger.debug("[ast_extractor] lizard failed on %s", file)
        return FileStructure(path=file, language=language)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    # Lizard uses "ClassName::methodName" for class methods
    class_methods: dict[str, list[tuple[str, int]]] = defaultdict(list)
    top_level_funcs = []

    for fn in result.function_list:
        if "::" in fn.name:
            class_name, method_name = fn.name.split("::", 1)
            class_methods[class_name].append((method_name, fn.start_line))
        else:
            top_level_funcs.append(fn)

    classes = [
        ClassInfo(
            name=cls,
            method_count=len(methods),
            bases=[],  # lizard doesn't expose base classes
            line=methods[0][1],
        )
        for cls, methods in class_methods.items()
    ]

    functions: list[FunctionInfo] = []
    for cls, methods in class_methods.items():
        for method_name, line in methods:
            functions.append(
                FunctionInfo(name=method_name, line=line, is_method=True, class_name=cls)
            )
    for fn in top_level_funcs:
        functions.append(
            FunctionInfo(name=fn.name, line=fn.start_line, is_method=False, class_name=None)
        )

    top_level_count = len(class_methods) + len(top_level_funcs)

    # Scan for JSDoc blocks and map them to entity keys
    jsdoc_map = _scan_jsdoc(jsdoc_source.splitlines())
    docstrings: dict[str, str | None] = {}
    for cls, methods in class_methods.items():
        docstrings[f"class:{cls}"] = _find_jsdoc(jsdoc_map, methods[0][1]) if methods else None
        for method_name, mline in methods:
            docstrings[f"func:{cls}.{method_name}"] = _find_jsdoc(jsdoc_map, mline)
    for fn in top_level_funcs:
        docstrings[f"func:{fn.name}"] = _find_jsdoc(jsdoc_map, fn.start_line)

    return FileStructure(
        path=file,
        language=language,
        classes=classes,
        top_level_definitions=top_level_count,
        functions=functions,
        docstrings=docstrings,
    )


# ---------------------------------------------------------------------------
# Combined extractor
# ---------------------------------------------------------------------------


def extract_all(files: dict[str, list[Path]]) -> list[FileStructure]:
    structures: list[FileStructure] = []
    for f in files.get("python", []):
        structures.append(extract_python(f))
    for f in files.get("js_ts", []):
        structures.append(extract_js_ts(f, "js_ts"))
    for f in files.get("vue", []):
        structures.append(extract_js_ts(f, "vue"))
    return structures
