"""Template e-mail premium (CSS inline) — ordre : hero → KPI → barres 8h → alertes → insights → tâches répétées."""

from __future__ import annotations

from services.report_model import AlertLevel, DailyReportData
from utils.helpers import (
    esc,
    fmt_hours,
    format_report_date,
    mini_ratio_bar,
    progress_bar_8h_html,
)
from utils.i18n import I18n


def _alert_style(level: AlertLevel) -> tuple[str, str, str]:
    if level == AlertLevel.CRITICAL:
        return "#b91c1c", "#fef2f2", "🔴"
    if level == AlertLevel.WARNING:
        return "#c2410c", "#fff7ed", "🟠"
    return "#15803d", "#f0fdf4", "🟢"


def _kpi_card(icon: str, label: str, value_html: str, sub: str = "") -> str:
    sub_html = f'<p style="margin:6px 0 0;font-size:11px;color:#94a3b8;">{sub}</p>' if sub else ""
    return (
        f'<td style="width:25%;vertical-align:top;padding:8px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-radius:14px;border:1px solid #eceef2;background:#ffffff;box-shadow:0 4px 24px rgba(15,23,42,0.06);">'
        f'<tr><td style="padding:16px 14px;">'
        f'<p style="margin:0 0 8px;font-size:20px;line-height:1;">{icon}</p>'
        f'<p style="margin:0;font-size:11px;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;color:#64748b;">{esc(label)}</p>'
        f'<p style="margin:8px 0 0;font-size:22px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">{value_html}</p>'
        f"{sub_html}"
        f"</td></tr></table></td>"
    )


def render_email_html(data: DailyReportData, i18n: I18n) -> str:
    ws = esc(data.workspace_name)
    date_str = esc(format_report_date(data.report_date, i18n.locale))
    pct = data.team_pct_change_vs_prev
    sign = "+" if pct > 0 else ""

    # --- 1. Hero
    hero = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border-radius:20px;overflow:hidden;background:linear-gradient(180deg,#f8fafc 0%,#f1f5f9 100%);border:1px solid #e2e8f0;">
<tr><td style="padding:32px 28px;text-align:center;">
<p style="margin:0 0 8px;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#64748b;">Clockify</p>
<h1 style="margin:0;font-size:26px;font-weight:800;color:#0f172a;letter-spacing:-0.03em;line-height:1.2;">
{esc(i18n.t("hero_title"))} – {ws}
</h1>
<p style="margin:14px 0 0;font-size:15px;color:#475569;font-weight:500;">{date_str}</p>
<p style="margin:8px 0 0;font-size:14px;color:#64748b;line-height:1.5;max-width:420px;margin-left:auto;margin-right:auto;">
{esc(i18n.t("hero_sub"))}
</p>
</td></tr></table>
"""

    # --- 2. KPI cards
    vs_prev = f"{esc(data.team_change_arrow)} {sign}{pct:.1f} % · {fmt_hours(data.prev_team_total)} veille"
    kpi_row = (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>"
        + _kpi_card("📊", i18n.t("total_team"), esc(fmt_hours(data.total_team_hours)))
        + _kpi_card("👥", i18n.t("active_people"), str(data.active_employees))
        + _kpi_card("⚖️", i18n.t("avg_hours"), esc(fmt_hours(data.avg_hours_per_employee)))
        + _kpi_card("📈", i18n.t("vs_yesterday"), f'<span style="color:#4f46e5;">{esc(data.team_change_arrow)} {sign}{pct:.1f} %</span>', vs_prev)
        + "</tr></table>"
    )

    # --- 3. Barres 8h par employé
    prog_cards = []
    for em in data.employees:
        bar_html, _lbl = progress_bar_8h_html(em.total_hours, 280)
        prog_cards.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;border-radius:16px;border:1px solid #eef2f7;background:#ffffff;box-shadow:0 2px 12px rgba(15,23,42,0.04);">'
            f'<tr><td style="padding:16px 18px;">'
            f'<table role="presentation" width="100%"><tr>'
            f'<td style="vertical-align:middle;"><p style="margin:0;font-size:15px;font-weight:700;color:#0f172a;">{esc(em.name)}</p>'
            f'<p style="margin:4px 0 0;font-size:13px;color:#64748b;">{esc(fmt_hours(em.total_hours))}</p></td>'
            f'<td align="right" style="vertical-align:middle;">{bar_html}</td>'
            f"</tr></table></td></tr></table>"
        )
    progress_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:18px;">
<tr><td style="padding:0 0 12px;">
<p style="margin:0;font-size:17px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">⏱ {esc(i18n.t("progress_section"))}</p>
<p style="margin:6px 0 0;font-size:12px;color:#64748b;">🟢 &gt; 7 h · 🟠 5–7 h · 🔴 &lt; 5 h (référence journée 8 h)</p>
</td></tr>
<tr><td>{''.join(prog_cards)}</td></tr></table>
"""

    # --- 4. Alertes équipe (filtrées)
    team = data.team_alerts or []
    alert_blocks = []
    for a in team[:35]:
        border, bg, ic = _alert_style(a.level)
        alert_blocks.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">'
            f'<tr><td style="border-left:4px solid {border};background:{bg};padding:14px 16px;border-radius:0 12px 12px 0;">'
            f'<p style="margin:0 0 6px;font-size:12px;font-weight:700;color:{border};">{ic} {esc(a.title)}</p>'
            f'<p style="margin:0;font-size:14px;color:#334155;line-height:1.5;">{esc(a.detail)}</p>'
            f"</td></tr></table>"
        )
    alerts_html = "".join(alert_blocks) or f'<p style="color:#64748b;font-size:14px;">{esc(i18n.t("no_data"))}</p>'
    alerts_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
