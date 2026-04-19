"""
Rapport quotidien Clockify → e-mail (Resend).
Déclenchement : POST /daily-report avec CRON_SECRET (Bearer ou ?token=).
"""

from __future__ import annotations

import html
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query

load_dotenv()

UTC = ZoneInfo("UTC")

CLOCKIFY_API_BASE = os.environ.get("CLOCKIFY_API_BASE_URL", "https://api.clockify.me/api/v1").rstrip("/")
CLOCKIFY_REPORTS_BASE = os.environ.get("CLOCKIFY_REPORTS_BASE_URL", "https://reports.api.clockify.me/v1").rstrip(
    "/"
)

RESEND_USER_AGENT = "clockify-daily-report/1.0"


@dataclass
class ReportRange:
    label: str
    start_utc: datetime
    end_utc: datetime
    report_date: date


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise HTTPException(status_code=500, detail=f"Variable manquante : {name}")
    return v


def _parse_iso_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _entry_duration_seconds(entry: dict[str, Any]) -> float:
    ti = entry.get("timeInterval") or {}
    start = ti.get("start")
    end = ti.get("end")
    if start and end:
        a = _parse_iso_dt(start)
        b = _parse_iso_dt(end)
        return max(0.0, (b - a).total_seconds())
    dur = entry.get("duration")
    if isinstance(dur, (int, float)) and dur > 0:
        return float(dur) / 1000.0 if dur > 86400000 else float(dur)
    return 0.0


def _report_range_for_settings() -> ReportRange:
    tz_name = os.environ.get("TIMEZONE", "America/Toronto")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TIMEZONE invalide : {tz_name}") from exc

    mode = (os.environ.get("REPORT_DAY", "yesterday") or "yesterday").strip().lower()
    now = datetime.now(tz)

    if mode == "today":
        d = now.date()
        start_local = datetime.combine(d, time.min, tzinfo=tz)
        end_local = now
        label = f"Aujourd'hui ({d.isoformat()}) — jusqu'à maintenant"
    elif mode == "yesterday":
        d = (now - timedelta(days=1)).date()
        start_local = datetime.combine(d, time.min, tzinfo=tz)
        end_local = datetime.combine(d, time(23, 59, 59, 999999), tzinfo=tz)
        label = f"Journée complète du {d.isoformat()}"
    else:
        raise HTTPException(status_code=500, detail="REPORT_DAY doit être 'yesterday' ou 'today'")

    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)
    return ReportRange(label=label, start_utc=start_utc, end_utc=end_utc, report_date=d)


def _clockify_headers(api_key: str) -> dict[str, str]:
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def _get_workspace_id(client: httpx.Client, api_key: str, name: str) -> str:
    r = client.get(f"{CLOCKIFY_API_BASE}/workspaces", headers=_clockify_headers(api_key))
    r.raise_for_status()
    workspaces = r.json()
    target = name.strip().lower()
    for w in workspaces:
        if (w.get("name") or "").strip().lower() == target:
            return w["id"]
    raise HTTPException(
        status_code=404,
        detail=f'Workspace "{name}" introuvable. Vérifie CLOCKIFY_WORKSPACE_NAME.',
    )


def _fetch_workspace_users(client: httpx.Client, api_key: str, workspace_id: str) -> list[dict[str, Any]]:
    r = client.get(
        f"{CLOCKIFY_API_BASE}/workspaces/{workspace_id}/users",
        headers=_clockify_headers(api_key),
    )
    r.raise_for_status()
    return r.json()


def _fetch_detailed_time_entries(
    client: httpx.Client, api_key: str, workspace_id: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    page = 1
    page_size = 200

    body_base: dict[str, Any] = {
        "dateRangeStart": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "dateRangeEnd": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "exportType": "JSON",
        "detailedFilter": {"page": page, "pageSize": page_size},
    }

    while True:
        body = {**body_base, "detailedFilter": {"page": page, "pageSize": page_size}}
        r = client.post(
            f"{CLOCKIFY_REPORTS_BASE}/workspaces/{workspace_id}/reports/detailed",
            headers=_clockify_headers(api_key),
            json=body,
        )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Clockify reports/detailed : {r.status_code} — {r.text[:500]}",
            )
        data = r.json()
        batch = data.get("timeentries") or data.get("timeEntries") or []
        if not batch:
            break
        entries.extend(batch)
        if len(batch) < page_size:
            break
        page += 1

    return entries


def _user_label(entry: dict[str, Any], user_names: dict[str, str]) -> tuple[str, str]:
    uid = entry.get("userId")
    u = entry.get("user")
    if isinstance(u, dict):
        uid = uid or u.get("id")
        name = u.get("name") or u.get("email")
        if uid and name:
            user_names.setdefault(uid, name)
            return uid, name
    if uid:
        return uid, user_names.get(uid, uid)
    return "unknown", "Inconnu"


def _build_email_html(
    range_info: ReportRange,
    hours_by_user: dict[str, float],
    user_names: dict[str, str],
    long_entries: list[str],
    anomalies: list[str],
    recommendations: list[str],
) -> str:
    rows = []
    for uid, h in sorted(hours_by_user.items(), key=lambda x: (-x[1], user_names.get(x[0], x[0]))):
        name = html.escape(user_names.get(uid, uid))
        rows.append(f"<tr><td>{name}</td><td style='text-align:right'>{h:.2f} h</td></tr>")

    if not rows:
        rows.append("<tr><td colspan='2'>Aucune entrée sur la période.</td></tr>")

    def list_section(title: str, items: list[str]) -> str:
        if not items:
            return ""
        lis = "".join(f"<li>{html.escape(x)}</li>" for x in items)
        return f"<h3>{html.escape(title)}</h3><ul>{lis}</ul>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Rapport Clockify</title></head>
