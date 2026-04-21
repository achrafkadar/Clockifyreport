"""Template e-mail premium (CSS inline) — hero → KPI → barres / ref. → alertes → projets jour → tâches répétées."""

from __future__ import annotations

from services.report_model import AlertLevel, DailyReportData
from utils.helpers import (
    esc,
    fmt_hours,
    format_report_date,
    progress_bar_8h_html,
)
from utils.i18n import I18n


def _alert_style(level: AlertLevel) -> tuple[str, str, str]:
    if level == AlertLevel.CRITICAL:
        return "#b91c1c", "#fef2f2", "🔴"
    if level == AlertLevel.WARNING:
        return "#c2410c", "#fff7ed", "🟠"
    return "#15803d", "#f0fdf4", "🟢"


def _kpi_cell(icon: str, label: str, value_html: str, sub: str = "") -> str:
    sub_html = f'<p style="margin:8px 0 0;font-size:11px;color:#94a3b8;line-height:1.35;">{sub}</p>' if sub else ""
    return (
        f'<td style="width:25%;vertical-align:top;padding:6px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-radius:16px;border:1px solid #e2e8f0;background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);'
        f'box-shadow:0 2px 16px rgba(15,23,42,0.06);min-height:120px;">'
        f'<tr><td style="padding:18px 16px;text-align:center;">'
        f'<p style="margin:0 0 10px;font-size:22px;line-height:1;">{icon}</p>'
        f'<p style="margin:0;font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#64748b;">{esc(label)}</p>'
        f'<p style="margin:10px 0 0;font-size:21px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;line-height:1.15;">{value_html}</p>'
        f"{sub_html}"
        f"</td></tr></table></td>"
    )


def _insights_two_columns(lines: list[str], i18n: I18n) -> str:
    if not lines:
        return f'<p style="color:#64748b;font-size:14px;margin:0;">{esc(i18n.t("no_data"))}</p>'
    n = len(lines)
    mid = (n + 1) // 2
    col1 = lines[:mid]
    col2 = lines[mid:]
    li1 = "".join(
        f'<li style="margin:0 0 10px;padding-left:4px;color:#334155;font-size:13px;line-height:1.55;">{esc(x)}</li>'
        for x in col1
    )
    li2 = "".join(
        f'<li style="margin:0 0 10px;padding-left:4px;color:#334155;font-size:13px;line-height:1.55;">{esc(x)}</li>'
        for x in col2
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:50%;vertical-align:top;padding:0 10px 0 0;">'
        f'<ul style="margin:0;padding:0 0 0 16px;list-style-type:disc;">{li1}</ul></td>'
        f'<td style="width:50%;vertical-align:top;padding:0 0 0 10px;">'
        f'<ul style="margin:0;padding:0 0 0 16px;list-style-type:disc;">{li2}</ul></td>'
        f"</tr></table>"
    )


