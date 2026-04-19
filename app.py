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


@dataclass(frozen=True)
class WorkBucket:
    """Agrégation par personne + projet + tâche."""

    user_id: str
    project_id: str
    task_id: str


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise HTTPException(status_code=500, detail=f"Variable manquante : {name}")
    return v


def _alert_threshold_hours() -> float:
    raw = os.environ.get("PROJECT_HOURS_ALERT_THRESHOLD", "3").strip()
    try:
        return max(0.5, float(raw.replace(",", ".")))
    except ValueError:
        return 3.0


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


def _entry_project_task_labels(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    proj = entry.get("project") if isinstance(entry.get("project"), dict) else {}
    project_id = str(entry.get("projectId") or proj.get("id") or "")
    project_name = (proj.get("name") or entry.get("projectName") or "").strip() or "(Sans projet)"
    task = entry.get("task") if isinstance(entry.get("task"), dict) else {}
    task_id = str(entry.get("taskId") or task.get("id") or "")
    task_name = (task.get("name") or entry.get("taskName") or "").strip()
    if not task_name:
        task_name = "—"
    return project_id, project_name, task_id, task_name


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
    user_names: dict[str, str],
    hours_by_user: dict[str, float],
    detail_rows: list[tuple[str, str, str, str, float]],
    project_over_3h: list[str],
    long_entries: list[str],
    anomalies: list[str],
    recommendations: list[str],
    threshold_h: float,
) -> str:
    """HTML e-mail : tableaux + styles inline (compatibilité clients mail)."""
    tz_label = html.escape(os.environ.get("TIMEZONE", "America/Toronto"))
    title = html.escape(range_info.label)

    # Résumé par personne
    summary_rows = []
    for uid, h in sorted(hours_by_user.items(), key=lambda x: (-x[1], user_names.get(x[0], x[0]))):
        if uid == "unknown":
            continue
        n = html.escape(user_names.get(uid, uid))
        summary_rows.append(
            f"<tr><td style='padding:12px 16px;border-bottom:1px solid #e8e4f0;'>{n}</td>"
            f"<td style='padding:12px 16px;border-bottom:1px solid #e8e4f0;text-align:right;font-weight:600;color:#1e1b4b;'>{h:.2f} h</td></tr>"
        )
    if not summary_rows:
        summary_rows.append(
            "<tr><td colspan='2' style='padding:16px;color:#64748b;'>Aucune entrée sur la période.</td></tr>"
        )

    # Détail projet / tâche — (user_name, project, task, hours) déjà ordonnés
    detail_body = []
    for user_name, project_name, task_name, _uid, hrs in detail_rows:
        detail_body.append(
            f"<tr>"
            f"<td style='padding:10px 14px;border-bottom:1px solid #eef2f7;'>{html.escape(user_name)}</td>"
            f"<td style='padding:10px 14px;border-bottom:1px solid #eef2f7;color:#334155;'>{html.escape(project_name)}</td>"
            f"<td style='padding:10px 14px;border-bottom:1px solid #eef2f7;color:#64748b;font-size:14px;'>{html.escape(task_name)}</td>"
            f"<td style='padding:10px 14px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:600;color:#0f172a;'>{hrs:.2f} h</td>"
            f"</tr>"
        )
    if not detail_body:
        detail_body.append(
            "<tr><td colspan='4' style='padding:16px;color:#64748b;'>—</td></tr>"
        )

    def alert_cards(items: list[str], accent: str) -> str:
        if not items:
            return ""
        cards = []
        for text in items:
            cards.append(
                f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='margin-bottom:10px;'>"
                f"<tr><td style='border-left:4px solid {accent};background:#faf8ff;padding:12px 16px;border-radius:0 8px 8px 0;font-size:14px;line-height:1.45;color:#334155;'>"
                f"{html.escape(text)}</td></tr></table>"
            )
        return "".join(cards)

    def list_block(title: str, items: list[str]) -> str:
        if not items:
            return ""
        lis = "".join(f"<li style='margin:6px 0;'>{html.escape(x)}</li>" for x in items)
        return (
            f"<h3 style='margin:24px 0 12px;font-size:15px;color:#1e1b4b;letter-spacing:0.02em;'>{html.escape(title)}</h3>"
            f"<ul style='margin:0;padding-left:20px;color:#475569;font-size:14px;'>{lis}</ul>"
        )

    over3_title = f"Dépassements — plus de {threshold_h:g} h sur un même projet / tâche"
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width" /><title>Rapport Clockify</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" style="max-width:640px;border-collapse:collapse;">

<tr><td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 50%,#a855f7 100%);border-radius:16px 16px 0 0;padding:28px 24px;">
<p style="margin:0 0 8px;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.85);">Rapport Clockify</p>
<h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff;line-height:1.3;">{title}</h1>
<p style="margin:12px 0 0;font-size:13px;color:rgba(255,255,255,0.9);">Fuseau : {tz_label}</p>
</td></tr>

<tr><td style="background:#ffffff;padding:8px 0 0;"></td></tr>

<tr><td style="background:#ffffff;padding:0 24px 20px;">
<h2 style="margin:0 0 12px;font-size:16px;color:#1e1b4b;">Résumé par personne</h2>
<table role="presentation" width="100%" style="border-collapse:collapse;border-radius:12px;overflow:hidden;border:1px solid #e8e4f0;">
<thead>
<tr style="background:#f8fafc;">
<th align="left" style="padding:12px 16px;font-size:12px;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;">Personne</th>
<th align="right" style="padding:12px 16px;font-size:12px;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;">Total</th>
</tr>
</thead>
<tbody>{''.join(summary_rows)}</tbody>
</table>
</td></tr>

