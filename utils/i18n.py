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
    "hero_title": "Rapport quotidien de productivité",
    "hero_sub": "Vue globale de l'activité et des anomalies",
    "progress_section": "Temps par personne (référence 8 h)",
    "team_alerts_title": "Alertes équipe",
    "team_alerts_sub": "Uniquement : personnes sans temps saisi (jour ouvré).",
    "annex": "Synthèse projets & classement",
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
    "insights": "Projets de la journée",
    "insights_sub": "Où l’équipe a enregistré du temps sur la même période que le rapport.",
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
    "hours_vs_ref": "Temps saisi / objectif journée",
    "progress_legend": "Référence journée",
    "projects_flagged": "Projets au-delà du budget indicatif",
}

_EN = {
    "hero_title": "Daily productivity report",
    "hero_sub": "Activity overview and anomalies",
    "progress_section": "Time per person (8 h reference)",
    "team_alerts_title": "Team alerts",
    "team_alerts_sub": "Only: people with no time logged (business day).",
    "annex": "Projects & ranking",
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
    "insights": "Projects for the day",
    "insights_sub": "Where the team logged time on the same period as this report.",
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
    "hours_vs_ref": "Logged / daily target",
    "progress_legend": "Daily reference",
    "projects_flagged": "Projects over soft budget",
}
