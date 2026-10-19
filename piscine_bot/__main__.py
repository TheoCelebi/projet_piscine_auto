"""Réserve automatiquement les séances qui correspondent aux règles de config.yaml.

    python -m piscine_bot                  # simulation : affiche ce qui serait réservé
    python -m piscine_bot --reserver       # un passage : réserve ce qui est ouvert
    python -m piscine_bot --surveiller     # tourne en continu et réserve dès l'ouverture
    python -m piscine_bot --planning 2026-10-21   # affiche le planning d'un jour
"""

import argparse
import os
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta

import yaml
from dotenv import load_dotenv

from .etat import ANNULEE, RESERVEE, Etat
from .heitzfit import PARIS, Heitzfit, HeitzfitError

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FENETRE_JOURS = 3  # les réservations ouvrent 48h avant : aujourd'hui + 2 jours suffisent
AVANCE_CONNEXION_S = 60  # connexion 1 min avant l'ouverture
RETENTE_MAX_S = 180  # on réessaie pendant 3 min si HeitzFit n'a pas encore ouvert
# Codes HeitzFit renvoyés quand la séance est hors de la période de réservation.
PAS_ENCORE_OUVERT = {"PERIOD_EXCEEDED", "PERIOD_NOT_STARTED"}


def log(msg):
    print(f"[{datetime.now(PARIS):%d/%m %H:%M:%S}] {msg}", flush=True)


def normaliser(texte):
    """Majuscules sans accents, pour comparer 'Balnéo' et 'BALNEOTHÉRAPIE'."""
    sans_accents = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return sans_accents.upper().strip()


def correspond(seance, regle):
    """Tous les critères présents dans la règle doivent être vrais."""
    if "activite" in regle and normaliser(regle["activite"]) not in normaliser(seance["activity"]):
        return False
    if "salle" in regle and normaliser(regle["salle"]) not in normaliser(seance["room"]):
        return False
    if "jours" in regle and JOURS[seance["debut"].weekday()] not in [j.lower() for j in regle["jours"]]:
        return False
    heure = seance["debut"].strftime("%H:%M")
    if "apres" in regle and heure < regle["apres"]:
        return False
    if "avant" in regle and heure > regle["avant"]:
        return False
    return True


def afficher(s):
    return (f"{JOURS[s['debut'].weekday()][:3]} {s['debut']:%d/%m %H:%M}  {s['activity']:<12} "
            f"{s['room']:<20} {s['placesTaken']}/{s['placesMax']}  (id {s['id']})")


