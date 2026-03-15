import requests
import os
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_KEY = os.environ.get("FOOTBALL_DATA_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Championnats + Coupes + Coupes d'Europe
COMPETITIONS = {
    "FL1": "🇫🇷 Ligue 1",
    "PL":  "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "PD":  "🇪🇸 La Liga",
    "SA":  "🇮🇹 Serie A",
    "BL1": "🇩🇪 Bundesliga",
    "FAC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 FA Cup",
    "DFB": "🇩🇪 DFB-Pokal",
    "CIT": "🇮🇹 Coppa Italia",
    "CDR": "🇪🇸 Copa del Rey",
    "FLC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League Cup",
    "CL":  "🏆 Champions League",
    "EL":  "🏆 Europa League",
    "UCL": "🏆 Conference League",
}

# Chaînes TV par compétition (diffuseurs France 2025-2026)
TV_CHANNELS = {
    "FL1": "📺 Ligue 1+ / beIN",
    "PL":  "📺 Canal+",
    "PD":  "📺 beIN Sports",
    "SA":  "📺 DAZN",
    "BL1": "📺 beIN Sports",
    "FAC": "📺 Canal+",
    "DFB": "📺 beIN Sports",
    "CIT": "📺 DAZN",
    "CDR": "📺 beIN Sports",
    "FLC": "📺 Canal+",
    "CL":  "📺 Canal+",
    "EL":  "📺 Canal+",
    "UCL": "📺 Canal+",
}

DISPLAY_ORDER = ["FL1", "PL", "PD", "SA", "BL1", "CL", "EL", "UCL", "FAC", "FLC", "CDR", "CIT", "DFB"]


def get_fixtures():
    """Récupère les matchs du jour."""
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
            elif response.status_code == 403:
                print(f"🔒 {name}: plan payant")
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

        # Tour de coupe
        stage = match.get("stage", "")
        stage_labels = {
            "FINAL": "🏅 Finale", "SEMI_FINALS": "Demi",
            "QUARTER_FINALS": "1/4", "LAST_16": "1/8",
            "LAST_32": "1/16", "LAST_64": "1/32",
        }
        stage_str = f" ({stage_labels[stage]})" if stage in stage_labels else ""

        line = f"  • {home} vs {away} — {heure_str}{score_str}{stage_str}"
        par_comp[code].append((heure_str, line))

    for code in DISPLAY_ORDER:
        if code in par_comp:
            par_comp[code].sort(key=lambda x: x[0])
            tv = TV_CHANNELS.get(code, "")
            message += f"*{COMPETITIONS[code]}* {tv}\n"
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
    print("=" * 50)
    print("🔄 Récupération des matchs...")
    print(f"🔑 Clé API: {'Oui' if API_KEY else 'NON'}")
    print("=" * 50)

    matches = get_fixtures()
    print(f"\n📋 TOTAL: {len(matches)} matchs")
    message = format_message(matches)
    print(message)
    send_telegram(message)


if __name__ == "__main__":
    main()
