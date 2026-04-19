# Email-agenda — Documentation du projet

Application **FastAPI** qui lit **Google Agenda** (compte `wenovsolutions@gmail.com` ou autre selon config), filtre les événements (production / tournage, convention `{Prod}_Client_Sujet`), et met à jour une **Google Sheet**.

---

## Fonctionnalités

- Synchronisation agenda → feuille (colonnes : Date, Début, Fin, Type, Client, Enregistrement, Titre, Lieu, Description).
- Fenêtre de dates : `DAYS_PAST` + `DAYS_AHEAD` (passé + futur pour bilan mensuel).
- Authentification Google : **compte de service** (fichier JSON ou `GOOGLE_SERVICE_ACCOUNT_JSON_B64` sur Railway).
- Endpoints : **`GET /health`**, **`/sync`** (feuille seule), **`/report/email`** (mail seul), **`/sync-and-report`** (**feuille + mail en une fois**), même auth `CRON_SECRET`.
- Déploiement : **Railway** ; dépôt Git : **https://github.com/achrafkadar/Email-agenda** (à adapter si le repo change).

---

## Convention de titres (agenda)

Format : **`{Tag}_Client_Sujet`**

| Exemple | Type | Client | Enregistrement |
|--------|------|--------|----------------|
| `{Prod}_Stephanebisson_Videostatistique` | Production | Stephanebisson | Videostatistique |
| `{Prod}_Loyaltaxi_Podcast` | Production | Loyaltaxi | Podcast |

- `{Prod}` / `{Production}` → Production ; `{Tour}` / `{Tournage}` → Tournage.
- Sans cette forme, le filtre utilise `FILTER_KEYWORDS` (ex. tournage, production, prod).

---

## Configuration locale

| Fichier | Rôle |
|---------|------|
| `settings.env` | Variables (non commité) : chemins, `SPREADSHEET_ID`, etc. |
| `google-credentials.json` | Clé compte de service (non commitée). |
| `.env.example` | Modèle des variables. |

Commande manuelle : `source .venv/bin/activate` puis `python app.py --once`.

Outil optionnel : **`encode-key.html`** (ouvert dans le navigateur) pour générer le Base64 du JSON sans Terminal.

---

## Variables importantes (Railway et / ou `settings.env`)