class Bot:
    def __init__(self, config, etat, reel):
        self.config = config
        self.etat = etat
        self.reel = reel
        self.hf = Heitzfit(config["centre"])
        self.delai = timedelta(hours=config.get("ouverture_heures_avant", 48))
        self.exclues = {int(i) for i in config.get("exclure_ids", [])}
        self.connecte_a = None
        self.sur_compte = set()  # séances déjà réservées sur le compte (par le bot ou par toi)

    def connexion(self):
        load_dotenv()
        email, mdp = os.getenv("HEITZFIT_EMAIL"), os.getenv("HEITZFIT_PASSWORD")
        if not email or not mdp:
            raise SystemExit("HEITZFIT_EMAIL / HEITZFIT_PASSWORD manquants dans .env")
        self.hf.connexion(email, mdp)
        self.connecte_a = time.monotonic()

    def cibles(self):
        maintenant = datetime.now(PARIS)
        seances = self.hf.planning(maintenant.date(), FENETRE_JOURS)
        return [s for s in seances
                if s["debut"] > maintenant and not s["deleted"]
                and s["id"] not in self.exclues
                and any(correspond(s, r) for r in self.config["regles"])]

    def synchroniser(self):
        """Détecte les séances réservées par le bot que tu as annulées depuis l'appli."""
        self.sur_compte = self.hf.mes_reservations()
        if not self.config.get("detecter_annulations", False):
            return
        for s in self.etat.synchroniser(self.sur_compte):
            log(f"ANNULÉE PAR TOI (ne sera plus réservée) : {s['activite']} {s['debut'][:16]}")

    def passage(self):
        """Réserve tout ce qui est ouvert. Renvoie les séances qui ouvriront plus tard."""
        a_venir = []
        for s in self.cibles():
            statut = self.etat.statut(s["id"])
            if statut in (RESERVEE, ANNULEE) or s["id"] in self.sur_compte:
                continue
            ouverture = s["debut"] - self.delai
            if ouverture > datetime.now(PARIS):
                a_venir.append((ouverture, s))
                continue
            if s["placesTaken"] >= s["placesMax"]:
                # Complète : on retentera au prochain passage, une place peut se libérer.
                if not self.reel:
                    log(f"[simulation] complète, surveillée : {afficher(s)}")
                continue
            if not self.reel:
                log(f"[simulation] réserverait : {afficher(s)}")
                continue
            self.tenter(s, ouverture)
        if not self.reel:
            for ouverture, s in sorted(a_venir, key=lambda x: x[0]):
                log(f"[simulation] réserverait le {ouverture:%d/%m à %H:%M} : {afficher(s)}")
        return a_venir

    def tenter(self, s, ouverture):
        try:
            if self.reserver_des_ouverture(s, ouverture):
                self.etat.marquer(s, RESERVEE)
                log(f"RÉSERVÉ : {afficher(s)}")
            else:
                log(f"ÉCHEC   : {afficher(s)} -> toujours fermé après {RETENTE_MAX_S}s")
        except HeitzfitError as e:
            log(f"ÉCHEC   : {afficher(s)} -> {e.code or e}")

    def reserver_des_ouverture(self, seance, ouverture):
        """Réserve, en réessayant chaque seconde tant que HeitzFit dit que ce n'est pas encore ouvert."""
        while datetime.now(PARIS) < ouverture:
            time.sleep(0.2)
        fin = time.monotonic() + RETENTE_MAX_S
        while True:
            try:
                self.hf.reserver(seance["id"])
                return True
            except HeitzfitError as e:
                if e.code not in PAS_ENCORE_OUVERT:
                    raise
                if time.monotonic() > fin:
                    return False
                time.sleep(1)

    def surveiller(self):
        intervalle = self.config.get("intervalle_minutes", 10) * 60
        log(f"Surveillance démarrée (vérification toutes les {intervalle // 60} min).")
        while True:
            try:
                # Session neuve toutes les 30 min pour ne jamais tomber sur un jeton expiré.
                if self.connecte_a is None or time.monotonic() - self.connecte_a > 1800:
                    self.connexion()
                self.synchroniser()
                a_venir = self.passage()
                prochaine = min((o for o, _ in a_venir), default=None)
                attente = intervalle
                if prochaine:
                    avant_ouverture = (prochaine - datetime.now(PARIS)).total_seconds()
                    if avant_ouverture <= intervalle:
                        # Une ouverture tombe avant le prochain passage : on se cale dessus.
                        log(f"Prochaine ouverture à {prochaine:%H:%M:%S}, on se tient prêt.")
                        time.sleep(max(0, avant_ouverture - AVANCE_CONNEXION_S))
                        self.connexion()
                        for o, s in a_venir:
                            if o == prochaine:
                                self.tenter(s, o)
                        continue
            except (HeitzfitError, OSError) as e:
                log(f"Erreur (on réessaiera) : {e}")
                self.connecte_a = None
                attente = 60
            time.sleep(attente)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--etat", default="etat.json", help="fichier mémoire du bot")
    parser.add_argument("--reserver", action="store_true", help="un passage, réservations réelles")
    parser.add_argument("--surveiller", action="store_true", help="tourne en continu, réservations réelles")
    parser.add_argument("--planning", metavar="AAAA-MM-JJ", help="afficher le planning d'un jour et quitter")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if args.planning:
        for s in Heitzfit(config["centre"]).planning(date.fromisoformat(args.planning)):
            print(afficher(s))
        return 0

    bot = Bot(config, Etat(args.etat), reel=args.reserver or args.surveiller)
    if args.surveiller:
        bot.surveiller()
    if args.reserver:
        bot.connexion()
        bot.synchroniser()
    bot.passage()
    return 0


if __name__ == "__main__":
    sys.exit(main())
