"""Template e-mail HTML (CSS inline, compatible clients)."""

from __future__ import annotations

from services.report_model import AlertLevel, DailyReportData
from utils.helpers import esc, fmt_hours, progress_bar_html
from utils.i18n import I18n


def _card_outer_open(bg: str = "#ffffff") -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin-bottom:16px;border-radius:14px;overflow:hidden;border:1px solid #e8e8ec;background:{bg};">'
        f"<tr><td style='padding:20px 22px;'>"
    )


def _card_outer_close() -> str:
    return "</td></tr></table>"


def _alert_color(level: AlertLevel) -> tuple[str, str]:
    if level == AlertLevel.CRITICAL:
        return "#b91c1c", "#fef2f2"
    if level == AlertLevel.WARNING:
        return "#c2410c", "#fff7ed"
    return "#15803d", "#f0fdf4"


def _badge_status(level: AlertLevel, i18n: I18n) -> str:
    if level == AlertLevel.CRITICAL:
        label = i18n.t("status_crit")
        fg, bg = "#991b1b", "#fee2e2"
    elif level == AlertLevel.WARNING:
        label = i18n.t("status_warn")
        fg, bg = "#9a3412", "#ffedd5"
    else:
        label = i18n.t("status_ok")
        fg, bg = "#166534", "#dcfce7"
    return (
        '<span style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:11px;font-weight:600;'
        f'color:{fg};background:{bg};">{esc(label)}</span>'
    )


