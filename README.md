# projet_piscine_auto

Automatisation de mes inscriptions aux séances de la piscine de Bois-Colombes (Heitzfit4), pour mon usage personnel.

> Projet en cours de mise en place.

## Sécurité

- Les identifiants vont dans un fichier `.env` local, jamais versionné (voir `.env.example`).
- La configuration personnelle (`config.yaml`), les sessions navigateur, les logs et les captures d'écran sont ignorés par git.
- Un scan de secrets (gitleaks) tourne à chaque push.
