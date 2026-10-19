"""Menu interactif pour gérer les règles du bot.

    python -m piscine_bot.gerer
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta

import yaml
from dotenv import load_dotenv

from .__main__ import JOURS, afficher, correspond
from .heitzfit import PARIS, Heitzfit, HeitzfitError

CONFIG = "config.yaml"
DEPOT = "TheoCelebi/projet_piscine_auto"
ENTETE = "# Géré avec : python -m piscine_bot.gerer  (voir config.example.yaml pour le format)\n"
APERCU_JOURS = 21


def charger():
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def sauver(config):
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(ENTETE)
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def decrire_regle(r):
    eau = r.get("salle", "").upper() == "BALNEO"
    morceaux = []
    if "activite" in r:
        morceaux.append(r["activite"])
    else:
        morceaux.append("toutes les séances dans l'eau" if eau else "toutes les activités")
    if "salle" in r and not (eau and "activite" not in r):
        morceaux.append("dans l'eau" if eau else f"salle « {r['salle']} »")
    morceaux.append(", ".join(r["jours"]) if "jours" in r else "tous les jours")
    if "heure" in r:
        morceaux.append(f"à {r['heure']}")
    if "apres" in r:
        morceaux.append(f"après {r['apres']}")
    if "avant" in r:
        morceaux.append(f"avant {r['avant']}")
    return " · ".join(morceaux)


def demander(question, defaut=""):
    rep = input(f"{question}{f' [{defaut}]' if defaut else ''} : ").strip()
    return rep or defaut


def choisir(titre, options, multiple=False, aucun=None):
    """Affiche une liste numérotée. Renvoie un élément (ou une liste si multiple)."""
    print(f"\n{titre}")
    if aucun:
        print(f"   0. {aucun}")
    for i, o in enumerate(options, 1):
        print(f"  {i:>2}. {o}")
    while True:
        rep = input("Choix" + (" (ex. 1,3,5)" if multiple else "") + " : ").strip()
        if aucun and rep in ("", "0"):
            return [] if multiple else None
        try:
            nums = [int(x) for x in rep.replace(" ", "").split(",") if x]
            if nums and all(1 <= n <= len(options) for n in nums):
                return [options[n - 1] for n in nums] if multiple else options[nums[0] - 1]
        except ValueError:
            pass
        print("  Choix invalide.")


def planning(config):
    seances = Heitzfit(config["centre"]).planning(datetime.now(PARIS).date(), APERCU_JOURS)
    return [s for s in seances if not s["deleted"]]


# --- Actions du menu ---------------------------------------------------------

def voir_regles(config):
    regles = config.get("regles", [])
    print("\nRègles actives (le bot réserve une séance si elle correspond à au moins une) :")
    if not regles:
        print("  (aucune règle : le bot ne réservera rien)")
    for i, r in enumerate(regles, 1):
        print(f"  {i}. {decrire_regle(r)}")


def ajouter_regle(config):
    print("\nChargement du planning pour proposer les vrais noms de séances...")
    seances = planning(config)
    eau = sorted({s["activity"] for s in seances if "BALNEO" in s["room"].upper()})
    autres = sorted({s["activity"] for s in seances} - set(eau))
    options = ["Toutes les séances dans l'eau"] + [f"{a} (eau)" for a in eau] + autres
    choix = choisir("Quelle séance ?", options)

    regle = {}
    if choix == options[0]:
        regle["salle"] = "BALNEO"
    else:
        regle["activite"] = choix.removesuffix(" (eau)")

    jours = choisir("Quels jours ? (0 = tous les jours)", JOURS, multiple=True, aucun="Tous les jours")
    if jours:
        regle["jours"] = jours

    # On propose les horaires qui existent réellement pour ce choix.
    candidates = [s for s in seances if correspond(s, regle)]
    horaires = sorted({s["debut"].strftime("%H:%M") for s in candidates})
    if horaires:
        heure = choisir("Quelle heure de début ? (0 = toutes)", horaires, aucun="Toutes les heures")
        if heure:
            regle["heure"] = heure
    else:
        print("  (aucune séance de ce type pour l'instant dans le planning : toutes les heures)")
        heure = demander("Heure exacte HH:MM, ou Entrée pour toutes")
        if heure:
            regle["heure"] = heure

    print(f"\nNouvelle règle : {decrire_regle(regle)}")
    if demander("Confirmer ? (o/n)", "o").lower().startswith("o"):
        config.setdefault("regles", []).append(regle)
        sauver(config)
        print("Règle ajoutée.")
        return True
    return False


def supprimer_regle(config):
    regles = config.get("regles", [])
    if not regles:
        print("\nAucune règle à supprimer.")
        return False
    r = choisir("Quelle règle supprimer ?", [decrire_regle(r) for r in regles], aucun="Annuler")
    if r is None:
        return False
    idx = [decrire_regle(x) for x in regles].index(r)
    del regles[idx]
    sauver(config)
    print("Règle supprimée.")
    return True


def apercu(config):
    print(f"\nSéances du planning publié ({APERCU_JOURS} prochains jours) que le bot réservera :")
    maintenant = datetime.now(PARIS)
    delai = timedelta(hours=config.get("ouverture_heures_avant", 48))
    trouve = False
    for s in planning(config):
        if s["debut"] > maintenant and any(correspond(s, r) for r in config.get("regles", [])):
            ouverture = s["debut"] - delai
            quand = "déjà ouverte" if ouverture <= maintenant else \
                f"réservée le {JOURS[ouverture.weekday()]} {ouverture:%d/%m à %H:%M}"
            print(f"  {afficher(s)}  -> {quand}")
            trouve = True
    if not trouve:
        print("  (aucune pour l'instant ; la piscine publie ses séances au fur et à mesure)")


def mes_reservations(config):
    load_dotenv()
    hf = Heitzfit(config["centre"])
    try:
        hf.connexion(os.getenv("HEITZFIT_EMAIL"), os.getenv("HEITZFIT_PASSWORD"))
        ids = hf.mes_reservations()
    except HeitzfitError as e:
        print(f"\nConnexion impossible : {e.code or e}")
        return
    print("\nTes réservations actuelles sur HeitzFit :")
    seances = {s["id"]: s for s in planning(config)}
    if not ids:
        print("  (aucune)")
    for i in sorted(ids, key=lambda i: seances[i]["debut"] if i in seances else datetime.max.replace(tzinfo=PARIS)):
        print(f"  {afficher(seances[i])}" if i in seances else f"  séance id {i} (hors des {APERCU_JOURS} prochains jours)")


def publier():
    print("\nEnvoi de la configuration sur GitHub (secret HEITZFIT_CONFIG)...")
    with open(CONFIG, "rb") as f:
        res = subprocess.run(["gh", "secret", "set", "HEITZFIT_CONFIG", "-R", DEPOT], stdin=f)
    print("Envoyée : le bot l'utilisera dès son prochain passage." if res.returncode == 0
          else "Échec de l'envoi (gh est-il connecté ? essaie : gh auth status).")
    return res.returncode == 0


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config = charger()
    non_publie = False
    actions = [
        "Voir les règles",
        "Ajouter une règle",
        "Supprimer une règle",
        "Aperçu : séances qui seront réservées",
        "Mes réservations actuelles (HeitzFit)",
        "Envoyer la config sur GitHub",
    ]
    print("=== Bot piscine : gestion des règles ===")
    voir_regles(config)
    while True:
        if non_publie:
            print("\n(!) Modifications pas encore envoyées sur GitHub.")
        choix = choisir("Que veux-tu faire ?", actions, aucun="Quitter")
        try:
            if choix is None:
                if non_publie and demander("Envoyer les modifications sur GitHub avant de quitter ? (o/n)",
                                           "o").lower().startswith("o"):
                    publier()
                return 0
            if choix == actions[0]:
                voir_regles(config)
            elif choix == actions[1]:
                non_publie |= ajouter_regle(config)
            elif choix == actions[2]:
                non_publie |= supprimer_regle(config)
            elif choix == actions[3]:
                apercu(config)
            elif choix == actions[4]:
                mes_reservations(config)
            elif choix == actions[5]:
                if publier():
                    non_publie = False
        except (HeitzfitError, OSError) as e:
            print(f"\nErreur : {e}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
