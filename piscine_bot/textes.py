"""Textes lisibles par tout le monde (pas de jargon) et liens « ajouter à l'agenda »."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
LIEU = "Centre aquatique de Bois-Colombes"
LIEN_HEITZFIT = "https://app.heitzfit.com/#/planning/browse"


def heure(dt):
    return f"{dt.hour}h{dt.minute:02d}"


def date_longue(dt):
    """« jeudi 20 novembre »"""
    return f"{JOURS[dt.weekday()]} {dt.day} {MOIS[dt.month - 1]}"


def quand(dt):
    """« jeudi 20 novembre à 9h15 »"""
    return f"{date_longue(dt)} à {heure(dt)}"


def nom(seance):
    """« AQUABIKE » -> « Aquabike »"""
    return str(seance["activity"]).strip().capitalize()


def salle(seance):
    """« 03-BALNEOTHÉRAPIE » -> « bassin balnéo »"""
    brut = str(seance.get("room", ""))
    if "BALNEO" in brut.upper().replace("É", "E"):
        return "bassin balnéo"
    return brut.split("-", 1)[-1].strip().capitalize()


def ligne(seance):
    """« jeudi 20 novembre à 9h15 : Aquabike (bassin balnéo) »"""
    return f"{quand(seance['debut'])} : {nom(seance)} ({salle(seance)})"


def fin(seance):
    if seance.get("end"):
        return datetime.fromisoformat(seance["end"].replace("Z", "+00:00"))
    return seance["debut"] + timedelta(minutes=seance.get("duration") or 45)


def _utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def lien_agenda(seance):
    """Lien Google Agenda pré-rempli (s'ouvre aussi dans un navigateur)."""
    return "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE",
        "text": f"Piscine : {nom(seance)}",
        "dates": f"{_utc(seance['debut'])}/{_utc(fin(seance))}",
        "location": LIEU,
        "details": f"{nom(seance)}, {salle(seance)}. Réservé automatiquement.",
    })


def fichier_agenda(seance):
    """Fichier .ics : un appui dessus ajoute la séance à l'agenda du téléphone (iPhone comme Android)."""
    lignes = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//projet_piscine_auto//FR", "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{seance['id']}@projet-piscine-auto",
        f"DTSTAMP:{_utc(datetime.now(timezone.utc))}",
        f"DTSTART:{_utc(seance['debut'])}",
        f"DTEND:{_utc(fin(seance))}",
        f"SUMMARY:Piscine : {nom(seance)}",
        f"LOCATION:{LIEU}",
        f"DESCRIPTION:{nom(seance)}\\, {salle(seance)}. Réservé automatiquement.",
        "BEGIN:VALARM", "TRIGGER:-PT1H", "ACTION:DISPLAY", "DESCRIPTION:Piscine dans 1 heure", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return ("\r\n".join(lignes) + "\r\n").encode("utf-8")
