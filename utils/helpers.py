from __future__ import annotations

import html
from typing import Optional


def esc(s: Optional[str]) -> str:
    return html.escape(s or "", quote=True)


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
