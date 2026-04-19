"""Textes FR / EN pour le rapport."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class I18n:
    locale: str

    def t(self, key: str) -> str:
        if self.locale == "en":
            return _EN.get(key, _FR.get(key, key))
        return _FR.get(key, key)


_FR = {
    "title": "Rapport temps — équipe",
    "summary": "Vue d'ensemble",
    "total_team": "Heures équipe",
    "active_people": "Personnes actives",
    "avg_hours": "Moyenne / personne",
    "vs_yesterday": "vs veille",
    "alerts": "Alertes intelligentes",
    "level_critical": "Critique",
    "level_warning": "Attention",
    "level_ok": "OK",
    "employees": "Équipe",
    "col_name": "Nom",
    "col_total": "Total",
    "col_tasks": "Tâches",
    "col_main_project": "Projet principal",
    "col_trend": "Tendance",
    "col_status": "Statut",
    "col_score": "Score",
    "status_ok": "OK",
    "status_warn": "Attention",
    "status_crit": "Critique",
    "insights": "Insights productivité",
    "projects": "Projets",
    "project_top3": "Top 3 projets (jour)",
    "ranking": "Classement",
    "top3": "Top 3",
    "bottom3": "3 plus bas",
    "footer": "Rapport automatique Clockify",
    "no_data": "Aucune donnée",
    "uncategorized": "Non classé",
    "productive": "Temps facturable (productif)",
    "non_productive": "Non facturable",
    "priority_vs_other": "Prioritaires vs autres",
    "repeated_tasks": "Tâches longues répétées (2 jours)",
    "projects_flagged": "Projets au-delà du budget indicatif",
}

_EN = {
    "title": "Team time report",
    "summary": "Overview",
    "total_team": "Team hours",
    "active_people": "Active people",
    "avg_hours": "Average / person",
    "vs_yesterday": "vs previous day",
    "alerts": "Smart alerts",
    "level_critical": "Critical",
    "level_warning": "Warning",
    "level_ok": "OK",
    "employees": "Team",
    "col_name": "Name",
    "col_total": "Total",
    "col_tasks": "Tasks",
    "col_main_project": "Main project",
    "col_trend": "Trend",
    "col_status": "Status",
    "col_score": "Score",
    "status_ok": "OK",
    "status_warn": "Warning",
    "status_crit": "Critical",
    "insights": "Productivity insights",
    "projects": "Projects",
    "project_top3": "Top 3 projects (day)",
    "ranking": "Ranking",
    "top3": "Top 3",
    "bottom3": "Bottom 3",
    "footer": "Automated Clockify report",
    "no_data": "No data",
    "uncategorized": "Uncategorized",
    "productive": "Billable (productive)",
    "non_productive": "Non-billable",
    "priority_vs_other": "Priority vs other",
    "repeated_tasks": "Repeated long tasks (2 days)",
    "projects_flagged": "Projects over soft budget",
}
