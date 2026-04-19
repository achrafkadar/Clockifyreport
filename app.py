"""
Rapport quotidien Clockify → e-mail (Resend).
Architecture : config / services / templates / jobs.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from jobs.daily_report import run_daily_email_job
from services.analytics import mock_report_data
from templates.email_report import render_email_html
from utils.i18n import I18n

load_dotenv()

app = FastAPI(title="Clockify daily report", version="2.0.0")


@app.on_event("startup")
def _startup_log() -> None:
    print(f"[clockify-report] PORT={os.environ.get('PORT', '')!r}")
    if not (os.environ.get("CRON_SECRET") or "").strip():
        print(
            "[clockify-report] CRON_SECRET vide : /daily-report et /preview-email accessibles sans mot de passe."
        )


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


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "clockify-daily-report", "version": "2.0"}


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
    return run_daily_email_job()


@app.get("/preview-email", response_class=HTMLResponse)
def preview_email(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> HTMLResponse:
    """Aperçu HTML (données fictives) — même auth que /daily-report si CRON_SECRET défini."""
    _verify_cron(authorization, token)
    loc = (os.environ.get("LOCALE", "fr") or "fr").strip().lower()[:2]
    html = render_email_html(mock_report_data(), I18n(loc))
    return HTMLResponse(content=html)


def main() -> None:
    if "--send-once" in sys.argv:
        os.environ.setdefault("CRON_SECRET", "local-dev")
        print(run_daily_email_job())
        return
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