def render_email_html(data: DailyReportData, i18n: I18n) -> str:
    tz = esc(data.timezone_label)
    title = esc(data.period_label)
    ws = esc(data.workspace_name)

    # --- Summary KPIs
    pct_team = data.team_pct_change_vs_prev
    sign = "+" if pct_team > 0 else ""
    summary_block = f"""
{_card_outer_open("#fafafa")}
<p style="margin:0 0 6px;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:#64748b;">{esc(i18n.t("summary"))}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="width:25%;vertical-align:top;padding:8px;">
<p style="margin:0;font-size:12px;color:#64748b;">{esc(i18n.t("total_team"))}</p>
<p style="margin:6px 0 0;font-size:22px;font-weight:700;color:#0f172a;">{fmt_hours(data.total_team_hours)}</p>
</td>
<td style="width:25%;vertical-align:top;padding:8px;">
<p style="margin:0;font-size:12px;color:#64748b;">{esc(i18n.t("active_people"))}</p>
<p style="margin:6px 0 0;font-size:22px;font-weight:700;color:#0f172a;">{data.active_employees}</p>
</td>
<td style="width:25%;vertical-align:top;padding:8px;">
<p style="margin:0;font-size:12px;color:#64748b;">{esc(i18n.t("avg_hours"))}</p>
<p style="margin:6px 0 0;font-size:22px;font-weight:700;color:#0f172a;">{fmt_hours(data.avg_hours_per_employee)}</p>
</td>
<td style="width:25%;vertical-align:top;padding:8px;">
<p style="margin:0;font-size:12px;color:#64748b;">{esc(i18n.t("vs_yesterday"))}</p>
<p style="margin:6px 0 0;font-size:18px;font-weight:700;color:#4338ca;">{esc(data.team_change_arrow)} {sign}{pct_team:.1f} %</p>
<p style="margin:4px 0 0;font-size:11px;color:#94a3b8;">{fmt_hours(data.prev_team_total)} veille</p>
</td>
</tr></table>
{_card_outer_close()}
"""

    # --- Alerts
    alert_rows = []
    for a in data.alerts[:40]:
        fg, bg = _alert_color(a.level)
        lvl_label = (
            i18n.t("level_critical")
            if a.level == AlertLevel.CRITICAL
            else (i18n.t("level_warning") if a.level == AlertLevel.WARNING else i18n.t("level_ok"))
        )
        alert_rows.append(
            f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='margin-bottom:10px;'>"
            f"<tr><td style='border-left:4px solid {fg};background:{bg};padding:12px 14px;border-radius:0 10px 10px 0;'>"
            f"<p style='margin:0 0 4px;font-size:11px;font-weight:700;color:{fg};text-transform:uppercase;'>{esc(lvl_label)}</p>"
            f"<p style='margin:0;font-size:13px;color:#334155;line-height:1.45;'><strong>{esc(a.title)}</strong> — {esc(a.detail)}</p>"
            f"</td></tr></table>"
        )
    alerts_html = "".join(alert_rows) or f"<p style='color:#64748b;font-size:14px;'>{esc(i18n.t('no_data'))}</p>"
    alerts_block = f"""
{_card_outer_open()}
<p style="margin:0 0 12px;font-size:15px;font-weight:700;color:#0f172a;">🚨 {esc(i18n.t("alerts"))}</p>
{alerts_html}
{_card_outer_close()}
"""

    # --- Employee table
    emp_rows = []
    for em in data.employees:
        trend_s = f"{em.trend_arrow} {em.trend_vs_prev_pct:+.1f} %"
        score_pct = max(0, min(100, (em.score + 3) * 20))
        bar = progress_bar_html(score_pct, 100)
        emp_rows.append(
            f"<tr>"
            f"<td style='padding:12px 10px;border-bottom:1px solid #eef2f7;font-size:14px;color:#0f172a;'>{esc(em.name)}</td>"
            f"<td style='padding:12px 10px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:600;'>{fmt_hours(em.total_hours)}</td>"
            f"<td style='padding:12px 10px;border-bottom:1px solid #eef2f7;text-align:center;'>{em.task_count}</td>"
            f"<td style='padding:12px 10px;border-bottom:1px solid #eef2f7;font-size:13px;color:#475569;'>{esc(em.main_project_name)} <span style='color:#94a3b8;'>({em.main_project_pct:.0f}%)</span></td>"
            f"<td style='padding:12px 10px;border-bottom:1px solid #eef2f7;font-size:13px;'>{esc(trend_s)}</td>"
            f"<td style='padding:12px 10px;border-bottom:1px solid #eef2f7;'>{_badge_status(em.status, i18n)}</td>"
            f"<td style='padding:12px 10px;border-bottom:1px solid #eef2f7;'>{bar}<span style='font-size:12px;color:#64748b;margin-left:8px;'>{em.score}</span></td>"
            f"</tr>"
        )
    employees_block = f"""
{_card_outer_open()}
<p style="margin:0 0 14px;font-size:15px;font-weight:700;color:#0f172a;">👥 {esc(i18n.t("employees"))}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
<tr style="background:#f8fafc;">
<th align="left" style="padding:10px;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;">{esc(i18n.t("col_name"))}</th>
<th align="right" style="padding:10px;font-size:10px;text-transform:uppercase;color:#64748b;">{esc(i18n.t("col_total"))}</th>
<th align="center" style="padding:10px;font-size:10px;text-transform:uppercase;color:#64748b;">{esc(i18n.t("col_tasks"))}</th>
<th align="left" style="padding:10px;font-size:10px;text-transform:uppercase;color:#64748b;">{esc(i18n.t("col_main_project"))}</th>
<th align="left" style="padding:10px;font-size:10px;text-transform:uppercase;color:#64748b;">{esc(i18n.t("col_trend"))}</th>
<th align="left" style="padding:10px;font-size:10px;text-transform:uppercase;color:#64748b;">{esc(i18n.t("col_status"))}</th>
<th align="left" style="padding:10px;font-size:10px;text-transform:uppercase;color:#64748b;">{esc(i18n.t("col_score"))}</th>
</tr>
{''.join(emp_rows)}
</table>
{_card_outer_close()}
"""

    # Insights
    ins_lines = "".join(
        f"<li style='margin:8px 0;color:#334155;font-size:14px;line-height:1.5;'>{esc(x)}</li>" for x in data.insight_lines
    )
    insights_block = f"""
{_card_outer_open()}
<p style="margin:0 0 10px;font-size:15px;font-weight:700;color:#0f172a;">🧠 {esc(i18n.t("insights"))}</p>
<ul style="margin:0;padding-left:18px;">{ins_lines}</ul>
<p style="margin:12px 0 0;font-size:13px;color:#64748b;">{esc(i18n.t("productive"))} : <strong>{fmt_hours(data.productive_hours)}</strong> · {esc(i18n.t("non_productive"))} : <strong>{fmt_hours(data.non_productive_hours)}</strong></p>
<p style="margin:8px 0 0;font-size:13px;color:#64748b;">{esc(i18n.t("priority_vs_other"))} : {fmt_hours(data.priority_hours)} / {fmt_hours(data.other_hours)} · {esc(i18n.t("uncategorized"))} : {fmt_hours(data.uncategorized_hours)}</p>
{_card_outer_close()}
"""

    rep_lines = "".join(
        f"<li style='margin:6px 0;font-size:13px;color:#334155;'>{esc(x)}</li>" for x in data.repeated_task_notes[:12]
    )
    repeated_block = (
        f"{_card_outer_open()}"
        f"<p style='margin:0 0 8px;font-size:14px;font-weight:700;color:#0f172a;'>🔁 {esc(i18n.t('repeated_tasks'))}</p>"
        f"<ul style='margin:0;padding-left:18px;'>{rep_lines}</ul>"
        f"{_card_outer_close()}"
        if data.repeated_task_notes
        else ""
    )

    # Projects
    proj_rows = []
    for p in data.projects[:15]:
        flag = " ⚠️" if p.flagged else ""
        proj_rows.append(
            f"<tr><td style='padding:10px;border-bottom:1px solid #eef2f7;font-size:14px;'>{esc(p.name)}{flag}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:600;'>{fmt_hours(p.hours)}</td></tr>"
        )
    top_lines = "".join(
        f"<li style='margin:6px 0;font-size:14px;color:#334155;'><strong>{esc(p.name)}</strong> — {fmt_hours(p.hours)}</li>"
        for p in data.top_projects
    )
    projects_block = f"""
{_card_outer_open()}
<p style="margin:0 0 10px;font-size:15px;font-weight:700;color:#0f172a;">📁 {esc(i18n.t("projects"))}</p>
<table role="presentation" width="100%">{''.join(proj_rows)}</table>
<p style="margin:14px 0 6px;font-size:13px;font-weight:600;color:#475569;">{esc(i18n.t("project_top3"))}</p>
<ul style="margin:0;padding-left:18px;">{top_lines}</ul>
{_card_outer_close()}
"""

    # Ranking
    top_s = "".join(f"<li style='margin:6px 0;'>{esc(n)} — {fmt_hours(h)}</li>" for n, h in data.ranking_top)
    bot_s = "".join(f"<li style='margin:6px 0;'>{esc(n)} — {fmt_hours(h)}</li>" for n, h in data.ranking_bottom)
    rank_block = f"""
{_card_outer_open()}
<p style="margin:0 0 10px;font-size:15px;font-weight:700;color:#0f172a;">🏆 {esc(i18n.t("ranking"))}</p>
<table role="presentation" width="100%"><tr>
<td style="width:50%;vertical-align:top;padding-right:8px;">
<p style="font-size:12px;font-weight:600;color:#16a34a;">{esc(i18n.t("top3"))}</p>
<ul style="margin:8px 0 0;padding-left:18px;">{top_s}</ul>
</td>
<td style="width:50%;vertical-align:top;padding-left:8px;">
<p style="font-size:12px;font-weight:600;color:#dc2626;">{esc(i18n.t("bottom3"))}</p>
<ul style="margin:8px 0 0;padding-left:18px;">{bot_s}</ul>
</td>
</tr></table>
{_card_outer_close()}
"""

    # Dark mode hint: meta + optional background
    return f"""<!DOCTYPE html>
<html lang="{esc(i18n.locale)}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<title>{esc(i18n.t("title"))}</title>
</head>
<body style="margin:0;padding:0;background:#eceef2;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eceef2;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" style="max-width:680px;border-collapse:collapse;">

<tr><td style="background:linear-gradient(135deg,#312e81 0%,#4f46e5 40%,#7c3aed 100%);border-radius:18px 18px 0 0;padding:28px 24px;">
<p style="margin:0 0 6px;font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:rgba(255,255,255,0.75);">Clockify · {ws}</p>
<h1 style="margin:0;font-size:24px;font-weight:800;color:#ffffff;line-height:1.25;">{esc(i18n.t("title"))}</h1>
<p style="margin:12px 0 0;font-size:14px;color:rgba(255,255,255,0.88);">{title}</p>
<p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.75);">{tz}</p>
</td></tr>

<tr><td style="height:12px;background:transparent;"></td></tr>

<tr><td style="padding:0;">
{summary_block}
{alerts_block}
{employees_block}
{insights_block}
{repeated_block}
{projects_block}
{rank_block}
</td></tr>

<tr><td style="padding:16px 8px 8px;text-align:center;">
<p style="margin:0;font-size:11px;color:#94a3b8;">{esc(i18n.t("footer"))} · Wenov</p>
</td></tr>

</table>
</td></tr></table>
</body>
</html>"""
