"""Client Telegram minimal (bot privé : ne répond qu'à la conversation TELEGRAM_CHAT_ID).

Pour trouver l'identifiant de la conversation après avoir écrit /start au bot :
    python -m piscine_bot.telegram
"""

import json
import os

import requests
from dotenv import load_dotenv

CLAVIER = {
    "keyboard": [["📅 Mes séances", "🗓 Ma semaine"], ["🏖 Pause", "🏊 Mes cours"], ["❓ Aide"]],
    "resize_keyboard": True,
    "is_persistent": True,
}


class Telegram:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    @property
    def actif(self):
        return bool(self.token and self.chat_id)

    def appel(self, methode, fichiers=None, **params):
        """N'échoue jamais : Telegram en panne ne doit pas empêcher une réservation."""
        if not self.token:
            return None
        try:
            r = requests.post(f"https://api.telegram.org/bot{self.token}/{methode}",
                              data=params if fichiers else None, json=None if fichiers else params,
                              files=fichiers, timeout=15)
            data = r.json()
            return data.get("result") if data.get("ok") else None
        except (requests.RequestException, ValueError):
            return None

    def envoyer(self, texte, boutons=None, silencieux=False, clavier=False):
        """boutons : liste de lignes de (libellé, url) ou (libellé, "donnee:..."), en boutons sous le message."""
        if not self.actif:
            return
        params = {"chat_id": self.chat_id, "text": texte, "disable_notification": silencieux,
                  "link_preview_options": {"is_disabled": True}}
        if boutons:
            params["reply_markup"] = {"inline_keyboard": [
                [{"text": t, "url": v} if v.startswith("http") else {"text": t, "callback_data": v} for t, v in rang]
                for rang in boutons]}
        elif clavier:
            params["reply_markup"] = CLAVIER
        self.appel("sendMessage", **params)

    def envoyer_fichier(self, nom_fichier, contenu, legende="", silencieux=False):
        if not self.actif:
            return
        self.appel("sendDocument", fichiers={"document": (nom_fichier, contenu, "text/calendar")},
                   chat_id=self.chat_id, caption=legende, disable_notification=json.dumps(silencieux))

    def nouvelles(self, offset):
        """Messages reçus depuis le dernier passage (Telegram les garde 24h)."""
        return self.appel("getUpdates", offset=offset, timeout=0,
                          allowed_updates=["message", "callback_query"]) or []

    def acquitter(self, id_callback, texte=""):
        self.appel("answerCallbackQuery", callback_query_id=id_callback, text=texte)


def main():
    load_dotenv(".env")
    tg = Telegram()
    if not tg.token:
        raise SystemExit("Ajoute TELEGRAM_TOKEN=... dans .env (jeton donné par @BotFather).")
    vus = {}
    for u in tg.appel("getUpdates") or []:
        chat = (u.get("message") or {}).get("chat") or {}
        if chat:
            vus[chat["id"]] = chat.get("first_name") or chat.get("title") or "?"
    if not vus:
        print("Aucun message reçu : ouvre le bot dans Telegram, appuie sur Démarrer (/start), puis relance.")
    for chat_id, prenom in vus.items():
        print(f"Conversation de {prenom} : TELEGRAM_CHAT_ID={chat_id}")


if __name__ == "__main__":
    main()
