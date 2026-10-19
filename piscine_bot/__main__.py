"""Réserve les séances listées dans config.yaml.

    python -m piscine_bot                  # simulation : affiche ce qui serait réservé
    python -m piscine_bot --reserver       # réserve pour de vrai
    python -m piscine_bot --planning 2026-10-21   # affiche le planning d'un jour
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta

import yaml
from dotenv import load_dotenv

from .heitzfit import PARIS, Heitzfit, HeitzfitError

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FENETRE_JOURS = 3  # les réservations ouvrent 48h avant : aujourd'hui + 2 jours suffisent


def charger_config(chemin):
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


def correspond(seance, voulue):
    if seance["activity"].strip().upper() != voulue["activite"].strip().upper():
        return False
    if seance["debut"].strftime("%H:%M") != voulue["heure"]:
        return False
    if "date" in voulue:
        return seance["debut"].date() == date.fromisoformat(str(voulue["date"]))
    if "jour" in voulue:
        return JOURS[seance["debut"].weekday()] == voulue["jour"].strip().lower()
    return True


def afficher(s):
    return (f"{JOURS[s['debut'].weekday()][:3]} {s['debut']:%d/%m %H:%M}  {s['activity']:<12} {s['room']:<20} "
            f"{s['placesTaken']}/{s['placesMax']}  (id {s['id']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--reserver", action="store_true", help="réserver pour de vrai (sinon simulation)")
    parser.add_argument("--planning", metavar="AAAA-MM-JJ", help="afficher le planning d'un jour et quitter")
    args = parser.parse_args()

    config = charger_config(args.config)
    hf = Heitzfit(config["centre"])

    if args.planning:
        for s in hf.planning(date.fromisoformat(args.planning)):
            print(afficher(s))
        return 0

    maintenant = datetime.now(PARIS)
    seances = [s for s in hf.planning(maintenant.date(), FENETRE_JOURS)
               if s["debut"] > maintenant and not s["deleted"]]
    cibles = [s for s in seances if any(correspond(s, v) for v in config["seances"])]

    if not cibles:
        print("Aucune séance voulue dans le planning des prochains jours.")
        return 0

    if args.reserver:
        load_dotenv()
        email, mdp = os.getenv("HEITZFIT_EMAIL"), os.getenv("HEITZFIT_PASSWORD")
        if not email or not mdp:
            print("HEITZFIT_EMAIL / HEITZFIT_PASSWORD manquants dans .env", file=sys.stderr)
            return 2
        hf.connexion(email, mdp)
        print("Connecté.")

    echecs = 0
    for s in cibles:
        if not args.reserver:
            print(f"[simulation] réserverait : {afficher(s)}")
            continue
        try:
            hf.reserver(s["id"])
            print(f"RÉSERVÉ : {afficher(s)}")
        except HeitzfitError as e:
            echecs += 1
            print(f"ÉCHEC   : {afficher(s)} -> {e.code or e}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
