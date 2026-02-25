import logging
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

from app.models.metrics_schema import (
    CategoryResult,
    IssueAction,
    IssueActions,
    MetricResult,
    MetricsSnapshot,
    Severity,
    SeverityDistribution,
    TopIssue,
)
from app.services.metrics.severity import SEVERITY_SCORES

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.WARNING,
    Severity.ACCEPTABLE,
    Severity.GOOD,
    Severity.EXCELLENT,
]


def _worst_severity(severities: list[Severity]) -> Severity:
    for sev in _SEVERITY_ORDER:
        if sev in severities:
            return sev
    return Severity.EXCELLENT


def build_snapshot(
    project_id: str,
    categorized_metrics: list[tuple[str, MetricResult]],
) -> MetricsSnapshot:
    by_category: dict[str, list[MetricResult]] = defaultdict(list)
    for category_name, metric in categorized_metrics:
        by_category[category_name].append(metric)

    all_metrics = [m for _, m in categorized_metrics]

    overall_score = (
        round(mean(SEVERITY_SCORES[m.severity.value] for m in all_metrics))
        if all_metrics
        else 0
    )

    dist: dict[str, int] = {sev.value: 0 for sev in Severity}
    for m in all_metrics:
        dist[m.severity.value] += 1

    categories: list[CategoryResult] = []
    for name, metrics in by_category.items():
        worst = _worst_severity([m.severity for m in metrics])
        metrics_sorted = sorted(
            metrics, key=lambda m: _SEVERITY_ORDER.index(m.severity)
        )
        categories.append(
            CategoryResult(name=name, severity=worst, metrics=metrics_sorted)
        )
    categories.sort(key=lambda c: _SEVERITY_ORDER.index(c.severity))

    metric_by_name = {m.name: m for m in all_metrics}
    import_cycles = (
        int(metric_by_name["Import Cycles"].value)
        if "Import Cycles" in metric_by_name
        else 0
    )
    doc_coverage = (
        float(metric_by_name["Overall Documentation Coverage"].value)
        if "Overall Documentation Coverage" in metric_by_name
        else 0.0
    )
    module_density = (
        float(metric_by_name["Module Graph Density"].value)
        if "Module Graph Density" in metric_by_name
        else 0.0
    )

    warn_critical = sorted(
        [m for m in all_metrics if m.severity in (Severity.WARNING, Severity.CRITICAL)],
        key=lambda m: _SEVERITY_ORDER.index(m.severity),
    )
    top_issues: list[TopIssue] = [
        TopIssue(
            id=f"issue-{i + 1}",
            title=m.name,
            description=m.description,
            severity=m.severity,
            actions=IssueActions(
                primary=IssueAction(label="View Details", action="view-details"),
                secondary=IssueAction(label="Learn More", action="learn-more"),
            ),
        )
        for i, m in enumerate(warn_critical[:5])
    ]

    return MetricsSnapshot(
        projectId=project_id,
        overallScore=overall_score,
        importCycles=import_cycles,
        documentationCoverage=doc_coverage,
        moduleDensity=module_density,
        lastAnalyzed=datetime.now(timezone.utc),
        severityDistribution=SeverityDistribution(**dist),
        categories=categories,
        topIssues=top_issues,
    )
