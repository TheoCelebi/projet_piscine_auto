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

## Fonctionnement

- **Règles** (`config.yaml`) : par nom d'activité, salle, jours, heure exacte ou plage horaire. Le planning peut changer, le bot réserve toute séance qui correspond (ex. `salle: BALNEO` = tout ce qui se passe dans l'eau).
- **Ouverture** : les réservations ouvrent 48h avant. En mode `--surveiller`, le bot lit le planning toutes les 10 min et se cale à la seconde sur la prochaine ouverture.
- **Séances complètes** : surveillées ; si une place se libère, le bot la prend.
- **Mémoire** (`etat.json`, local) : ce que le bot a réservé. Si une séance réservée par le bot disparaît de « Mes réservations », c'est que tu l'as annulée : le bot ne la reprendra jamais.
- Les séances que tu réserves toi-même sont reconnues et ignorées.

Le bot appelle directement l'API de app.heitzfit.com (centre 1879, Bois-Colombes).

## Sécurité

- Les identifiants vont dans un fichier `.env` local, jamais versionné (voir `.env.example`).
- La configuration personnelle (`config.yaml`), la mémoire du bot (`etat.json`), les sessions navigateur, les logs et les captures d'écran sont ignorés par git.
- Un scan de secrets (gitleaks) tourne à chaque push.
