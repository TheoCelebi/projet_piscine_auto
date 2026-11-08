"""Notifications sur téléphone via ntfy.sh (appli ntfy, abonnement au sujet NTFY_TOPIC)."""

import os
from datetime import datetime

import requests

from .heitzfit import PARIS

# La nuit, le bot réserve quand même, mais la notification n'arrive qu'au matin.
NUIT_DEBUT, NUIT_FIN = 0, 7  # de minuit à 7h (heure de Paris)
REVEIL = (8, 15)             # notifications de la nuit livrées à 8h15


def heure_de_livraison(maintenant=None):
    """Instant de livraison différée si on est la nuit, sinon None (livraison immédiate)."""
    maintenant = maintenant or datetime.now(PARIS)
    if NUIT_DEBUT <= maintenant.hour < NUIT_FIN:
        return maintenant.replace(hour=REVEIL[0], minute=REVEIL[1], second=0, microsecond=0)
    return None


def notifier(titre, message, tags=(), priorite=3):
    """N'échoue jamais : une notification ratée ne doit pas faire échouer une réservation."""
    sujet = os.getenv("NTFY_TOPIC", "").strip()
    if not sujet:
        return
    # Publication JSON : gère les accents dans le titre, contrairement aux en-têtes HTTP.
    corps = {"topic": sujet, "title": titre, "message": message, "tags": list(tags), "priority": priorite}
    livraison = heure_de_livraison()
    if livraison:
        # ntfy.sh garde le message et ne l'envoie au téléphone qu'à l'heure demandée.
        corps["delay"] = str(int(livraison.timestamp()))
        corps["message"] += f"\n(événement de {datetime.now(PARIS):%H:%M}, notification retardée pour la nuit)"
    try:
        requests.post("https://ntfy.sh/", json=corps, timeout=10)
    except requests.RequestException:
        pass
