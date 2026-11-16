# projet_piscine_auto

Automatisation de mes inscriptions aux séances de la piscine de Bois-Colombes (Heitzfit4), pour mon usage personnel.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # puis remplis ton email et ton mot de passe HeitzFit
cp config.example.yaml config.yaml  # puis adapte les règles
```

## Utilisation

```bash
.venv/bin/python -m piscine_bot                        # simulation : affiche ce qui serait réservé
.venv/bin/python -m piscine_bot --reserver             # un passage : réserve ce qui est ouvert
.venv/bin/python -m piscine_bot --surveiller           # tourne en continu et réserve dès l'ouverture
.venv/bin/python -m piscine_bot --planning 2026-10-21  # planning d'un jour
```

## Gérer les règles (menu)

```bash
.venv/bin/python -m piscine_bot.gerer
```

Ou double-clic sur `Piscine.command` dans le Finder. Le menu permet de voir, ajouter (à partir des vrais noms et horaires du planning) et supprimer des règles, d'avoir un aperçu des séances qui seront réservées, de voir ses réservations HeitzFit, et d'envoyer la config sur GitHub.

## Fonctionnement

- **Règles** (`config.yaml`) : par nom d'activité, salle, jours, heure exacte ou plage horaire. Le planning peut changer, le bot réserve toute séance qui correspond (ex. `salle: BALNEO` = tout ce qui se passe dans l'eau).
- **Ouverture** : les réservations ouvrent 48h avant. En mode `--surveiller`, le bot lit le planning toutes les 10 min et se cale à la seconde sur la prochaine ouverture.
- **Séances complètes** : surveillées ; si une place se libère, le bot la prend.
- **Mémoire** (`etat.json`, local) : ce que le bot a réservé. Si une séance réservée par le bot disparaît de « Mes réservations », c'est que tu l'as annulée : le bot ne la reprendra jamais.
- Les séances que tu réserves toi-même sont reconnues et ignorées.

## Exécution automatique (GitHub Actions)

Le workflow `reservation.yml` est déclenché chaque heure à HH:05 (heure de Paris) par cron-job.org via l’API GitHub (workflow_dispatch), avec un cron GitHub horaire en secours. Le passage de 9h05 attend les ouvertures de 9h15 et réserve à la seconde ; les autres reprennent les places libérées. Chaque passage s’arrête aussitôt : rien ne tourne chez soi.

Secrets à définir dans le dépôt (Settings → Secrets and variables → Actions) :

- `HEITZFIT_EMAIL`, `HEITZFIT_PASSWORD` : identifiants HeitzFit
- `HEITZFIT_CONFIG` : contenu de `config.yaml` (gardé secret pour ne pas publier ses horaires)
- `NTFY_TOPIC` : notifications de l'administrateur ; les autres canaux sont décrits plus haut

Les logs étant publics, le bot y masque le détail des séances. La mémoire (`etat.json`) est conservée d'un passage à l'autre dans le cache GitHub Actions. En cas d'échec, GitHub envoie un email.

Le bot appelle directement l'API de app.heitzfit.com (centre 1879, Bois-Colombes).

## Pour la personne qui va à la piscine

Elle n'a besoin ni du terminal ni de GitHub : tout passe par son téléphone (voir [GUIDE.md](GUIDE.md), à lui donner).

- **Notifications simples** (sans jargon) : séance réservée, place récupérée, annulation prise en compte, limite de l'abonnement atteinte. Boutons « Ouvrir HeitzFit » et « Ajouter à l'agenda ».
- **Rappel la veille** vers 19h et **récapitulatif de la semaine** le dimanche soir.
- **La nuit** (0h-7h), le bot réserve quand même mais les messages arrivent à 8h15 (ntfy) ou sans sonnerie (Telegram).
- **Bot Telegram privé** (facultatif) : boutons « Mes séances », « Ma semaine », « Pause » (vacances), « Mes cours » (activer / désactiver un cours). Il ne répond qu'à sa conversation. Les messages sont lus à chaque passage du bot (environ une fois par heure).
- Les détails techniques (erreurs, séances complètes) ne vont qu'à l'administrateur (`NTFY_TOPIC`), qui reçoit aussi une copie des réservations.

Canaux (secrets GitHub, tous facultatifs) :

| Secret | Rôle |
|---|---|
| `NTFY_TOPIC_MERE` | son sujet ntfy (appli ntfy sur son téléphone) |
| `NTFY_EMAIL_MERE` | copie des notifications par email (envoyée via ntfy.sh) |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | bot Telegram : jeton donné par @BotFather, puis `python -m piscine_bot.telegram` pour trouver l'identifiant de sa conversation |

Les pauses de vacances se règlent aussi dans le menu (`Pauses (vacances)`), ou dans `config.yaml` (`pauses:`).

## Sécurité

- Les identifiants vont dans un fichier `.env` local, jamais versionné (voir `.env.example`).
- La configuration personnelle (`config.yaml`), la mémoire du bot (`etat.json`), les sessions navigateur, les logs et les captures d'écran sont ignorés par git.
- Un scan de secrets (gitleaks) tourne à chaque push.