| Variable | Rôle |
|----------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | **Recommandé sur Railway** : fichier JSON encodé en Base64 (une ligne). |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Alternative : JSON brut (fragile à coller). |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local uniquement : chemin vers le `.json`. |
| `SPREADSHEET_ID` | ID dans l’URL de la feuille Google. |
| `SHEET_NAME` | Nom de l’onglet (ex. `Planning`). |
| `CALENDAR_ID` | **Adresse Google du calendrier** (ex. `wenovsolutions@gmail.com`). **Ne pas utiliser `primary`** avec un compte de service (c’est l’agenda vide du robot). |
| `CRON_SECRET` | Secret pour protéger `/sync`, `/report/email`, `/sync-and-report` (Bearer ou `?token=`). Voir [Automatisation et cron](#automatisation-et-cron). |
| `DAYS_PAST` / `DAYS_AHEAD` | Fenêtre de dates. |
| `FILTER_KEYWORDS` | Mots-clés si titre hors convention. |
| `TIMEZONE` | Défaut **`America/Toronto`** (Canada Est). Ex. `America/Vancouver` (Pacifique), `Europe/Paris` si besoin. |

Le compte de service (`client_email` dans le JSON) doit avoir accès en **lecture** au calendrier et en **écriture** à la feuille.

---

## Rapport e-mail hebdomadaire (Resend)

- Compte [Resend](https://resend.com) → clé API `RESEND_API_KEY`.
- Variables : `EMAIL_TO` = ton Gmail pour **recevoir** ; **`EMAIL_FROM`** ne peut **pas** être `@gmail.com` (Resend n’autorise pas ce domaine comme expéditeur). Mets **`onboarding@resend.dev`** pour tester, ou un mail sur **un domaine que tu as ajouté et vérifié** sur [resend.com/domains](https://resend.com/domains) (ex. `Agenda <noreply@wenov.ca>`).
- `REPORT_WEEKS_BACK` (défaut **10**) : nombre de semaines glissantes prises en compte pour les tableaux.
- Déclenchement : **GET** ou **POST** `/report/email` avec la même auth que `/sync` (`?token=` ou `Authorization: Bearer`).
- Contenu : **(1)** détail par événement ; **(2)** synthèse par semaine × client ; **(3)** en bas : **résumé global + % par client** (part du nombre de séances sur la période du rapport).
- **`GET` ou `POST /sync-and-report`** : enchaîne **mise à jour de la feuille** puis **envoi du mail** — un seul cron suffit si tu veux les deux à chaque fois.
- Local : `python app.py --email-report` ou `python app.py --sync-and-email`.
- Automatisation : un cron sur **`POST https://…/sync-and-report`** (Bearer), ou garder `/sync` et `/report/email` séparés si tu préfères (détails ci-dessous).
- Si Resend renvoie **403 / erreur 1010** : l’API exige un en-tête **User-Agent** — corrigé dans le code (`email-agenda-sync/1.0`).

---

## Déploiement automatique

1. **GitHub** : push sur `main` peut déclencher un build si le service Railway est **connecté au repo** (réglages du service → source GitHub).
2. **Script `deploy.sh`** (à la racine) : commit (si changements) → `git push origin main` → `railway up`.

```bash
chmod +x deploy.sh
./deploy.sh
./deploy.sh "Description des changements"
```

3. **Cron externe** (ex. [cron-job.org](https://cron-job.org)) : **`POST`** vers **`/sync-and-report`** (recommandé : feuille + mail en une fois) avec `Authorization: Bearer <CRON_SECRET>`. Tu peux encore utiliser uniquement **`/sync`** si tu ne veux pas l’e-mail automatique.

---

## Automatisation et cron

### Un seul job au lieu de deux

Si tu avais **deux** tâches planifiées (`/sync` puis `/report/email`), tu peux les **remplacer par une seule** qui appelle **`POST /sync-and-report`** : même effet (feuille mise à jour, puis envoi du rapport), un seul déclencheur à maintenir.

**URL** (adapte le domaine Railway) :

```text
https://TON_APP.up.railway.app/sync-and-report
```

**Exemple avec `curl`** (cron sur un serveur, script, ou valeur proche sur Railway Cron) :

```bash
curl -sS -X POST "https://TON_APP.up.railway.app/sync-and-report" \
  -H "Authorization: Bearer TON_CRON_SECRET"
```

- Même règle qu’avant : le header **`Authorization: Bearer …`** doit reprendre la valeur exacte de **`CRON_SECRET`** définie sur Railway.
- En test rapide uniquement : **`GET` ou `POST`** avec **`?token=CRON_SECRET`** — **évite** de laisser le token dans l’URL en production ou dans des captures d’écran.
- **Désactive** les anciens jobs qui pointaient séparément vers `/sync` et `/report/email` si tu ne veux pas **doubler** les exécutions.

**Selon l’outil de planification** : cron-job.org, EasyCron, GitHub Actions `schedule`, crontab Linux, etc. — un seul job **POST** vers `/sync-and-report` avec le Bearer suffit.

### Pourquoi `CRON_SECRET` est une variable d’environnement

Ce n’est pas une obligation du mot « cron » : c’est une **pratique de sécurité**.

1. **Protéger les routes** : l’URL de l’app est publique. Sans secret, n’importe qui pourrait déclencher synchro et e-mails. `CRON_SECRET` joue le rôle d’un **mot de passe** pour ces endpoints.
2. **Hors du dépôt Git** : si le secret était écrit en dur dans le code, il serait visible sur GitHub. Les variables Railway / `.env` (non commitées) gardent le secret **hors du repo**.
3. **Changement sans modifier le code** : tu peux **changer** le secret sur Railway (rotation) sans nouveau déploiement du code.
4. **Environnements distincts** : local, staging et prod peuvent avoir des valeurs **différentes**.

Le nom **CRON** indique surtout que c’est souvent le **job planifié** qui envoie ce secret dans **`Authorization: Bearer …`**.

### Cron sur Railway (dashboard)

- **Service web** : l’app FastAPI doit rester **Running** en continu — c’est normal et ce n’est pas « bloqué ».
- **Service Cron** (tâche planifiée) : la commande doit être **courte** et **se terminer** après l’action (typiquement un **`curl`** vers ton HTTPS). Ce n’est **pas** un serveur qui tourne tout le temps.
- **Ne pas** mettre **`railway up`** dans la commande du Cron sur Railway : `railway up` sert à **déployer depuis ton Mac** avec le CLI, pas à exécuter la synchro sur la plateforme.
- **Run now** : l’interface peut rester en chargement **tant que la commande du Cron n’a pas fini**. Si `/sync-and-report` prend plusieurs minutes (Google Agenda + Sheets + mail), l’UI peut sembler « figée » pendant ce temps — regarde les **logs du service Cron** pour voir la progression ou les erreurs (401, timeout, etc.).
- **`CRON_SECRET` sur le Cron** : si la commande utilise `$CRON_SECRET`, cette variable doit aussi être **définie pour le service Cron** (ou partagée comme prévu par Railway), sinon le `curl` part sans bon en-tête → souvent **401**.
- Si une exécution précédente **ne se termine pas**, Railway peut bloquer ou retarder la suivante — vérifier les logs, redéployer si besoin, et s’assurer que la commande **quitte** après le `curl`.

---

## URL Railway (exemple)

- App : `https://email-agenda-production.up.railway.app`
- Santé : `GET /health`
- Sync manuelle (navigateur, test) : `GET /sync?token=CRON_SECRET` (ne pas partager l’URL avec le token).

---

## Dépannage rapide

| Problème | Piste |
|----------|--------|
| Feuille vide, `events_total: 0` | `CALENDAR_ID` = e-mail du bon agenda, pas `primary` ; partage avec le compte de service. |
| Erreur JSON sur la clé | Utiliser `GOOGLE_SERVICE_ACCOUNT_JSON_B64`. |
| 401 sur `/sync` | `Authorization: Bearer …` identique à `CRON_SECRET` sur Railway. |
| « Run now » du Cron Railway qui charge longtemps | Souvent : synchro longue — consulter les **logs du Cron** ; ou exécution précédente non terminée. Voir [Cron sur Railway](#cron-sur-railway-dashboard). |
| Beaucoup d’événements mais peu de lignes | Normal : seuls les titres qui passent le filtre sont exportés. |

---

## Structure des fichiers principaux

```
Email-agenda/
├── app.py              # Application FastAPI + logique sync
├── requirements.txt
├── Procfile            # Démarrage uvicorn sur Railway
├── deploy.sh           # Push Git + déploiement Railway
├── encode-key.html     # Base64 de la clé (navigateur, local)
├── DOCUMENTATION.md    # Ce fichier
├── .env.example
├── settings.env        # Local, non versionné
└── .gitignore
```

---

## Sécurité

- Ne jamais committer `settings.env`, `.env`, `google-credentials.json` ni tokens.
- Ne pas partager les URL contenant `?token=`.

---

*Document généré pour le projet Email-agenda — synchronisation Google Agenda → Google Sheets via Railway.*
