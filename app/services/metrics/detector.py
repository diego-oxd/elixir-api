import shutil
from pathlib import Path

from app.services.metrics.file_walker import discover_files


def detect_languages(repo_path: str) -> set[str]:
    """Return the set of language families present in the repo.

    Possible values: "python", "js_ts", "vue"
    """
    files = discover_files(repo_path)
    root = Path(repo_path)
    detected: set[str] = set()

    if files["python"]:
        detected.add("python")

    if files["js_ts"] or files["vue"] or (root / "package.json").exists():
        detected.add("js_ts")

    if files["vue"]:
        detected.add("vue")

    return detected


def check_tool_available(tool: str) -> bool:
    return shutil.which(tool) is not None
