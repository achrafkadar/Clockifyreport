"""Agrégations, anomalies, scores, tendances."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Optional

from config.settings import ReportConfig
from services.clockify_client import (
    entry_billable,
    entry_duration_seconds,
    entry_project_task,
    entry_start_local,
    user_label,
)
from services.report_model import (
    AlertItem,
    AlertLevel,
    DailyReportData,
    EmployeeMetrics,
    ProjectStat,
    RepeatedTaskRow,
)

TEAM_ALERT_ONLY_TITLE = "Aucun temps"


def _project_day_insight_lines(
    entries: list[dict[str, Any]],
    unames: dict[str, str],
    locale: str,
    max_lines: int = 32,
) -> list[str]:
    """Projets travaillés sur la période du rapport, avec contributeurs."""
    proj_h: dict[str, float] = defaultdict(float)
    proj_users: dict[str, set[str]] = defaultdict(set)
    for e in entries:
        uid, uname = user_label(e, unames)
        _, pname, _, _ = entry_project_task(e)
        proj_h[pname] += entry_duration_seconds(e) / 3600.0
        if uid != "unknown":
            proj_users[pname].add(uname)
    items = sorted(proj_h.items(), key=lambda x: -x[1])
    lines: list[str] = []
    fr = locale != "en"
    for pname, hrs in items[:max_lines]:
        people = sorted(proj_users[pname])
        nu = len(people)
        if nu == 0:
            people_s = "—"
        elif nu <= 5:
            people_s = ", ".join(people)
        else:
            people_s = ", ".join(people[:5]) + (f" (+{nu - 5})" if fr else f" (+{nu - 5})")
        if fr:
            lines.append(f"«{pname}» : {hrs:.2f} h — {people_s} ({nu} pers.)")
        else:
            lines.append(f"«{pname}»: {hrs:.2f} h — {people_s} ({nu} people)")
    if len(items) > max_lines:
        if fr:
            lines.append(f"… et {len(items) - max_lines} autre(s) projet(s).")
        else:
            lines.append(f"… and {len(items) - max_lines} more project(s).")
    if not lines:
        return (
            ["Aucun temps projet sur la période."]
            if fr
            else ["No project time logged for this period."]
        )
    return lines


def _hours_by_user(entries: list[dict[str, Any]], user_names: dict[str, str]) -> dict[str, float]:
    h: dict[str, float] = defaultdict(float)
    for e in entries:
        uid, _ = user_label(e, user_names)
        if uid != "unknown":
            user_names[uid] = _
        h[uid] += entry_duration_seconds(e) / 3600.0
    return dict(h)


def _entry_counts(entries: list[dict[str, Any]], user_names: dict[str, str]) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for e in entries:
        uid, _ = user_label(e, user_names)
        c[uid] += 1
    return dict(c)


def _distinct_task_counts(entries: list[dict[str, Any]], user_names: dict[str, str]) -> dict[str, int]:
    seen: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for e in entries:
        uid, _ = user_label(e, user_names)
        pid, _, tid, _ = entry_project_task(e)
        seen[uid].add((pid, tid))
    return {u: len(s) for u, s in seen.items()}


def _hours_by_user_project(entries: list[dict[str, Any]], user_names: dict[str, str]) -> dict[tuple[str, str], float]:
    h: dict[tuple[str, str], float] = defaultdict(float)
    for e in entries:
        uid, _ = user_label(e, user_names)
        pid, pname, _, _ = entry_project_task(e)
        h[(uid, pid or pname)] += entry_duration_seconds(e) / 3600.0
    return dict(h)


def _hours_by_project_team(entries: list[dict[str, Any]], user_names: dict[str, str]) -> dict[str, tuple[str, float]]:
    """project_id -> (name, hours)"""
    h: dict[str, float] = defaultdict(float)
    names: dict[str, str] = {}
    for e in entries:
        user_label(e, user_names)
        pid, pname, _, _ = entry_project_task(e)
        key = pid or pname
        names[key] = pname
        h[key] += entry_duration_seconds(e) / 3600.0
    return {k: (names.get(k, k), v) for k, v in h.items()}


def _user_task_hours(entries: list[dict[str, Any]], user_names: dict[str, str]) -> dict[tuple[str, str], float]:
    """(user_id, task_id) -> hours"""
    h: dict[tuple[str, str], float] = defaultdict(float)
    for e in entries:
        uid, _ = user_label(e, user_names)
        _, _, tid, _ = entry_project_task(e)
        h[(uid, tid)] += entry_duration_seconds(e) / 3600.0
    return dict(h)


def _productive_split(entries: list[dict[str, Any]], user_names: dict[str, str]) -> tuple[float, float]:
    prod = 0.0
    nonp = 0.0
    unknown = 0.0
    for e in entries:
        user_label(e, user_names)
        sec = entry_duration_seconds(e)
        h = sec / 3600.0
        b = entry_billable(e)
        if b is True:
            prod += h
        elif b is False:
            nonp += h
        else:
            unknown += h
    if unknown > 0:
        nonp += unknown
    return prod, nonp


def _priority_hours(
    entries: list[dict[str, Any]], user_names: dict[str, str], cfg: ReportConfig
) -> tuple[float, float]:
    pri = 0.0
    oth = 0.0
    for e in entries:
        user_label(e, user_names)
        pid, pname, _, _ = entry_project_task(e)
        sec = entry_duration_seconds(e)
        h = sec / 3600.0
        is_p = pid in cfg.priority_project_ids or pname.lower() in cfg.priority_project_names
        if is_p:
            pri += h
        else:
            oth += h
    return pri, oth


def _uncategorized_hours(entries: list[dict[str, Any]], user_names: dict[str, str]) -> float:
    t = 0.0
    for e in entries:
        user_label(e, user_names)
        _, pname, _, _ = entry_project_task(e)
        if pname == "(Sans projet)":
            t += entry_duration_seconds(e) / 3600.0
    return t


def _outside_hours_flags(
    entries: list[dict[str, Any]], user_names: dict[str, str], cfg: ReportConfig, tz: str
) -> list[str]:
    flags: list[str] = []
    for e in entries:
        uid, uname = user_label(e, user_names)
        st = entry_start_local(e, tz)
        if not st:
            continue
        hour = st.hour
        if hour < cfg.work_hour_start or hour >= cfg.work_hour_end:
            flags.append(f"{uname} : entrée démarrée à {hour:02d}h (hors plage {cfg.work_hour_start}h–{cfg.work_hour_end}h).")
    return flags[:20]


def build_daily_report(
    cfg: ReportConfig,
    report_date: date,
    period_label: str,
    timezone_label: str,
    workspace_name: str,
    entries_report: list[dict[str, Any]],
    entries_compare: list[dict[str, Any]],
    workspace_users: list[dict[str, Any]],
) -> DailyReportData:
    """entries_compare = journée calendaire précédente (pour tendances équipe & perso)."""
    unames: dict[str, str] = {}
    for u in workspace_users:
        uid = u.get("id")
        if uid:
            unames[uid] = (u.get("name") or u.get("email") or uid)[:200]

    hu_report = _hours_by_user(entries_report, unames)
    hu_prev = _hours_by_user(entries_compare, dict(unames))

    total_team = sum(h for k, h in hu_report.items() if k != "unknown")
    prev_team = sum(h for k, h in hu_prev.items() if k != "unknown")
    active = len([k for k, h in hu_report.items() if k != "unknown" and h > 1e-6])
    avg = total_team / active if active else 0.0

    if prev_team > 1e-9:
        pct = (total_team - prev_team) / prev_team * 100.0
    else:
        pct = 100.0 if total_team > 0 else 0.0
    arrow = "↑" if total_team >= prev_team else "↓"

    alerts: list[AlertItem] = []

    # Tâches / projets > seuil (agrégat par personne + projet + tâche)
    bucket_h: dict[tuple[str, str, str], float] = defaultdict(float)
    bucket_lbl: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for e in entries_report:
        uid, uname = user_label(e, unames)
        pid, pname, tid, tname = entry_project_task(e)
        key = (uid, pid, tid)
        bucket_h[key] += entry_duration_seconds(e) / 3600.0
        bucket_lbl[key] = (uname, pname, tname)
    for key, hrs in bucket_h.items():
        uid, _, _ = key
        if uid == "unknown" or hrs <= cfg.task_alert_hours:
            continue
        uname, pname, tname = bucket_lbl.get(key, ("", "", "—"))
        alerts.append(
            AlertItem(
                AlertLevel.WARNING,
                "Tâche / projet long",
                f"{uname} — «{pname}» ({tname}) : {hrs:.2f} h (> {cfg.task_alert_hours:g} h).",
            )
        )

    ec_report = _entry_counts(entries_report, unames)
    for uid, n in ec_report.items():
        if uid != "unknown" and n > cfg.max_entries_per_day:
            alerts.append(
                AlertItem(
                    AlertLevel.WARNING,
                    "Beaucoup d'entrées",
                    f"{unames.get(uid, uid)} : {n} lignes aujourd'hui (> {cfg.max_entries_per_day}).",
                )
            )

    for line in _outside_hours_flags(entries_report, unames, cfg, cfg.timezone):
        alerts.append(AlertItem(AlertLevel.WARNING, "Horaire atypique", line))

    wd = report_date.weekday() < 5
    for u in workspace_users:
        if (u.get("status") or "").upper() != "ACTIVE":
            continue
        uid = u.get("id")
        if not uid:
            continue
        h = hu_report.get(uid, 0.0)
        name = unames.get(uid, uid)
        if wd and h < 1e-6:
            alerts.append(AlertItem(AlertLevel.CRITICAL, "Aucun temps", f"{name} : 0 h enregistré (jour ouvré)."))
        elif h > 1e-6 and h < cfg.low_hours_warning:
            alerts.append(
                AlertItem(AlertLevel.WARNING, "Temps faible", f"{name} : {h:.2f} h (< {cfg.low_hours_warning:g} h).")
            )
        if h > cfg.high_hours_warning:
            alerts.append(
                AlertItem(AlertLevel.CRITICAL, "Temps élevé", f"{name} : {h:.2f} h (> {cfg.high_hours_warning:g} h).")
            )

    # Tâches répétées 2 jours (même user + task_id > seuil sur J et J-1)
    ut_r = _user_task_hours(entries_report, unames)
    ut_p = _user_task_hours(entries_compare, unames)
    uid_tid_label: dict[tuple[str, str], str] = {}
    for e in entries_report:
        uid, _ = user_label(e, unames)
        _, _, tid, tname = entry_project_task(e)
        if tid:
            uid_tid_label[(uid, tid)] = tname if tname != "—" else "Tâche"

    repeated_rows: list[RepeatedTaskRow] = []
    for (uid, tid), hr in ut_r.items():
        if not tid:
            continue
        hp = ut_p.get((uid, tid), 0.0)
        if hr >= cfg.long_task_repeat_hours and hp >= cfg.long_task_repeat_hours:
            repeated_rows.append(
                RepeatedTaskRow(
                    employee_name=unames.get(uid, uid),
                    task_name=uid_tid_label.get((uid, tid), "Tâche"),
                    hours_report_day=hr,
                    hours_previous_day=hp,
                )
            )
    repeated_notes = [
        f"{r.employee_name} — «{r.task_name}» : {r.hours_report_day:.1f} h + {r.hours_previous_day:.1f} h (2 j)"
        for r in repeated_rows
    ]

    # Projets
    proj_map = _hours_by_project_team(entries_report, unames)
    projects: list[ProjectStat] = []
    for pid, (pname, hrs) in proj_map.items():
        flagged = hrs > cfg.project_expected_hours
        projects.append(ProjectStat(project_id=pid, name=pname, hours=hrs, flagged=flagged))
    projects.sort(key=lambda x: -x.hours)
    top3 = projects[:3]

    # Insights : projets touchés sur la journée (même période que le rapport)
    prod, nonp = _productive_split(entries_report, unames)
    pri, oth = _priority_hours(entries_report, unames, cfg)
    unc = _uncategorized_hours(entries_report, unames)
    insight_lines = _project_day_insight_lines(entries_report, unames, cfg.locale)
    # Employés : main project %, trend, score, status
    uproj = defaultdict(lambda: defaultdict(float))
    for e in entries_report:
        uid, _ = user_label(e, unames)
        _, pname, _, _ = entry_project_task(e)
        uproj[uid][pname] += entry_duration_seconds(e) / 3600.0

    dtc = _distinct_task_counts(entries_report, unames)

    active_uids: list[str] = []
    for u in workspace_users:
        if (u.get("status") or "").upper() != "ACTIVE":
            continue
        uid = u.get("id")
        if not uid:
            continue
        active_uids.append(uid)

    employees: list[EmployeeMetrics] = []
    for uid in active_uids:
        total = hu_report.get(uid, 0.0)
        prev = hu_prev.get(uid, 0.0)
        if prev > 1e-9:
            tr_pct = (total - prev) / prev * 100.0
        else:
            tr_pct = 100.0 if total > 0 else 0.0
        t_arrow = "↑" if total >= prev else "↓"

        mp_name = ""
        mp_pct = 0.0
        if uproj[uid] and total > 1e-9:
            mp_name = max(uproj[uid].items(), key=lambda x: x[1])[0]
            mp_pct = (uproj[uid][mp_name] / total * 100.0) if total > 1e-9 else 0.0

        status = AlertLevel.OK
        if total < 1e-6 and wd:
            status = AlertLevel.CRITICAL
        elif total < 1e-6:
            status = AlertLevel.OK
        elif total < cfg.low_hours_warning:
            status = AlertLevel.WARNING
        elif total > cfg.high_hours_warning:
            status = AlertLevel.CRITICAL

        score = 0
        if cfg.full_day_hours_min <= total <= cfg.full_day_hours_max:
            score += 1
        if status == AlertLevel.OK:
            score += 1
        if wd and 1e-9 < total < cfg.low_hours_warning:
            score -= 1
        if total > cfg.high_hours_warning:
            score -= 1
        note = f"+ journée complète si ∈[{cfg.full_day_hours_min},{cfg.full_day_hours_max}]h ; + sans alerte ; − sous/sur-charge"

        employees.append(
            EmployeeMetrics(
                user_id=uid,
                name=unames.get(uid, uid),
                total_hours=total,
                task_count=dtc.get(uid, 0),
                entry_count=ec_report.get(uid, 0),
                main_project_name=mp_name or "—",
                main_project_pct=mp_pct,
                trend_vs_prev_pct=tr_pct,
                trend_arrow=t_arrow,
                status=status,
                score=score,
                score_note=note,
            )
        )

    employees.sort(
        key=lambda e: (
            0 if e.total_hours > 1e-6 else 1,
            -e.total_hours if e.total_hours > 1e-6 else 0.0,
            e.name.lower(),
        )
    )

    ranked_pos = [(e.name, e.total_hours) for e in employees if e.total_hours > 1e-6]
    ranked_pos.sort(key=lambda x: -x[1])
    top_r = ranked_pos[:3]
    ranked_all = [(e.name, e.total_hours) for e in employees]
    ranked_all.sort(key=lambda x: x[1])
    bottom_r = ranked_all[:3]

    team_alerts = [a for a in alerts if a.title == TEAM_ALERT_ONLY_TITLE]

    return DailyReportData(
        report_date=report_date,
        period_label=period_label,
        timezone_label=timezone_label,
        workspace_name=workspace_name,
        total_team_hours=total_team,
        active_employees=active,
        avg_hours_per_employee=avg,
        prev_team_total=prev_team,
        team_pct_change_vs_prev=pct,
        team_change_arrow=arrow,
        alerts=alerts,
        employees=employees,
        insight_lines=insight_lines,
        projects=projects,
        top_projects=top3,
        ranking_top=top_r,
        ranking_bottom=bottom_r,
        productive_hours=prod,
        non_productive_hours=nonp,
        priority_hours=pri,
        other_hours=oth,
        uncategorized_hours=unc,
        repeated_task_notes=repeated_notes,
        repeated_tasks=repeated_rows,
        team_alerts=team_alerts,
        daily_reference_hours=cfg.project_expected_hours,
        raw_meta={"entries_report": len(entries_report), "entries_compare": len(entries_compare)},
    )


def mock_report_data() -> DailyReportData:
    """Jeu de démonstration pour prévisualisation HTML."""
    return DailyReportData(
        report_date=date(2026, 4, 18),
        period_label="Journée complète du 2026-04-18",
        timezone_label="America/Toronto",
        workspace_name="Wenov",
        total_team_hours=31.5,
        active_employees=5,
        avg_hours_per_employee=6.3,
        prev_team_total=28.0,
        team_pct_change_vs_prev=12.5,
        team_change_arrow="↑",
        alerts=[
            AlertItem(AlertLevel.WARNING, "Tâche / projet long", "Oussama — « Montage » : 4.5 h (> 3 h)."),
            AlertItem(AlertLevel.CRITICAL, "Temps élevé", "Lee : 11.2 h (> 10 h)."),
        ],
        employees=[
            EmployeeMetrics(
                "1",
                "Alice",
                8.0,
                6,
                9,
                "Client A",
                62.0,
                5.2,
                "↑",
                AlertLevel.OK,
                2,
                "",
            ),
            EmployeeMetrics(
                "2",
                "Oussama",
                7.5,
                8,
                12,
                "Montage",
                55.0,
                -3.0,
                "↓",
                AlertLevel.WARNING,
                0,
                "",
            ),
            EmployeeMetrics(
                "3",
                "Zoe",
                0.0,
                0,
                0,
                "—",
                0.0,
                0.0,
                "→",
                AlertLevel.CRITICAL,
                0,
                "",
            ),
        ],
        insight_lines=[
            "«Client A» : 14.00 h — Alice, Oussama (2 pers.)",
            "«Montage» : 10.50 h — Oussama (1 pers.)",
        ],
        projects=[
            ProjectStat("p1", "Client A", 14.0, False),
            ProjectStat("p2", "Interne", 10.0, True),
        ],
        top_projects=[
            ProjectStat("p1", "Client A", 14.0, False),
            ProjectStat("p2", "Interne", 10.0, True),
            ProjectStat("p3", "Pub", 7.5, False),
        ],
        ranking_top=[("Alice", 8.0), ("Oussama", 7.5), ("Sam", 6.0)],
        ranking_bottom=[("Kim", 4.0), ("Jo", 5.0), ("Max", 5.5)],
        productive_hours=24.0,
        non_productive_hours=7.5,
        priority_hours=18.0,
        other_hours=13.5,
        uncategorized_hours=2.0,
        repeated_task_notes=[],
        repeated_tasks=[
            RepeatedTaskRow("Oussama", "Montage vidéo", 3.5, 2.8),
        ],
        team_alerts=[
            AlertItem(AlertLevel.CRITICAL, "Aucun temps", "Kim : 0 h enregistré (jour ouvré)."),
        ],
        daily_reference_hours=8.0,
    )