<tr><td style="background:#ffffff;padding:0 24px 24px;">
<h2 style="margin:0 0 12px;font-size:16px;color:#1e1b4b;">Détail par projet &amp; tâche</h2>
<table role="presentation" width="100%" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:12px;">
<thead>
<tr style="background:linear-gradient(180deg,#f8fafc 0%,#f1f5f9 100%);">
<th align="left" style="padding:11px 14px;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;">Personne</th>
<th align="left" style="padding:11px 14px;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;">Projet</th>
<th align="left" style="padding:11px 14px;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;">Tâche</th>
<th align="right" style="padding:11px 14px;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;">Durée</th>
</tr>
</thead>
<tbody>{''.join(detail_body)}</tbody>
</table>
</td></tr>

<tr><td style="background:#fffbeb;padding:20px 24px;border-top:1px solid #fde68a;">
<h2 style="margin:0 0 12px;font-size:15px;color:#92400e;">{html.escape(over3_title)}</h2>
{alert_cards(project_over_3h, "#d97706") if project_over_3h else "<p style='margin:0;color:#78716c;font-size:14px;'>Aucun dépassement sur cette période.</p>"}
</td></tr>

<tr><td style="background:#ffffff;padding:20px 24px;">
{list_block("Autres points d'attention", anomalies)}
{list_block("Recommandations", recommendations)}
{list_block("Entrées très longues (> 8 h)", long_entries)}
</td></tr>

<tr><td style="background:#f8fafc;padding:16px 24px;border-radius:0 0 16px 16px;border-top:1px solid #e2e8f0;">
<p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">Envoi automatique — Wenov · Clockify daily report</p>
</td></tr>

</table>
</td></tr></table>
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
    threshold_h = _alert_threshold_hours()

    range_info = _report_range_for_settings()

    user_names: dict[str, str] = {}
    hours_by_user: dict[str, float] = defaultdict(float)
    # bucket (uid, project_id, task_id) -> hours; labels en parallèle
    bucket_hours: dict[WorkBucket, float] = defaultdict(float)
    bucket_labels: dict[WorkBucket, tuple[str, str, str]] = {}
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
        h = sec / 3600.0
        hours_by_user[uid] += h
        if sec > 8 * 3600:
            desc = (e.get("description") or "(sans description)")[:80]
            long_entries.append(f"{label} — {sec / 3600.0:.1f} h — {desc}")

        pid, pname, tid, tname = _entry_project_task_labels(e)
        b = WorkBucket(user_id=uid, project_id=pid, task_id=tid)
        bucket_hours[b] += h
        bucket_labels[b] = (label, pname, tname)

    # Lignes détail triées
    detail_rows: list[tuple[str, str, str, str, float]] = []
    for b, hrs in bucket_hours.items():
        if b.user_id == "unknown":
            continue
        uname, pname, tname = bucket_labels.get(b, ("", "(Sans projet)", "—"))
        detail_rows.append((uname, pname, tname, b.user_id, hrs))
    detail_rows.sort(key=lambda r: (r[0].lower(), r[1].lower(), r[2].lower()))

    # Alertes > seuil (par personne + projet + tâche)
    project_over_3h: list[str] = []
    for b, hrs in sorted(bucket_hours.items(), key=lambda x: -x[1]):
        if b.user_id == "unknown" or hrs <= threshold_h:
            continue
        uname, pname, tname = bucket_labels.get(b, ("", "", "—"))
        if tname and tname != "—":
            project_over_3h.append(
                f"Le temps sur « {pname} » (tâche : {tname}) pour {uname} dépasse {threshold_h:g} h : {hrs:.2f} h."
            )
        else:
            project_over_3h.append(
                f"Le temps sur le projet « {pname} » pour {uname} dépasse {threshold_h:g} h : {hrs:.2f} h."
            )

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
    if project_over_3h:
        recommendations.append(
            f"Vérifier la répartition ou la charge pour les blocs dépassant {threshold_h:g} h sur un même projet / tâche."
        )
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
    if not recommendations and not anomalies and not project_over_3h:
        recommendations.append("Rien d'anormal sur les seuils automatiques — bon suivi.")

    html_body = _build_email_html(
        range_info,
        user_names,
        dict(hours_by_user),
        detail_rows,
        project_over_3h,
        long_entries,
        anomalies,
        recommendations,
        threshold_h,
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
        "alert_threshold_hours": threshold_h,
        "project_alerts_count": len(project_over_3h),
    }


app = FastAPI(title="Clockify daily report", version="1.0.0")


@app.on_event("startup")
def _warn_if_no_cron_secret() -> None:
    print(f"[clockify-report] PORT effectif (env)={os.environ.get('PORT', '')!r}")
    if not (os.environ.get("CRON_SECRET") or "").strip():
        print(
            "[clockify-report] CRON_SECRET est vide : /daily-report est accessible sans mot de passe. "
            "À éviter si l'app est exposée sur Internet."
        )


@app.get("/")
def root() -> dict[str, str]:
    """Évite les erreurs « no response » si la sonde ou le navigateur ouvre la racine."""
    return {"status": "ok", "service": "clockify-daily-report"}


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
