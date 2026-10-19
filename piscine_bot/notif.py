"""Notifications sur téléphone via ntfy.sh (appli ntfy, abonnement au sujet NTFY_TOPIC)."""

import os

import requests


def notifier(titre, message, tags=(), priorite=3):
    """N'échoue jamais : une notification ratée ne doit pas faire échouer une réservation."""
    sujet = os.getenv("NTFY_TOPIC", "").strip()
    if not sujet:
        return
    try:
        # Publication JSON : gère les accents dans le titre, contrairement aux en-têtes HTTP.
        requests.post("https://ntfy.sh/", json={
            "topic": sujet,
            "title": titre,
            "message": message,
            "tags": list(tags),
            "priority": priorite,
        }, timeout=10)
    except requests.RequestException:
        pass
