"""Mémoire locale du bot : ce qu'il a réservé, et ce que tu as annulé."""

import json
import os
from datetime import datetime, timedelta

from .heitzfit import PARIS

RESERVEE = "reservee"
ANNULEE = "annulee_par_toi"  # le bot ne la réservera plus jamais
COMPLETE = "complete"  # déjà signalée comme complète ; le bot guette encore un désistement
SUPPRIMEE = "supprimee_par_la_piscine"  # la piscine a retiré la séance (souvent pour la recréer)


class Etat:
    def __init__(self, chemin):
        self.chemin = chemin
        self.seances = {}
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                self.seances = json.load(f)
        # Réglages faits depuis Telegram, rappels déjà envoyés, etc.
        self.extra = self.seances.pop("_extra", {})

    def statut(self, id_seance):
        return self.seances.get(str(id_seance), {}).get("statut")

    def marquer(self, seance, statut):
        self.seances[str(seance["id"])] = {
            "activite": seance["activity"],
            "debut": seance["debut"].isoformat(),
            "statut": statut,
            "maj": datetime.now(PARIS).isoformat(timespec="seconds"),
        }
        self.sauver()

    def synchroniser(self, ids_reservees_sur_compte, existantes=None, horizon=None):
        """Une séance réservée par le bot qui n'est plus sur le compte a été annulée par toi...
        sauf si la séance n'existe plus au planning (`existantes`, connu jusqu'à `horizon`) :
        c'est alors la piscine qui l'a supprimée, et ce n'est pas une annulation de ta part.
        Renvoie (annulées par toi, supprimées par la piscine)."""
        maintenant = datetime.now(PARIS)
        annulees, supprimees = [], []
        for id_seance, s in self.seances.items():
            # Délai de grâce : une réservation toute fraîche peut ne pas encore apparaître.
            recente = maintenant - datetime.fromisoformat(s["maj"]) < timedelta(minutes=5)
            if (s["statut"] == RESERVEE and not recente and int(id_seance) not in ids_reservees_sur_compte
                    and datetime.fromisoformat(s["debut"]) > maintenant):
                debut = datetime.fromisoformat(s["debut"])
                retiree = existantes is not None and debut.date() < horizon and int(id_seance) not in existantes
                s["statut"] = SUPPRIMEE if retiree else ANNULEE
                s["maj"] = maintenant.isoformat(timespec="seconds")
                (supprimees if retiree else annulees).append(s)
        if annulees or supprimees:
            self.sauver()
        return annulees, supprimees

    def sauver(self):
        tmp = self.chemin + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({**self.seances, "_extra": self.extra}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.chemin)
