import os
from pathlib import Path

from app.models.metrics_schema import MetricResult, SecondaryMeasure
from app.services.metrics.file_walker import IGNORE_DIRS
from app.services.metrics.severity import FOLDER_NESTING_THRESHOLDS, calculate_severity

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