def render_email_html(data: DailyReportData, i18n: I18n) -> str:
    ws = esc(data.workspace_name)
    date_str = esc(format_report_date(data.report_date, i18n.locale))
    pct = data.team_pct_change_vs_prev
    sign = "+" if pct > 0 else ""
    ref = data.daily_reference_hours if data.daily_reference_hours > 1e-9 else 8.0
    ref_s = esc(fmt_hours(ref))

    hero = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:22px;border-radius:22px;overflow:hidden;background:linear-gradient(135deg,#f8fafc 0%,#eef2ff 50%,#f1f5f9 100%);border:1px solid #e2e8f0;">
<tr><td style="padding:36px 32px;text-align:center;">
<p style="margin:0 0 10px;font-size:10px;letter-spacing:0.28em;text-transform:uppercase;color:#64748b;">Clockify</p>
<h1 style="margin:0;font-size:27px;font-weight:800;color:#0f172a;letter-spacing:-0.03em;line-height:1.2;">
{esc(i18n.t("hero_title"))} – {ws}
</h1>
<p style="margin:16px 0 0;font-size:15px;color:#475569;font-weight:600;">{date_str}</p>
<p style="margin:10px 0 0;font-size:14px;color:#64748b;line-height:1.55;max-width:440px;margin-left:auto;margin-right:auto;">
{esc(i18n.t("hero_sub"))}
</p>
</td></tr></table>
"""

    vs_prev = f"{esc(data.team_change_arrow)} {sign}{pct:.1f} % · {fmt_hours(data.prev_team_total)} veille"
    kpi_row = (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>"
        + _kpi_cell("📊", i18n.t("total_team"), esc(fmt_hours(data.total_team_hours)))
        + _kpi_cell("👥", i18n.t("active_people"), str(data.active_employees))
        + _kpi_cell("⚖️", i18n.t("avg_hours"), esc(fmt_hours(data.avg_hours_per_employee)))
        + _kpi_cell("📈", i18n.t("vs_yesterday"), f'<span style="color:#4f46e5;">{esc(data.team_change_arrow)} {sign}{pct:.1f} %</span>', vs_prev)
        + "</tr></table>"
    )

    prog_cards = []
    for em in data.employees:
        bar_html, _lbl = progress_bar_8h_html(em.total_hours, 280, ref)
        hours_line = f"{esc(fmt_hours(em.total_hours))} / {ref_s}"
        prog_cards.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;border-radius:18px;border:1px solid #e8ecf1;background:#ffffff;box-shadow:0 2px 14px rgba(15,23,42,0.045);">'
            f'<tr><td style="padding:18px 20px;">'
            f'<table role="presentation" width="100%"><tr>'
            f'<td style="vertical-align:middle;width:42%;">'
            f'<p style="margin:0;font-size:15px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">{esc(em.name)}</p>'
            f'<p style="margin:6px 0 0;font-size:12px;color:#64748b;font-weight:600;">{esc(i18n.t("hours_vs_ref"))}</p>'
            f'<p style="margin:4px 0 0;font-size:14px;color:#0f172a;font-weight:700;">{hours_line}</p></td>'
            f'<td align="right" style="vertical-align:middle;">{bar_html}</td>'
            f"</tr></table></td></tr></table>"
        )
    legend = esc(i18n.t("progress_legend"))
    progress_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
<tr><td style="padding:0 0 14px;text-align:center;">
<p style="margin:0;font-size:18px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">⏱ {esc(i18n.t("progress_section"))}</p>
<p style="margin:8px 0 0;font-size:12px;color:#64748b;">{legend} : <strong>{ref_s}</strong> · 🟢 &gt; {ref * 7 / 8:.1f} h · 🟠 {ref * 5 / 8:.1f}–{ref * 7 / 8:.1f} h · 🔴 &lt; {ref * 5 / 8:.1f} h</p>
</td></tr>
<tr><td>{"".join(prog_cards)}</td></tr></table>
"""

    team = data.team_alerts or []
    alert_blocks = []
    for a in team[:40]:
        border, bg, ic = _alert_style(a.level)
        alert_blocks.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">'
            f'<tr><td style="border-left:4px solid {border};background:{bg};padding:14px 16px;border-radius:0 14px 14px 0;">'
            f'<p style="margin:0 0 6px;font-size:12px;font-weight:700;color:{border};">{ic} {esc(a.title)}</p>'
            f'<p style="margin:0;font-size:14px;color:#334155;line-height:1.5;">{esc(a.detail)}</p>'
            f"</td></tr></table>"
        )
    alerts_html = "".join(alert_blocks) or f'<p style="color:#64748b;font-size:14px;">{esc(i18n.t("no_data"))}</p>'
    alerts_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:22px;">