<tr><td style="padding:0 0 10px;">
<p style="margin:0;font-size:17px;font-weight:800;color:#0f172a;">🚨 {esc(i18n.t("team_alerts_title"))}</p>
</td></tr>
<tr><td>{alerts_html}</td></tr></table>
"""

    # --- 5. Insights + mini-barres
    tot_pn = data.productive_hours + data.non_productive_hours
    tot_prio = data.priority_hours + data.other_hours
    tot_team = data.total_team_hours or 1e-9
    ins_text = "".join(
        f'<li style="margin:8px 0;color:#334155;font-size:14px;line-height:1.5;">{esc(x)}</li>' for x in data.insight_lines
    )
    bar_prod = mini_ratio_bar(i18n.t("productive"), data.productive_hours, tot_pn, "#6366f1")
    bar_nonp = mini_ratio_bar(i18n.t("non_productive"), data.non_productive_hours, tot_pn, "#94a3b8")
    bar_pri = mini_ratio_bar("Prioritaires", data.priority_hours, tot_prio, "#0ea5e9")
    bar_oth = mini_ratio_bar("Secondaires", data.other_hours, tot_prio, "#cbd5e1")
    bar_unc = mini_ratio_bar(i18n.t("uncategorized"), data.uncategorized_hours, tot_team, "#f59e0b")
    insights_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border-radius:18px;border:1px solid #e8e8ec;background:#ffffff;box-shadow:0 4px 20px rgba(15,23,42,0.05);">
<tr><td style="padding:22px 22px;">
<p style="margin:0 0 12px;font-size:17px;font-weight:800;color:#0f172a;">🧠 {esc(i18n.t("insights"))}</p>
<ul style="margin:0 0 16px;padding-left:20px;">{ins_text}</ul>
<table role="presentation" width="100%"><tr>
<td style="width:50%;vertical-align:top;padding-right:10px;">{bar_prod}{bar_nonp}</td>
<td style="width:50%;vertical-align:top;padding-left:10px;">{bar_pri}{bar_oth}</td>
</tr></table>
<div style="margin-top:14px;">{bar_unc}</div>
</td></tr></table>
"""

    # --- 6. Tâches répétées (2 jours)
    rep_cards = []
    for r in data.repeated_tasks[:20]:
        cum = r.hours_report_day + r.hours_previous_day
        rep_cards.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;border-radius:12px;border:1px solid #fde68a;background:#fffbeb;">'
            f'<tr><td style="padding:14px 16px;">'
            f'<p style="margin:0;font-size:14px;font-weight:700;color:#92400e;">{esc(r.employee_name)} · {esc(r.task_name)}</p>'
            f'<p style="margin:6px 0 0;font-size:13px;color:#78350f;">Jour : {r.hours_report_day:.2f} h · Veille : {r.hours_previous_day:.2f} h · <strong>Cumul 2 j : {cum:.2f} h</strong></p>'
            f"</td></tr></table>"
        )
    repeated_section = ""
    if rep_cards:
        repeated_section = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
<tr><td style="padding:0 0 10px;">
<p style="margin:0;font-size:17px;font-weight:800;color:#0f172a;">🔁 {esc(i18n.t("repeated_tasks"))}</p>
</td></tr>
<tr><td>{''.join(rep_cards)}</td></tr></table>
"""

    # --- Annexe : projets + classement (compact)
    proj_rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px;">{esc(p.name)}</td>'
        f'<td align="right" style="padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:600;">{fmt_hours(p.hours)}</td></tr>'
        for p in data.projects[:12]
    )
    top_s = "".join(f'<span style="display:inline-block;margin:4px 8px 4px 0;font-size:12px;color:#166534;"><strong>{esc(n)}</strong> {fmt_hours(h)}</span>' for n, h in data.ranking_top)
    bot_s = "".join(f'<span style="display:inline-block;margin:4px 8px 4px 0;font-size:12px;color:#b91c1c;"><strong>{esc(n)}</strong> {fmt_hours(h)}</span>' for n, h in data.ranking_bottom)
    annex = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;border-radius:14px;border:1px solid #eef2f7;background:#fafafa;">
<tr><td style="padding:18px;">
<p style="margin:0 0 10px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">{esc(i18n.t("annex"))}</p>
<table role="presentation" width="100%">{proj_rows}</table>
<p style="margin:14px 0 6px;font-size:12px;font-weight:600;color:#475569;">{esc(i18n.t("top3"))}</p><p style="margin:0;">{top_s}</p>
<p style="margin:10px 0 6px;font-size:12px;font-weight:600;color:#475569;">{esc(i18n.t("bottom3"))}</p><p style="margin:0;">{bot_s}</p>
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
<body style="margin:0;padding:0;background:#e8eaef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#e8eaef;padding:28px 14px;">
<tr><td align="center">
<table role="presentation" width="100%" style="max-width:640px;border-collapse:collapse;">
<tr><td>
{hero}
{kpi_row}
{progress_section}
{alerts_section}
{insights_section}
{repeated_section}
{annex}
<p style="margin:20px 0 0;text-align:center;font-size:11px;color:#94a3b8;">{esc(i18n.t("footer"))} · {ws}</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