<body style="font-family:system-ui,Segoe UI,sans-serif;line-height:1.5;color:#111;">
<h2>Rapport Clockify — {html.escape(range_info.label)}</h2>
<p>Fuseau : {html.escape(os.environ.get("TIMEZONE", "America/Toronto"))}</p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;border-color:#ccc;">
<thead><tr><th>Personne</th><th>Temps déclaré</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
{list_section("Anomalies / points d'attention", anomalies)}
{list_section("Recommandations", recommendations)}
{list_section("Entrées très longues (&gt; 8 h)", long_entries)}
<hr><p style="color:#666;font-size:12px;">Envoi automatique — Clockify daily report</p>
</body></html>"""


def _send_resend(to_addr: str, from_addr: str, subject: str, html_body: str) -> None:
    api_key = _require_env("RESEND_API_KEY")
    payload = {"from": from_addr, "to": [to_addr], "subject": subject, "html": html_body}
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": RESEND_USER_AGENT},
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Resend : {r.status_code} — {r.text[:500]}")


def _verify_cron(authorization: Optional[str], token: Optional[str]) -> None:
    secret = (os.environ.get("CRON_SECRET") or "").strip()
    if not secret:
        return
    if token and token == secret:
        return
    if authorization and authorization.startswith("Bearer "):
        if authorization[7:].strip() == secret:
            return
    raise HTTPException(status_code=401, detail="Non autorisé")


def run_daily_report() -> dict[str, Any]:
    api_key = _require_env("CLOCKIFY_API_KEY")
    workspace_name = os.environ.get("CLOCKIFY_WORKSPACE_NAME", "Wenov").strip()
    email_to = os.environ.get("EMAIL_TO", "Ads@wenov.ca").strip()
    email_from = _require_env("EMAIL_FROM")

    range_info = _report_range_for_settings()

    user_names: dict[str, str] = {}
    hours_by_user: dict[str, float] = defaultdict(float)
    long_entries: list[str] = []

    entries: list[dict[str, Any]] = []
    with httpx.Client(timeout=120.0) as client:
        workspace_id = _get_workspace_id(client, api_key, workspace_name)
        ws_users = _fetch_workspace_users(client, api_key, workspace_id)
        for u in ws_users:
            uid = u.get("id")
            if uid:
                user_names[uid] = (u.get("name") or u.get("email") or uid)[:200]

        entries = _fetch_detailed_time_entries(
            client, api_key, workspace_id, range_info.start_utc, range_info.end_utc
        )

    for e in entries:
        uid, label = _user_label(e, user_names)
        if uid != "unknown":
            user_names[uid] = label
        sec = _entry_duration_seconds(e)
        hours_by_user[uid] += sec / 3600.0
        if sec > 8 * 3600:
            desc = (e.get("description") or "(sans description)")[:80]
            long_entries.append(f"{label} — {sec / 3600.0:.1f} h — {desc}")

    anomalies: list[str] = []
    for uid, h in hours_by_user.items():
        if uid == "unknown":
            continue
        if h > 12:
            anomalies.append(f"{user_names.get(uid, uid)} : total élevé ({h:.1f} h).")

    report_d = range_info.report_date
    if report_d.weekday() < 5:
        for u in ws_users:
            if (u.get("status") or "").upper() != "ACTIVE":
                continue
            uid = u.get("id")
            if not uid:
                continue
            h = hours_by_user.get(uid, 0.0)
            if h < 1e-6:
                name = u.get("name") or u.get("email") or uid
                anomalies.append(f"{name} : aucune heure déclarée ce jour-là (jour ouvré).")

    recommendations: list[str] = []
    if long_entries:
        recommendations.append(
            "Vérifier les entrées de plus de 8 h (pause oubliée ou mauvais découpage)."
        )
    if any("total élevé" in a for a in anomalies):
        recommendations.append("Valider les heures supplémentaires ou la charge avec la personne concernée.")
    if any("aucune heure" in a for a in anomalies):
        recommendations.append(
            "Demander une mise à jour Clockify ou noter l'absence / congé si c'était prévu."
        )
    if not recommendations and not anomalies:
        recommendations.append("Rien d'anormal sur les seuils automatiques — bon suivi.")

    html_body = _build_email_html(
        range_info, dict(hours_by_user), user_names, long_entries, anomalies, recommendations
    )
    subject = f"[Clockify] Rapport {range_info.report_date.isoformat()} — {workspace_name}"
    _send_resend(email_to, email_from, subject, html_body)

    return {
        "ok": True,
        "workspace": workspace_name,
        "report_date": range_info.report_date.isoformat(),
        "recipients": [email_to],
        "people_count": len([k for k in hours_by_user if k != "unknown"]),
        "entries_fetched": len(entries),
    }


app = FastAPI(title="Clockify daily report", version="1.0.0")


@app.on_event("startup")
def _warn_if_no_cron_secret() -> None:
    if not (os.environ.get("CRON_SECRET") or "").strip():
        print(
            "[clockify-report] CRON_SECRET est vide : /daily-report est accessible sans mot de passe. "
            "À éviter si l'app est exposée sur Internet."
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/daily-report")
@app.get("/daily-report")
def daily_report(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> dict[str, Any]:
    _verify_cron(authorization, token)
    return run_daily_report()


def main() -> None:
    if "--send-once" in sys.argv:
        os.environ.setdefault("CRON_SECRET", "local-dev")
        out = run_daily_report()
        print(out)
        return
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
