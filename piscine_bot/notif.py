"""Notifications.

Deux publics :
- famille() : la personne qui va à la piscine. Messages simples, avec boutons « Ouvrir HeitzFit »
  et « Ajouter à l'agenda ». Envoyés sur son sujet ntfy (NTFY_TOPIC_MERE), par email (NTFY_EMAIL_MERE)
  et/ou sur Telegram (TELEGRAM_TOKEN + TELEGRAM_CHAT_ID), selon ce qui est configuré.
  Une copie part aussi sur le sujet de l'administrateur.
- admin() : l'administrateur (NTFY_TOPIC) seulement, pour le technique (erreurs, séances complètes...).
"""

import os
from datetime import datetime

import requests

from .heitzfit import PARIS
from .telegram import Telegram
from .textes import LIEN_HEITZFIT, fichier_agenda, lien_agenda

# La nuit, le bot réserve quand même, mais la notification n'arrive qu'au matin.
NUIT_DEBUT, NUIT_FIN = 0, 7  # de minuit à 7h (heure de Paris)
REVEIL = (8, 15)             # notifications de la nuit livrées à 8h15


def heure_de_livraison(maintenant=None):
    """Instant de livraison différée si on est la nuit, sinon None (livraison immédiate)."""
    maintenant = maintenant or datetime.now(PARIS)
    if NUIT_DEBUT <= maintenant.hour < NUIT_FIN:
        return maintenant.replace(hour=REVEIL[0], minute=REVEIL[1], second=0, microsecond=0)
    return None


def _env(nom):
    return os.getenv(nom, "").strip()


def _ntfy(sujet, titre, message, tags=(), priorite=3, actions=(), email=None):
    """N'échoue jamais : une notification ratée ne doit pas faire échouer une réservation."""
    if not sujet:
        return
    # Publication JSON : gère les accents dans le titre, contrairement aux en-têtes HTTP.
    corps = {"topic": sujet, "title": titre, "message": message, "tags": list(tags), "priority": priorite}
    if actions:
        corps["actions"] = list(actions)
    if email:
        corps["email"] = email
    livraison = heure_de_livraison()
    if livraison:
        # ntfy.sh garde le message et ne l'envoie qu'à l'heure demandée.
        corps["delay"] = str(int(livraison.timestamp()))
        corps["message"] += f"\n(message de {datetime.now(PARIS):%H:%M}, gardé pour ne pas te réveiller)"
    try:
        requests.post("https://ntfy.sh/", json=corps, timeout=10)
    except requests.RequestException:
        pass


def admin(titre, message, tags=(), priorite=3):
    _ntfy(_env("NTFY_TOPIC"), titre, message, tags, priorite)


def famille(titre, message, tags=(), seance=None, priorite=3, copie_admin=True):
    actions = [{"action": "view", "label": "Ouvrir HeitzFit", "url": LIEN_HEITZFIT}]
    if seance:
        actions.append({"action": "view", "label": "Ajouter à l'agenda", "url": lien_agenda(seance)})

    sujet, email = _env("NTFY_TOPIC_MERE"), _env("NTFY_EMAIL_MERE") or None
    if sujet:
        _ntfy(sujet, titre, message, tags, priorite, actions, email)
    if copie_admin or not sujet:
        # Sans sujet dédié, l'email part avec le message de l'administrateur.
        _ntfy(_env("NTFY_TOPIC"), titre, message, tags, priorite, actions, None if sujet else email)

    tg = Telegram()
    if tg.actif:
        nuit = heure_de_livraison() is not None
        boutons = [[("Ouvrir HeitzFit", LIEN_HEITZFIT)]]
        if seance:
            boutons[0].append(("Google Agenda", lien_agenda(seance)))
        tg.envoyer(f"{titre}\n\n{message}", boutons=boutons, silencieux=nuit)
        if seance:
            tg.envoyer_fichier("seance-piscine.ics", fichier_agenda(seance),
                               "Appuie sur ce fichier pour ajouter la séance à ton agenda.", silencieux=True)
