# projet_piscine_auto

Automatisation de mes inscriptions aux séances de la piscine de Bois-Colombes (Heitzfit4), pour mon usage personnel.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # puis remplis ton email et ton mot de passe HeitzFit
cp config.example.yaml config.yaml  # puis liste tes séances
```

## Utilisation

```bash
.venv/bin/python -m piscine_bot                        # simulation : affiche ce qui serait réservé
.venv/bin/python -m piscine_bot --reserver             # réserve pour de vrai
.venv/bin/python -m piscine_bot --planning 2026-10-21  # planning d'un jour
```

Le bot appelle directement l'API de app.heitzfit.com (centre 1879, Bois-Colombes) : lecture du planning, connexion, puis réservation des séances qui correspondent à `config.yaml`.

## Sécurité

- Les identifiants vont dans un fichier `.env` local, jamais versionné (voir `.env.example`).
- La configuration personnelle (`config.yaml`), les sessions navigateur, les logs et les captures d'écran sont ignorés par git.
- Un scan de secrets (gitleaks) tourne à chaque push.
