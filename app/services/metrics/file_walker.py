import os
from pathlib import Path

IGNORE_DIRS = {
    "node_modules",
    "dist",
    "build",
    ".next",
    "out",
    ".nuxt",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "site-packages",
    ".git",
    "coverage",
    ".nyc_output",
    ".cache",
    "tmp",
    "temp",
}

PYTHON_EXTENSIONS = {".py"}
JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
VUE_EXTENSIONS = {".vue"}

IGNORE_SUFFIXES = (".min.js", ".min.css", ".min.ts", ".d.ts", ".pyc")


def discover_files(repo_path: str) -> dict[str, list[Path]]:
    """Walk repo_path and return source files grouped by language family.

    Returns:
        {
            "python": [...],
            "js_ts":  [...],   # includes .jsx, .tsx
            "vue":    [...],
        }
    Ignores build artifacts, virtual envs, and minified files.
    """
    result: dict[str, list[Path]] = {"python": [], "js_ts": [], "vue": []}
    root = Path(repo_path)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place so os.walk skips them
        dirnames[:] = [
            d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            if any(filename.endswith(suffix) for suffix in IGNORE_SUFFIXES):
                continue

            filepath = Path(dirpath) / filename
            ext = filepath.suffix.lower()

            if ext in PYTHON_EXTENSIONS:
                result["python"].append(filepath)
            elif ext in JS_TS_EXTENSIONS:
                result["js_ts"].append(filepath)
            elif ext in VUE_EXTENSIONS:
                result["vue"].append(filepath)

    return result
