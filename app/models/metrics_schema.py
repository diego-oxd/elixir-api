from datetime import datetime
from enum import Enum
from typing import Union

from pydantic import BaseModel, ConfigDict


class Severity(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    WARNING = "warning"
    CRITICAL = "critical"


SEVERITY_SCORES: dict[str, int] = {
    "excellent": 100,
    "good": 80,
    "acceptable": 60,
    "warning": 40,
    "critical": 20,
}


class SecondaryMeasure(BaseModel):
    value: Union[int, float]
    label: str  # e.g. "max callers", "avg depth", "% of total"


class MetricItem(BaseModel):
    """One entry in a metric's breakdown list."""

    model_config = ConfigDict(extra="ignore")

    name: str
    kind: str | None = None  # "Function" | "Class" | "Method" | "Module"
    count: Union[int, float, None] = None
    countLabel: str | None = (
        None  # "methods" | "callers" | "definitions" | "chars" | "hops"
    )
    filePath: str | None = None
    id: str | None = None


class DocTypeBreakdown(BaseModel):
    entityType: str  # "Function" | "Class" | "Method" | "Module"
    total: int
    documented: int
    coverage: float  # 0.0–100.0


class MetricResult(BaseModel):
    name: str
    value: Union[int, float]
    secondary: SecondaryMeasure | None = None
    severity: Severity
    description: str
    thresholdInfo: str
    details: list[dict] | None = None


class CategoryResult(BaseModel):
    name: str
    severity: Severity  # worst severity of any metric in this category
    metrics: list[MetricResult]


class SeverityDistribution(BaseModel):
    excellent: int
    good: int
    acceptable: int
    warning: int
    critical: int


class IssueAction(BaseModel):
    label: str
    action: str


class IssueActions(BaseModel):
    primary: IssueAction | None = None
    secondary: IssueAction | None = None


class TopIssue(BaseModel):
    id: str
    title: str
    description: str
    severity: Severity
    actions: IssueActions


class MetricsSnapshot(BaseModel):
    """Full metrics report for one analysis run. Stored in pages.content as JSONB."""

    projectId: str
    overallScore: int  # 0–100, average of SEVERITY_SCORES across all metrics
    importCycles: int  # KPI: value from "Import Cycles" metric
    documentationCoverage: (
        float  # KPI: value from "Overall Documentation Coverage" metric
    )
    moduleDensity: float  # KPI: value from "Module Graph Density" metric
    lastAnalyzed: datetime
    severityDistribution: SeverityDistribution
    categories: list[CategoryResult]  # sorted worst-first by category severity
    topIssues: list[TopIssue]  # max 5 WARNING/CRITICAL metrics
