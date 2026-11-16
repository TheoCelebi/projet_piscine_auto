"""Tout ce qui sert à la personne qui va à la piscine : pauses, rappels, récapitulatif, bot Telegram.

Les pauses et les cours désactivés viennent de deux sources :
- config.yaml (`pauses:`), géré par l'administrateur avec le menu ;
- Telegram, réglés par l'utilisatrice elle-même et gardés dans la mémoire du bot (etat.json).
"""

import re
import unicodedata
from datetime import date, datetime, timedelta

from .heitzfit import PARIS
from .notif import famille
from .telegram import Telegram
from .textes import date_longue, heure, ligne, nom

SOIR = (19, 22)  # rappel de la veille et récapitulatif du dimanche entre 19h et 22h
APERCU_JOURS = 14


def normaliser(texte):
    sans_accents = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return sans_accents.upper().strip()


# --- Pauses -----------------------------------------------------------------

def pauses(config, etat):
    """Toutes les pauses (config + Telegram), en couples de dates."""
    toutes = list(config.get("pauses") or []) + list(etat.extra.get("pauses", []))
    return [(date.fromisoformat(str(p["du"])), date.fromisoformat(str(p["au"]))) for p in toutes]


def en_pause(jour, config, etat):
    return any(du <= jour <= au for du, au in pauses(config, etat))


def activite_exclue(seance, etat):
    return normaliser(seance["activity"]) in etat.extra.get("activites_exclues", [])


