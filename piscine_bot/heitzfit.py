"""Client minimal pour l'API HeitzFit 4 (celle qu'utilise app.heitzfit.com)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://app.heitzfit.com"
# Identifiant public de l'appli web HeitzFit 4 (production), envoyé par le site à la connexion.
APP_ID = "b0b88fb90e9960f706bb"
PARIS = ZoneInfo("Europe/Paris")


class HeitzfitError(Exception):
    def __init__(self, message, code=None, status=None):
        super().__init__(message)
        self.code = code
        self.status = status


class Heitzfit:
    def __init__(self, id_centre, timeout=30):
        self.id_centre = id_centre
        self.api = f"{BASE_URL}/c/{id_centre}/ws"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "projet_piscine_auto (usage personnel)"

    def _request(self, method, path, **kwargs):
        resp = self.session.request(method, self.api + path, timeout=self.timeout, **kwargs)
        if not resp.ok:
            try:
                code = resp.json().get("ctxCode")
            except ValueError:
                code = None
            raise HeitzfitError(f"{method} {path} -> HTTP {resp.status_code} ({code})", code, resp.status_code)
        return resp.json() if resp.content else None

    def connexion(self, email, mot_de_passe):
        data = self._request("POST", "/api/auth/signin", json={
            "email": email,
            "password": mot_de_passe,
            "targetCenter": self.id_centre,
            "_appId": APP_ID,
        })
        token = (data or {}).get("token")
        if not token:
            raise HeitzfitError("Connexion refusée : pas de jeton dans la réponse", "SESS_TOKEN_KO")
        self.session.headers["Authorization"] = token

    def planning(self, jour: date, nb_jours=1):
        """Renvoie la liste des séances, avec l'heure de début en heure de Paris."""
        data = self._request("GET", "/api/planning/browse", params={
            "startDate": jour.isoformat(),
            "numberOfDays": nb_jours,
            "stackBy": "date",
            "idCenter": self.id_centre,
        })
        seances = []
        for liste in (data or {}).values():
            for s in liste:
                debut = datetime.fromisoformat(s["start"].replace("Z", "+00:00")).astimezone(PARIS)
                seances.append({**s, "debut": debut})
        return sorted(seances, key=lambda s: s["debut"])

    def reserver(self, id_seance, places=1, liste_attente=False):
        return self._request("POST", "/api/planning/book", json={
            "id": id_seance,
            "places": places,
            "joinQueueList": liste_attente,
        })
