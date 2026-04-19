"""Modèle de données du rapport (JSON intermédiaire avant rendu HTML)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Optional


class AlertLevel(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    OK = "ok"


@dataclass
class AlertItem:
    level: AlertLevel
    title: str
    detail: str


@dataclass
class EmployeeMetrics:
    user_id: str
    name: str
    total_hours: float
    task_count: int
    entry_count: int
    main_project_name: str
    main_project_pct: float
    trend_vs_prev_pct: float
    trend_arrow: str
    status: AlertLevel
    score: int
    score_note: str


@dataclass
class ProjectStat:
    project_id: str
    name: str
    hours: float
    flagged: bool


@dataclass
class RepeatedTaskRow:
    """Tâche longue répétée sur 2 jours consécutifs."""

    employee_name: str
    task_name: str
    hours_report_day: float
    hours_previous_day: float


@dataclass
class DailyReportData:
    report_date: date
    period_label: str
    timezone_label: str
    workspace_name: str
    total_team_hours: float
    active_employees: int
    avg_hours_per_employee: float
    prev_team_total: float
    team_pct_change_vs_prev: float
    team_change_arrow: str
    alerts: list[AlertItem] = field(default_factory=list)
    employees: list[EmployeeMetrics] = field(default_factory=list)
    insight_lines: list[str] = field(default_factory=list)
    projects: list[ProjectStat] = field(default_factory=list)
    top_projects: list[ProjectStat] = field(default_factory=list)
    ranking_top: list[tuple[str, float]] = field(default_factory=list)
    ranking_bottom: list[tuple[str, float]] = field(default_factory=list)
    productive_hours: float = 0.0
    non_productive_hours: float = 0.0
    priority_hours: float = 0.0
    other_hours: float = 0.0
    uncategorized_hours: float = 0.0
    repeated_task_notes: list[str] = field(default_factory=list)
    repeated_tasks: list[RepeatedTaskRow] = field(default_factory=list)
    # Alertes « équipe » : temps faible / élevé / aucune activité / trop d'entrées / horaires
    team_alerts: list[AlertItem] = field(default_factory=list)
    raw_meta: dict[str, Any] = field(default_factory=dict)
