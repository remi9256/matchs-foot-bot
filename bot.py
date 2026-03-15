import requests
import os
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_KEY = os.environ.get("API_FOOTBALL_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Les 5 grands championnats européens
LEAGUES = {
    39: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    61: "🇫🇷 Ligue 1",
    135: "🇮🇹 Serie A",
    140: "🇪🇸 La Liga",
    78: "🇩🇪 Bundesliga"
}

# Les saisons à tester (la saison 2025-2026 peut être codée 2025 ou 2024)
SEASONS = [2025, 2024]

def get_fixtures():
    """Récupère les matchs du jour pour les 5 championnats."""
    today = datetime.now(timezone(timedelta(hours=1))).strftime("%Y-%m-%d")
    all_fixtures = []
    found_leagues = set()

    for league_id in LEAGUES:
        for season in SEASONS:
            if league_id in found_leagues:
                break

            url = "https://v3.football.api-sports.io/fixtures"
            params = {
                "date": today,
                "league": league_id,
                "season": season
            }
            headers = {
                "x-apisports-key": API_KEY
            }

            try:
                response = requests.get(url, headers=headers, params=params)
                data = response.json()
                fixtures = data.get("response", [])
                if fixtures:
                    all_fixtures.extend(fixtures)
                    found_leagues.add(league_id)
                    print(f"✅ {LEAGUES[league_id]}: {len(fixtures)} matchs (saison {season})")
                else:
                    print(f"⚠️ {LEAGUES[league_id]}: 0 matchs pour saison {season}")
            except Exception as e:
                print(f"❌ Erreur pour {LEAGUES[league_id]} saison {season}: {e}")

    return all_fixtures


def format_message(fixtures):
    """Formate les matchs en message Telegram."""
    today = datetime.now(timezone(timedelta(hours=1))).strftime("%d/%m/%Y")
    message = f"⚽ *Matchs du jour — {today}*\n\n"

    par_ligue = {}
    for match in fixtures:
        lid = match["league"]["id"]
        if lid not in par_ligue:
            par_ligue[lid] = []

        # Convertir l'heure en heure française
        utc_time = datetime.fromisoformat(match["fixture"]["date"].replace("Z", "+00:00"))
        heure_fr = utc_time.astimezone(timezone(timedelta(hours=1)))
        heure_str = heure_fr.strftime("%Hh%M")

        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        par_ligue[lid].append((heure_str, f"  • {home} vs {away} — {heure_str}"))

    # Ordre d'affichage
    ordre = [61, 39, 140, 135, 78]
    for lid in ordre:
        if lid in par_ligue:
            # Trier par heure
            par_ligue[lid].sort(key=lambda x: x[0])
            message += f"*{LEAGUES[lid]}*\n"
            for _, m in par_ligue[lid]:
                message += f"{m}\n"
            message += "\n"

    if not fixtures:
        message += "🚫 Aucun match des 5 grands championnats aujourd'hui."
    else:
        message += f"📊 *{len(fixtures)} matchs* au total"

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
    fixtures = get_fixtures()
    print(f"📋 {len(fixtures)} matchs trouvés au total")
    message = format_message(fixtures)
    print(message)
    send_telegram(message)


if __name__ == "__main__":
    main()
