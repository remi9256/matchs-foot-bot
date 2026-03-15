import requests
import os
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_KEY = os.environ.get("FOOTBALL_DATA_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Championnats + Coupes + Champions League
COMPETITIONS = {
    # Championnats
    "FL1": "🇫🇷 Ligue 1",
    "PL":  "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "PD":  "🇪🇸 La Liga",
    "SA":  "🇮🇹 Serie A",
    "BL1": "🇩🇪 Bundesliga",
    # Coupes nationales
    "FAC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 FA Cup",
    "DFB": "🇩🇪 DFB-Pokal",
    "CIT": "🇮🇹 Coppa Italia",
    "CDR": "🇪🇸 Copa del Rey",
    "FLC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League Cup",
    # Coupes d'Europe
    "CL":  "🏆 Champions League",
    "EL":  "🏆 Europa League",
    "UCL": "🏆 Conference League",
}

# Ordre d'affichage dans le message
DISPLAY_ORDER = ["FL1", "PL", "PD", "SA", "BL1", "CL", "EL", "UCL", "FAC", "FLC", "CDR", "CIT", "DFB"]


def get_fixtures():
    """Récupère les matchs du jour pour chaque compétition."""
    tz_fr = timezone(timedelta(hours=1))
    today = datetime.now(tz_fr)
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"📅 Date: {today_str}")
    all_matches = []
    headers = {"X-Auth-Token": API_KEY}

    for code, name in COMPETITIONS.items():
        url = f"https://api.football-data.org/v4/competitions/{code}/matches"
        params = {"dateFrom": today_str, "dateTo": tomorrow_str}

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                matches = data.get("matches", [])
                if matches:
                    all_matches.extend(matches)
                    print(f"✅ {name}: {len(matches)} matchs")
                # Pas de message si 0 match (normal si pas de journée)
            elif response.status_code == 403:
                print(f"🔒 {name}: non dispo (plan payant)")
            else:
                print(f"⚠️ {name}: erreur {response.status_code}")
        except Exception as e:
            print(f"❌ {name}: {e}")

    return all_matches


def format_message(matches):
    """Formate les matchs en message Telegram."""
    tz_fr = timezone(timedelta(hours=1))
    today = datetime.now(tz_fr).strftime("%d/%m/%Y")
    message = f"⚽ *Matchs du jour — {today}*\n\n"

    par_comp = {}
    for match in matches:
        code = match["competition"]["code"]
        if code not in par_comp:
            par_comp[code] = []

        utc_time = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
        heure_fr = utc_time.astimezone(tz_fr)
        heure_str = heure_fr.strftime("%Hh%M")

        home = match["homeTeam"].get("shortName") or match["homeTeam"]["name"]
        away = match["awayTeam"].get("shortName") or match["awayTeam"]["name"]

        status = match["status"]
        if status == "FINISHED":
            h = match["score"]["fullTime"]["home"]
            a = match["score"]["fullTime"]["away"]
            score_str = f" → {h}-{a} ✅"
        elif status in ("IN_PLAY", "PAUSED", "EXTRA_TIME", "PENALTY_SHOOTOUT"):
            h = match["score"]["fullTime"]["home"] or 0
            a = match["score"]["fullTime"]["away"] or 0
            score_str = f" → {h}-{a} 🔴 LIVE"
        else:
            score_str = ""

        # Pour les coupes, afficher le tour
        stage = match.get("stage", "")
        stage_labels = {
            "FINAL": "🏅 Finale",
            "SEMI_FINALS": "Demi-finale",
            "QUARTER_FINALS": "Quart de finale",
            "LAST_16": "8e de finale",
            "LAST_32": "16e de finale",
            "LAST_64": "32e de finale",
            "ROUND_4": "4e tour",
            "ROUND_3": "3e tour",
        }
        stage_str = f" ({stage_labels[stage]})" if stage in stage_labels else ""

        par_comp[code].append((heure_str, f"  • {home} vs {away} — {heure_str}{score_str}{stage_str}"))

    for code in DISPLAY_ORDER:
        if code in par_comp:
            par_comp[code].sort(key=lambda x: x[0])
            message += f"*{COMPETITIONS[code]}*\n"
            for _, m in par_comp[code]:
                message += f"{m}\n"
            message += "\n"

    if not matches:
        message += "🚫 Aucun match aujourd'hui."
    else:
        message += f"📊 *{len(matches)} matchs* au total"

    return message


def send_telegram(message):
    """Envoie le message via Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ Message Telegram envoyé !")
    else:
        print(f"❌ Erreur Telegram: {response.text}")


def main():
    print("🔄 Récupération des matchs...")
    print(f"🔑 Clé API: {'Oui' if API_KEY else 'NON !!!'}")
    matches = get_fixtures()
    print(f"\n📋 TOTAL: {len(matches)} matchs")
    message = format_message(matches)
    print(message)
    send_telegram(message)


if __name__ == "__main__":
    main()
