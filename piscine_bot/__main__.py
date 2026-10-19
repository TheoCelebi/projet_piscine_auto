"""Réserve les séances listées dans config.yaml.

    python -m piscine_bot                  # simulation : affiche ce qui serait réservé
    python -m piscine_bot --reserver       # réserve pour de vrai ce qui est déjà ouvert
    python -m piscine_bot --reserver --attendre   # attend l'ouverture (48h avant) puis réserve
    python -m piscine_bot --planning 2026-10-21   # affiche le planning d'un jour
"""

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta

import yaml
from dotenv import load_dotenv

from .heitzfit import PARIS, Heitzfit, HeitzfitError

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FENETRE_JOURS = 3  # les réservations ouvrent 48h avant : aujourd'hui + 2 jours suffisent
AVANCE_CONNEXION_S = 60  # connexion 1 min avant l'ouverture
RETENTE_MAX_S = 180  # on réessaie pendant 3 min si HeitzFit n'a pas encore ouvert
# Codes HeitzFit renvoyés quand la séance est hors de la période de réservation.
PAS_ENCORE_OUVERT = {"PERIOD_EXCEEDED", "PERIOD_NOT_STARTED"}


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
    parser.add_argument("--attendre", action="store_true",
                        help="si la réservation n'est pas encore ouverte, attendre l'ouverture puis réserver")
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

    delai = timedelta(hours=config.get("ouverture_heures_avant", 48))
    cibles.sort(key=lambda s: s["debut"])

    if args.reserver:
        load_dotenv()
        email, mdp = os.getenv("HEITZFIT_EMAIL"), os.getenv("HEITZFIT_PASSWORD")
        if not email or not mdp:
            print("HEITZFIT_EMAIL / HEITZFIT_PASSWORD manquants dans .env", file=sys.stderr)
            return 2

    echecs = 0
    for s in cibles:
        ouverture = s["debut"] - delai
        attente = (ouverture - datetime.now(PARIS)).total_seconds()
        if not args.reserver:
            info = f"ouvre le {ouverture:%d/%m à %H:%M}" if attente > 0 else "ouverte"
            print(f"[simulation] réserverait : {afficher(s)}  [{info}]")
            continue
        if attente > 0:
            if not args.attendre:
                print(f"PAS ENCORE : {afficher(s)} -> ouvre le {ouverture:%d/%m à %H:%M} (utilise --attendre)")
                continue
            print(f"Attente de l'ouverture ({ouverture:%d/%m %H:%M:%S}) pour : {afficher(s)}", flush=True)
            # On se connecte juste avant l'ouverture pour avoir une session fraîche.
            time.sleep(max(0, attente - AVANCE_CONNEXION_S))
        try:
            hf.connexion(email, mdp)
            if reserver_des_ouverture(hf, s, ouverture):
                print(f"RÉSERVÉ : {afficher(s)}")
            else:
                echecs += 1
                print(f"ÉCHEC   : {afficher(s)} -> toujours fermé après {RETENTE_MAX_S}s")
        except HeitzfitError as e:
            echecs += 1
            print(f"ÉCHEC   : {afficher(s)} -> {e.code or e}")
    return 1 if echecs else 0


def reserver_des_ouverture(hf, seance, ouverture):
    """Réserve, en réessayant chaque seconde tant que HeitzFit dit que ce n'est pas encore ouvert."""
    while datetime.now(PARIS) < ouverture:
        time.sleep(0.2)
    fin = time.monotonic() + RETENTE_MAX_S
    while True:
        try:
            hf.reserver(seance["id"])
            return True
        except HeitzfitError as e:
            if e.code not in PAS_ENCORE_OUVERT or time.monotonic() > fin:
                if e.code in PAS_ENCORE_OUVERT:
                    return False
                raise
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
