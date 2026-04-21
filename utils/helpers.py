from __future__ import annotations

import html
from datetime import date
from typing import Optional

_MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def esc(s: Optional[str]) -> str:
    return html.escape(s or "", quote=True)


def format_report_date(d: date, locale: str) -> str:
    if locale == "en":
        return d.strftime("%B %d, %Y")
    return f"{d.day} {_MOIS_FR[d.month - 1]} {d.year}"


def progress_bar_8h_html(hours: float, width_px: int = 260, ref_hours: float = 8.0) -> tuple[str, str]:
    """
    Barre sur une journée de référence (souvent 8 h).
    Couleur : vert > ~87,5 %, orange ~62,5–87,5 %, rouge en dessous.
    """
    ref = ref_hours if ref_hours > 1e-9 else 8.0
    pct = min(100.0, max(0.0, (hours / ref) * 100.0))
    inner = int(round((pct / 100.0) * width_px))
    hi = ref * 7.0 / 8.0
    mid = ref * 5.0 / 8.0
    if hours > hi:
        fill, label = "#16a34a", "OK"
    elif hours >= mid:
        fill, label = "#ea580c", "Attention"
    else:
        fill, label = "#dc2626", "Faible"
    track = "#e5e7eb"
    html_bar = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:{width_px}px;height:12px;'
        f'background:{track};border-radius:999px;overflow:hidden;border-collapse:collapse;">'
        f'<tr><td style="width:{inner}px;min-width:8px;height:12px;background:{fill};border-radius:999px 0 0 999px;"></td>'
        f'<td style="background:{track};"></td></tr></table>'
        f'<span style="font-size:11px;color:#64748b;margin-left:8px;">{pct:.0f}% / {ref:g} h</span>'
    )
    return html_bar, label


def mini_ratio_bar(label: str, value: float, total: float, color: str, width_px: int = 200) -> str:
    if total <= 1e-9:
        pct = 0.0
    else:
        pct = min(100.0, (value / total) * 100.0)
    inner = int(round((pct / 100.0) * width_px))
    return (
        f'<p style="margin:0 0 4px;font-size:12px;color:#475569;">{label}</p>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:{width_px}px;height:8px;'
        f'background:#e5e7eb;border-radius:6px;overflow:hidden;"><tr>'
        f'<td style="width:{inner}px;height:8px;background:{color};border-radius:6px 0 0 6px;"></td>'
        f'<td style="background:#e5e7eb;"></td></tr></table>'
        f'<p style="margin:4px 0 0;font-size:11px;color:#64748b;">{pct:.0f}% · {value:.1f} h</p>'
    )


def parse_email_recipients(raw: str) -> list[str]:
    """Plusieurs adresses séparées par des virgules ou points-virgules."""
    if not raw or not raw.strip():
        return []
    out: list[str] = []
    for part in raw.replace(";", ",").split(","):
        p = part.strip()
        if p and "@" in p:
            out.append(p)
    return out


def fmt_hours(h: float) -> str:
    return f"{h:.2f} h"


def pct_change_str(prev: float, curr: float) -> str:
    if prev <= 1e-9:
        if curr <= 1e-9:
            return "0 %"
        return "+100 %"
    d = (curr - prev) / prev * 100.0
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.1f} %"


def progress_bar_html(pct: float, width_px: int = 120) -> str:
    """Barre horizontale 0–100 % (HTML e-mail)."""
    p = max(0.0, min(100.0, pct))
    inner = int(round((p / 100.0) * width_px))
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:{width_px}px;height:8px;'
        f'background:#e2e8f0;border-radius:4px;overflow:hidden;">'
        f'<tr><td style="width:{inner}px;height:8px;background:#6366f1;border-radius:4px 0 0 4px;"></td>'
        f'<td style="background:#e2e8f0;"></td></tr></table>'
    )
