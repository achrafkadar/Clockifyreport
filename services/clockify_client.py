"""Client Clockify — rapports détaillés & workspace."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

UTC = ZoneInfo("UTC")

CLOCKIFY_API_BASE = os.environ.get("CLOCKIFY_API_BASE_URL", "https://api.clockify.me/api/v1").rstrip("/")
CLOCKIFY_REPORTS_BASE = os.environ.get("CLOCKIFY_REPORTS_BASE_URL", "https://reports.api.clockify.me/v1").rstrip(
    "/"
)


def clockify_headers(api_key: str) -> dict[str, str]:
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def get_workspace_id(client: httpx.Client, api_key: str, name: str) -> str:
    r = client.get(f"{CLOCKIFY_API_BASE}/workspaces", headers=clockify_headers(api_key))
    r.raise_for_status()
    target = name.strip().lower()
    for w in r.json():
        if (w.get("name") or "").strip().lower() == target:
            return w["id"]
    raise ValueError(f'Workspace "{name}" introuvable')


def fetch_workspace_users(client: httpx.Client, api_key: str, workspace_id: str) -> list[dict[str, Any]]:
    r = client.get(
        f"{CLOCKIFY_API_BASE}/workspaces/{workspace_id}/users",
        headers=clockify_headers(api_key),
    )
    r.raise_for_status()
    return r.json()


def _detailed_max_pages() -> int:
    raw = (os.environ.get("CLOCKIFY_DETAILED_MAX_PAGES") or "1000").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 1000
    return max(1, min(n, 50_000))


def fetch_detailed_time_entries(
    client: httpx.Client, api_key: str, workspace_id: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    page = 1
    page_size = 200
    max_pages = _detailed_max_pages()
    prev_fingerprint: Optional[tuple[str, ...]] = None
    while True:
        if page > max_pages:
            raise RuntimeError(
                f"Clockify reports/detailed : pagination arrêtée après {max_pages} page(s) "
                f"({len(entries)} entrées). Augmentez CLOCKIFY_DETAILED_MAX_PAGES si nécessaire."
            )
        body: dict[str, Any] = {
            "dateRangeStart": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dateRangeEnd": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "exportType": "JSON",
            "detailedFilter": {"page": page, "pageSize": page_size},
        }
        r = client.post(
            f"{CLOCKIFY_REPORTS_BASE}/workspaces/{workspace_id}/reports/detailed",
            headers=clockify_headers(api_key),
            json=body,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Clockify reports/detailed {r.status_code}: {r.text[:400]}")
        data = r.json()
        batch = data.get("timeentries") or data.get("timeEntries") or []
        if not batch:
            break
        # Si l'API renvoie toujours la même page, éviter une boucle infinie.
        ids = tuple(
            f"{x.get('id')}|{(x.get('timeInterval') or {}).get('start')}" for x in batch[:page_size]
        )
        if prev_fingerprint is not None and ids == prev_fingerprint:
            raise RuntimeError(
                "Clockify reports/detailed : la page suivante est identique à la précédente "
                "(pagination bloquée côté API). Vérifiez la clé API / le workspace."
            )
        prev_fingerprint = ids
        entries.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return entries


def day_range_utc(d: date, tz_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(d, time.min, tzinfo=tz)
    end_local = datetime.combine(d, time(23, 59, 59, 999999), tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def report_calendar_date(tz_name: str, mode: str) -> tuple[date, str]:
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    mode = (mode or "yesterday").lower()
    if mode == "today":
        d = now.date()
        label = f"Aujourd'hui ({d.isoformat()}) — jusqu'à maintenant"
    else:
        d = (now - timedelta(days=1)).date()
        label = f"Journée complète du {d.isoformat()}"
    return d, label


def report_range_today_partial(tz_name: str) -> tuple[datetime, datetime, date, str]:
    """Pour REPORT_DAY=today : [minuit local, maintenant) en UTC."""
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    d = now.date()
    start_local = datetime.combine(d, time.min, tzinfo=tz)
    end_local = now
    label = f"Aujourd'hui ({d.isoformat()}) — jusqu'à maintenant"
    return start_local.astimezone(UTC), end_local.astimezone(UTC), d, label


def parse_iso_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def entry_duration_seconds(entry: dict[str, Any]) -> float:
    ti = entry.get("timeInterval") or {}
    start = ti.get("start")
    end = ti.get("end")
    if start and end:
        a = parse_iso_dt(start)
        b = parse_iso_dt(end)
        return max(0.0, (b - a).total_seconds())
    dur = entry.get("duration")
    if isinstance(dur, (int, float)) and dur > 0:
        return float(dur) / 1000.0 if dur > 86400000 else float(dur)
    return 0.0


def entry_start_local(entry: dict[str, Any], tz_name: str) -> Optional[datetime]:
    ti = entry.get("timeInterval") or {}
    start = ti.get("start")
    if not start:
        return None
    return parse_iso_dt(start).astimezone(ZoneInfo(tz_name))


def user_label(entry: dict[str, Any], user_names: dict[str, str]) -> tuple[str, str]:
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


def entry_project_task(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    proj = entry.get("project") if isinstance(entry.get("project"), dict) else {}
    project_id = str(entry.get("projectId") or proj.get("id") or "")
    project_name = (proj.get("name") or entry.get("projectName") or "").strip() or "(Sans projet)"
    task = entry.get("task") if isinstance(entry.get("task"), dict) else {}
    task_id = str(entry.get("taskId") or task.get("id") or "")
    task_name = (task.get("name") or entry.get("taskName") or "").strip() or "—"
    return project_id, project_name, task_id, task_name


def entry_billable(entry: dict[str, Any]) -> Optional[bool]:
    if "billable" in entry:
        return bool(entry.get("billable"))
    return None