def lire_dates(texte, aujourdhui):
    """« pause 20/12 au 3/1 » -> (2026-12-20, 2027-01-03). Année devinée : la prochaine occurrence."""
    trouve = re.findall(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", texte)
    if len(trouve) != 2:
        return None
    dates = []
    for j, m, a in trouve:
        try:
            if a:
                d = date(int(a) + (2000 if len(a) == 2 else 0), int(m), int(j))
            else:
                d = date(aujourdhui.year, int(m), int(j))
                if d < aujourdhui - timedelta(days=1):
                    d = d.replace(year=d.year + 1)
        except ValueError:
            return None
        dates.append(d)
    du, au = dates
    if au < du:
        au = au.replace(year=au.year + 1)
    return du, au


# --- Contenu des messages ----------------------------------------------------

def mes_seances(bot):
    """Séances réservées sur le compte (par le bot ou à la main), avec leur détail."""
    seances = bot.hf.planning(datetime.now(PARIS).date(), APERCU_JOURS)
    return [s for s in seances if s["id"] in bot.sur_compte and s["debut"] > datetime.now(PARIS)]


def texte_mes_seances(bot):
    liste = mes_seances(bot)
    if not liste:
        return ("Aucune séance réservée pour l'instant.\n"
                "Le bot réserve chaque cours 48h à l'avance, dès l'ouverture des inscriptions.")
    return "Tes séances réservées :\n\n" + "\n".join(f"✅ {ligne(s)}" for s in liste) + \
        "\n\nPour en annuler une : appli HeitzFit, « Mes réservations ». Le bot ne la reprendra pas."


def texte_semaine(bot, debut):
    """Ce qui est réservé et ce que le bot va réserver du jour `debut` aux 6 jours suivants."""
    maintenant = datetime.now(PARIS)
    seances = [s for s in bot.hf.planning(debut, 7) if s["debut"] > maintenant and not s["deleted"]]
    lignes = []
    for s in seances:
        if s["id"] in bot.sur_compte:
            lignes.append(f"✅ {ligne(s)}")
        elif bot.voulue(s, ignorer_pause=True):
            if en_pause(s["debut"].date(), bot.config, bot.etat):
                lignes.append(f"🏖 {ligne(s)} : en pause")
                continue
            ouverture = s["debut"] - bot.delai
            if ouverture > maintenant:
                lignes.append(f"🕒 {ligne(s)} : réservation auto {date_longue(ouverture)} à {heure(ouverture)}")
            else:
                lignes.append(f"⏳ {ligne(s)} : complet, le bot guette une place")
    if not lignes:
        return "Rien de prévu cette semaine pour l'instant."
    return ("Ta semaine piscine :\n\n" + "\n".join(lignes) +
            "\n\n✅ réservé · 🕒 sera réservé automatiquement · ⏳ complet pour l'instant")


AIDE = (
    "Bonjour 👋 Je réserve tes séances de piscine automatiquement.\n\n"
    "📅 Mes séances : ce qui est réservé\n"
    "🗓 Ma semaine : ce qui est réservé et ce que je vais réserver\n"
    "🏖 Pause : arrêter les réservations pendant tes vacances\n"
    "🏊 Mes cours : choisir les cours que je réserve\n\n"
    "Pour annuler une séance, fais-le dans l'appli HeitzFit comme d'habitude : je ne la reprendrai pas.\n\n"
    "Je lis tes messages une fois par heure : ma réponse peut prendre un peu de temps."
)


# --- Rappels automatiques --------------------------------------------------

def rappels(bot):
    """Rappel la veille au soir et récapitulatif le dimanche soir (une seule fois chacun)."""
    maintenant = datetime.now(PARIS)
    if not SOIR[0] <= maintenant.hour < SOIR[1]:
        return
    aujourdhui = maintenant.date().isoformat()
    demain = maintenant.date() + timedelta(days=1)

    if bot.etat.extra.get("rappel") != aujourdhui:
        bot.etat.extra["rappel"] = aujourdhui
        bot.etat.sauver()
        liste = [s for s in mes_seances(bot) if s["debut"].date() == demain]
        if liste:
            detail = "\n".join(f"• {heure(s['debut'])} : {nom(s)}" for s in liste)
            famille("Piscine demain 🏊", f"{detail}\n\nN'oublie pas ton maillot 🙂", tags=["bell"],
                    seance=liste[0], copie_admin=False)

    if maintenant.weekday() == 6 and bot.etat.extra.get("recap") != aujourdhui:
        bot.etat.extra["recap"] = aujourdhui
        bot.etat.sauver()
        famille("Ta semaine piscine", texte_semaine(bot, demain).removeprefix("Ta semaine piscine :\n\n"),
                tags=["calendar"], copie_admin=False)


# --- Bot Telegram ------------------------------------------------------------

def cours_disponibles(bot):
    """Noms des cours que les règles visent dans le planning publié."""
    seances = bot.hf.planning(datetime.now(PARIS).date(), 21)
    return sorted({normaliser(s["activity"]) for s in seances if bot.voulue(s, ignorer_pause=True,
                                                                            ignorer_exclusions=True)})


def boutons_cours(bot):
    exclues = bot.etat.extra.get("activites_exclues", [])
    return [[(f"{'🚫' if c in exclues else '✅'} {c.capitalize()}", f"cours:{c}")] for c in cours_disponibles(bot)]


def texte_pauses(bot):
    liste = pauses(bot.config, bot.etat)
    futures = [(du, au) for du, au in liste if au >= datetime.now(PARIS).date()]
    if not futures:
        return "Aucune pause prévue."
    return "Pauses prévues :\n" + "\n".join(f"🏖 du {date_longue(du)} au {date_longue(au)}" for du, au in futures)


def ajouter_pause(bot, du, au):
    bot.etat.extra.setdefault("pauses", []).append({"du": du.isoformat(), "au": au.isoformat()})
    bot.etat.sauver()
    return (f"C'est noté 🏖 Je ne réserve plus rien du {date_longue(du)} au {date_longue(au)}.\n"
            "Les séances déjà réservées pendant cette période restent réservées : "
            "annule-les dans HeitzFit si besoin.")


def repondre(bot, tg, texte):
    t = normaliser(texte)
    aujourdhui = datetime.now(PARIS).date()
    if "SEANCE" in t:
        tg.envoyer(texte_mes_seances(bot))
    elif "SEMAINE" in t:
        tg.envoyer(texte_semaine(bot, aujourdhui))
    elif "REPRENDRE" in t:
        bot.etat.extra["pauses"] = []
        bot.etat.sauver()
        reste = "" if not bot.config.get("pauses") else "\n(Il reste des pauses réglées dans la configuration du bot.)"
        tg.envoyer("C'est reparti ▶️ Je réserve de nouveau tes séances." + reste, clavier=True)
    elif "PAUSE" in t or "VACANCE" in t:
        dates = lire_dates(texte, aujourdhui)
        if dates:
            tg.envoyer(ajouter_pause(bot, *dates))
        else:
            tg.envoyer(texte_pauses(bot) + "\n\nCombien de temps veux-tu faire une pause ?\n"
                       "Ou écris les dates, par exemple : pause 20/12 au 3/1",
                       boutons=[[("1 semaine", "pause:7"), ("2 semaines", "pause:14")],
                                [("3 semaines", "pause:21"), ("▶️ Reprendre", "reprendre")]])
    elif "COURS" in t:
        boutons = boutons_cours(bot)
        tg.envoyer("Touche un cours pour l'activer ✅ ou le désactiver 🚫 :" if boutons else
                   "Aucun cours prévu dans le planning pour l'instant.", boutons=boutons or None)
    else:
        tg.envoyer(AIDE, clavier=True)


def bouton(bot, tg, donnee):
    aujourdhui = datetime.now(PARIS).date()
    if donnee.startswith("pause:"):
        jours = int(donnee.split(":")[1])
        tg.envoyer(ajouter_pause(bot, aujourdhui, aujourdhui + timedelta(days=jours - 1)))
    elif donnee == "reprendre":
        repondre(bot, tg, "reprendre")
    elif donnee.startswith("cours:"):
        cours = donnee.split(":", 1)[1]
        exclues = bot.etat.extra.setdefault("activites_exclues", [])
        if cours in exclues:
            exclues.remove(cours)
            msg = f"✅ {cours.capitalize()} : je le réserve de nouveau."
        else:
            exclues.append(cours)
            msg = f"🚫 {cours.capitalize()} : je ne le réserve plus."
        bot.etat.sauver()
        tg.envoyer(msg, boutons=boutons_cours(bot))


def traiter_messages(bot, log):
    """Lit les messages reçus depuis le dernier passage et y répond. Ignore les inconnus."""
    tg = Telegram()
    if not tg.actif:
        return
    offset = bot.etat.extra.get("telegram_offset")
    for u in tg.nouvelles(offset):
        bot.etat.extra["telegram_offset"] = u["update_id"] + 1
        bot.etat.sauver()
        if "callback_query" in u:
            cb = u["callback_query"]
            tg.acquitter(cb["id"])
            if str(cb.get("message", {}).get("chat", {}).get("id")) == tg.chat_id:
                bouton(bot, tg, cb.get("data", ""))
                log("Telegram : bouton traité.")
        elif "message" in u:
            msg = u["message"]
            if str(msg.get("chat", {}).get("id")) != tg.chat_id:
                continue  # bot privé : on ne répond pas aux inconnus
            repondre(bot, tg, msg.get("text", ""))
            log("Telegram : message traité.")

