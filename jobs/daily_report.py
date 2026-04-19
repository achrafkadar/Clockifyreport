"""Orchestration : Clockify → analytics → Resend."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import httpx
from fastapi import HTTPException

from config.settings import load_config
from services.analytics import build_daily_report
from services.clockify_client import (
    day_range_utc,
    fetch_detailed_time_entries,
    fetch_workspace_users,
    get_workspace_id,
    report_calendar_date,
    report_range_today_partial,
)
from templates.email_report import render_email_html
from utils.helpers import parse_email_recipients
from utils.i18n import I18n

RESEND_USER_AGENT = "clockify-daily-report/2.0"


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise HTTPException(status_code=500, detail=f"Variable manquante : {name}")
    return v


def _send_resend(to_addrs: list[str], from_addr: str, subject: str, html_body: str) -> None:
    api_key = _require_env("RESEND_API_KEY")
    payload = {"from": from_addr, "to": to_addrs, "subject": subject, "html": html_body}
    with httpx.Client(timeout=90.0) as client:
        r = client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": RESEND_USER_AGENT},
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Resend : {r.status_code} — {r.text[:500]}")


def run_daily_email_job() -> dict[str, Any]:
    cfg = load_config()
    api_key = _require_env("CLOCKIFY_API_KEY")
    raw_to = os.environ.get(
        "EMAIL_TO",
        "ads@wenov.ca,wenovsolutions@gmail.com",
    ).strip()
    recipients = parse_email_recipients(raw_to)
    if not recipients:
        raise HTTPException(status_code=500, detail="EMAIL_TO vide ou invalide (liste d’e-mails séparés par des virgules).")
    email_from = _require_env("EMAIL_FROM")
    workspace_name = cfg.workspace_name
    i18n = I18n(cfg.locale)

    if cfg.report_day == "today":
        start_utc, end_utc, report_date, period_label = report_range_today_partial(cfg.timezone)
        compare_date = report_date - timedelta(days=1)
    else:
        report_date, period_label = report_calendar_date(cfg.timezone, "yesterday")
        start_utc, end_utc = day_range_utc(report_date, cfg.timezone)
        compare_date = report_date - timedelta(days=1)

    c_start, c_end = day_range_utc(compare_date, cfg.timezone)

    try:
        with httpx.Client(timeout=120.0) as client:
            workspace_id = get_workspace_id(client, api_key, workspace_name)
            ws_users = fetch_workspace_users(client, api_key, workspace_id)
            entries_report = fetch_detailed_time_entries(client, api_key, workspace_id, start_utc, end_utc)
            entries_compare = fetch_detailed_time_entries(client, api_key, workspace_id, c_start, c_end)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    report = build_daily_report(
        cfg,
        report_date,
        period_label,
        cfg.timezone,
        workspace_name,
        entries_report,
        entries_compare,
        ws_users,
    )

    html_body = render_email_html(report, i18n)
    subject = f"[Clockify] {workspace_name} — {report_date.isoformat()}"
    _send_resend(recipients, email_from, subject, html_body)

    return {
        "ok": True,
        "workspace": workspace_name,
        "report_date": report_date.isoformat(),
        "recipients": recipients,
        "team_hours": round(report.total_team_hours, 2),
        "alerts_count": len(report.alerts),
        "entries_report": len(entries_report),
        "entries_compare_day": len(entries_compare),
    }
