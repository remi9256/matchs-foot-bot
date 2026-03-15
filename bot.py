import requests
import os
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_KEY = os.environ.get("FOOTBALL_DATA_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Les 5 grands championnats
LEAGUES = {
    "PL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "FL1": "🇫🇷 Ligue 1",
    "SA": "🇮🇹 Serie A",
    "PD": "🇪🇸 La Liga",
    "BL1": "🇩🇪 Bundesliga"
}


def get_fixtures():
    """Récupère tous les matchs du jour via football-data.org."""
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": API_KEY}

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        matches = data.get("matches", [])
        # Filtrer uniquement les 5 grands championnats
        filtered = [m for m in matches if m["competition"]["code"] in LEAGUES]
        print(f"✅ API football-data.org: {len(filtered)} matchs trouvés sur {len(matches)} total")
        return filtered
    except Exception as e:
        print(f"❌ Erreur API: {e}")
        return []


def format_message(matches):
    """Formate les matchs en message Telegram."""
    tz_fr = timezone(timedelta(hours=1))
    today = datetime.now(tz_fr).strftime("%d/%m/%Y")
    message = f"⚽ *Matchs du jour — {today}*\n\n"

    par_ligue = {}
    for match in matches:
        code = match["competition"]["code"]
        if code not in par_ligue:
            par_ligue[code] = []

        # Convertir l'heure en heure française
        utc_time = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
        heure_fr = utc_time.astimezone(tz_fr)
        heure_str = heure_fr.strftime("%Hh%M")

        home = match["homeTeam"]["shortName"] or match["homeTeam"]["name"]
        away = match["awayTeam"]["shortName"] or match["awayTeam"]["name"]

        # Score si le match est en cours ou terminé
        status = match["status"]
        if status in ("IN_PLAY", "PAUSED", "FINISHED"):
            h_goals = match["score"]["fullTime"]["home"] or 0
            a_goals = match["score"]["fullTime"]["away"] or 0
            score_str = f" ({h_goals}-{a_goals})"
            if status == "FINISHED":
                score_str += " ✅"
            elif status in ("IN_PLAY", "PAUSED"):
                score_str += " 🔴 LIVE"
        else:
            score_str = ""

        par_ligue[code].append((heure_str, f"  • {home} vs {away} — {heure_str}{score_str}"))

    # Ordre d'affichage : Ligue 1 d'abord
    ordre = ["FL1", "PL", "PD", "SA", "BL1"]
    for code in ordre:
        if code in par_ligue:
            par_ligue[code].sort(key=lambda x: x[0])
            message += f"*{LEAGUES[code]}*\n"
            for _, m in par_ligue[code]:
                message += f"{m}\n"
            message += "\n"

    if not matches:
        message += "🚫 Aucun match des 5 grands championnats aujourd'hui."
    else:
        message += f"📊 *{len(matches)} matchs* au total"

    return message


def send_telegram(message):
    """Envoie le message via Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ Message envoyé avec succès !")
    else:
        print(f"❌ Erreur Telegram: {response.text}")


def main():
    print("🔄 Récupération des matchs...")
    matches = get_fixtures()
    print(f"📋 {len(matches)} matchs trouvés")
    message = format_message(matches)
    print(message)
    send_telegram(message)


if __name__ == "__main__":
    main()
