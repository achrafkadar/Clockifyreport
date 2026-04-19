"""Configuration seuils & options (variables d'environnement)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _f(name: str, default: float) -> float:
    try:
        return float((os.environ.get(name) or str(default)).replace(",", "."))
    except ValueError:
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def _split_ids(raw: str) -> set[str]:
    return {x.strip() for x in (raw or "").split(",") if x.strip()}


@dataclass
class ReportConfig:
    timezone: str
    report_day: str
    workspace_name: str
    task_alert_hours: float
    low_hours_warning: float
    high_hours_warning: float
    max_entries_per_day: int
    work_hour_start: int
    work_hour_end: int
    full_day_hours_min: float
    full_day_hours_max: float
    long_task_repeat_hours: float
    project_expected_hours: float
    priority_project_ids: set[str] = field(default_factory=set)
    priority_project_names: set[str] = field(default_factory=set)
    locale: str = "fr"


def load_config() -> ReportConfig:
    return ReportConfig(
        timezone=os.environ.get("TIMEZONE", "America/Toronto").strip(),
        report_day=(os.environ.get("REPORT_DAY", "yesterday") or "yesterday").strip().lower(),
        workspace_name=os.environ.get("CLOCKIFY_WORKSPACE_NAME", "Wenov").strip(),
        task_alert_hours=_f("PROJECT_HOURS_ALERT_THRESHOLD", 3.0),
        low_hours_warning=_f("ALERT_LOW_HOURS", 4.0),
        high_hours_warning=_f("ALERT_HIGH_HOURS", 10.0),
        max_entries_per_day=_i("ALERT_MAX_ENTRIES_PER_DAY", 15),
        work_hour_start=_i("WORK_HOUR_START", 8),
        work_hour_end=_i("WORK_HOUR_END", 20),
        full_day_hours_min=_f("FULL_DAY_HOURS_MIN", 7.0),
        full_day_hours_max=_f("FULL_DAY_HOURS_MAX", 10.0),
        long_task_repeat_hours=_f("LONG_TASK_REPEAT_HOURS", 2.0),
        project_expected_hours=_f("PROJECT_EXPECTED_HOURS", 8.0),
        priority_project_ids=_split_ids(os.environ.get("PRIORITY_PROJECT_IDS", "")),
        priority_project_names={x.lower() for x in _split_ids(os.environ.get("PRIORITY_PROJECT_NAMES", ""))},
        locale=(os.environ.get("LOCALE", "fr") or "fr").strip().lower()[:2],
    )