<tr><td style="padding:0 0 12px;text-align:center;">
<p style="margin:0;font-size:18px;font-weight:800;color:#0f172a;">🚨 {esc(i18n.t("team_alerts_title"))}</p>
<p style="margin:8px 0 0;font-size:12px;color:#64748b;">{esc(i18n.t("team_alerts_sub"))}</p>
</td></tr>
<tr><td>{alerts_html}</td></tr></table>
"""

    insights_body = _insights_two_columns(data.insight_lines, i18n)
    insights_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:22px;border-radius:20px;border:1px solid #e5e7eb;background:linear-gradient(180deg,#ffffff 0%,#fafbfc 100%);box-shadow:0 4px 22px rgba(15,23,42,0.055);">
<tr><td style="padding:24px 22px;">
<p style="margin:0 0 6px;font-size:18px;font-weight:800;color:#0f172a;text-align:center;">🧠 {esc(i18n.t("insights"))}</p>
<p style="margin:0 0 18px;font-size:12px;color:#64748b;text-align:center;">{esc(i18n.t("insights_sub"))}</p>
{insights_body}
</td></tr></table>
"""

    rep_cards = []
    for r in data.repeated_tasks[:20]:
        cum = r.hours_report_day + r.hours_previous_day
        rep_cards.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;border-radius:14px;border:1px solid #fde68a;background:linear-gradient(90deg,#fffbeb 0%,#ffffff 100%);">'
            f'<tr><td style="padding:16px 18px;">'
            f'<p style="margin:0;font-size:14px;font-weight:800;color:#92400e;">{esc(r.employee_name)} · {esc(r.task_name)}</p>'
            f'<p style="margin:8px 0 0;font-size:13px;color:#78350f;">Jour : {r.hours_report_day:.2f} h · Veille : {r.hours_previous_day:.2f} h · <strong>Cumul 2 j : {cum:.2f} h</strong></p>'
            f"</td></tr></table>"
        )
    repeated_section = ""
    if rep_cards:
        repeated_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:22px;">
<tr><td style="padding:0 0 12px;text-align:center;">
<p style="margin:0;font-size:18px;font-weight:800;color:#0f172a;">🔁 {esc(i18n.t("repeated_tasks"))}</p>
</td></tr>
<tr><td>{"".join(rep_cards)}</td></tr></table>
"""

    proj_rows = "".join(
        f'<tr><td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;">{esc(p.name)}</td>'
        f'<td align="right" style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:700;">{fmt_hours(p.hours)}</td></tr>'
        for p in data.projects[:12]
    )
    top_s = "".join(
        f'<span style="display:inline-block;margin:4px 10px 4px 0;padding:6px 10px;border-radius:999px;font-size:12px;color:#166534;background:#ecfdf5;"><strong>{esc(n)}</strong> {fmt_hours(h)}</span>'
        for n, h in data.ranking_top
    )
    bot_s = "".join(
        f'<span style="display:inline-block;margin:4px 10px 4px 0;padding:6px 10px;border-radius:999px;font-size:12px;color:#991b1b;background:#fef2f2;"><strong>{esc(n)}</strong> {fmt_hours(h)}</span>'
        for n, h in data.ranking_bottom
    )
    annex = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;border-radius:16px;border:1px solid #eef2f7;background:#fafafa;">
<tr><td style="padding:20px;">
<p style="margin:0 0 12px;font-size:11px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;text-align:center;">{esc(i18n.t("annex"))}</p>
<table role="presentation" width="100%">{proj_rows}</table>
<p style="margin:16px 0 8px;font-size:12px;font-weight:700;color:#475569;text-align:center;">{esc(i18n.t("top3"))}</p><p style="margin:0;text-align:center;">{top_s}</p>
<p style="margin:14px 0 8px;font-size:12px;font-weight:700;color:#475569;text-align:center;">{esc(i18n.t("bottom3"))}</p><p style="margin:0;text-align:center;">{bot_s}</p>
</td></tr></table>
"""

    return f"""<!DOCTYPE html>
<html lang="{esc(i18n.locale)}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light"/>
<title>{esc(i18n.t("hero_title"))}</title>
</head>
<body style="margin:0;padding:0;background:linear-gradient(180deg,#dfe3ea 0%,#e8eaef 100%);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" style="max-width:620px;border-collapse:collapse;">
<tr><td style="padding:0 4px;">
{hero}
{kpi_row}
{progress_section}
{alerts_section}
{insights_section}
{repeated_section}
{annex}
<p style="margin:24px 0 0;text-align:center;font-size:11px;color:#94a3b8;">{esc(i18n.t("footer"))} · {ws}</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

