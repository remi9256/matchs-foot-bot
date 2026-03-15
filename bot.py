import requests
import os
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_KEY = os.environ.get("FOOTBALL_DATA_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

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

ODDS_SPORT_KEYS = {
    "FL1": "soccer_france_ligue_one",
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "SA":  "soccer_italy_serie_a",
    "BL1": "soccer_germany_bundesliga",
    "FAC": "soccer_fa_cup",
    "CL":  "soccer_uefa_champs_league",
    "EL":  "soccer_uefa_europa_league",
    "UCL": "soccer_uefa_europa_conference_league",
    "CDR": "soccer_spain_copa_del_rey",
    "CIT": "soccer_italy_coppa_italia",
    "DFB": "soccer_germany_dfb_pokal",
    "FLC": "soccer_efl_cup",
}

# Bookmakers préférés par ordre de priorité
PREFERRED_BOOKMAKERS = ["betclic", "winamax", "unibet", "betsson", "pinnacle", "1xbet"]

DISPLAY_ORDER = ["FL1", "PL", "PD", "SA", "BL1", "CL", "EL", "UCL", "FAC", "FLC", "CDR", "CIT", "DFB"]


def get_odds():
    """Récupère les cotes pour tous les matchs du jour."""
    odds_data = {}
    if not ODDS_API_KEY:
        print("⚠️ Pas de clé Odds API")
        return odds_data

    for code, sport_key in ODDS_SPORT_KEYS.items():
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                games = response.json()
                for game in games:
                    home = game.get("home_team", "")
                    away = game.get("away_team", "")

                    # Chercher le meilleur bookmaker disponible
                    best_cotes = None
                    best_bk = None

                    bookmakers = game.get("bookmakers", [])
                    # D'abord chercher un bookmaker préféré
                    for pref in PREFERRED_BOOKMAKERS:
                        for bk in bookmakers:
                            if bk["key"] == pref:
                                cotes = extract_cotes(bk, home, away)
                                if cotes:
                                    best_cotes = cotes
                                    best_bk = bk.get("title", pref)
                                    break
                        if best_cotes:
                            break

                    # Sinon prendre le premier bookmaker dispo
                    if not best_cotes and bookmakers:
                        bk = bookmakers[0]
                        cotes = extract_cotes(bk, home, away)
                        if cotes:
                            best_cotes = cotes
                            best_bk = bk.get("title", "?")

                    if best_cotes:
                        # Stocker avec plusieurs clés pour faciliter le matching
                        best_cotes["bk"] = best_bk
                        odds_data[f"{home}|{away}".lower()] = best_cotes

                remaining = response.headers.get("x-requests-remaining", "?")
                if games:
                    print(f"🎰 {COMPETITIONS.get(code, code)}: {len(games)} matchs avec cotes (reste: {remaining})")
            elif response.status_code in (404, 422):
                pass
            elif response.status_code == 429:
                print(f"⚠️ {COMPETITIONS.get(code, code)}: rate limit")
            else:
                print(f"⚠️ Odds {code}: erreur {response.status_code}")
        except Exception as e:
            print(f"❌ Odds {code}: {e}")

    print(f"\n🎰 {len(odds_data)} matchs avec cotes au total")
    return odds_data


def extract_cotes(bookmaker, home, away):
    """Extrait les cotes 1/N/2 d'un bookmaker."""
    for market in bookmaker.get("markets", []):
        if market["key"] == "h2h":
            cotes = {}
            for o in market["outcomes"]:
                if o["name"] == home:
                    cotes["1"] = o["price"]
                elif o["name"] == away:
                    cotes["2"] = o["price"]
                elif o["name"] == "Draw":
                    cotes["N"] = o["price"]
            if len(cotes) >= 2:
                return cotes
    return None


def match_odds(home, away, odds_data):
    """Cherche les cotes correspondant à un match."""
    home_l = home.lower().strip()
    away_l = away.lower().strip()

    # Match exact
    key = f"{home_l}|{away_l}"
    if key in odds_data:
        return odds_data[key]

    # Match partiel : chercher des mots en commun
    home_words = [w for w in home_l.replace("fc", "").replace("ac", "").split() if len(w) > 3]
    away_words = [w for w in away_l.replace("fc", "").replace("ac", "").split() if len(w) > 3]

    for okey, cotes in odds_data.items():
        parts = okey.split("|")
        if len(parts) != 2:
            continue
        h, a = parts

        home_match = any(w in h for w in home_words) if home_words else False
        away_match = any(w in a for w in away_words) if away_words else False

        if home_match and away_match:
            return cotes

    return None


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
                matches = response.json().get("matches", [])
                if matches:
                    all_matches.extend(matches)
                    print(f"✅ {name}: {len(matches)} matchs")
            elif response.status_code == 403:
                print(f"🔒 {name}: plan payant")
        except Exception as e:
            print(f"❌ {name}: {e}")

    return all_matches


def format_message(matches, odds_data):
    """Formate les matchs avec cotes."""
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

        stage = match.get("stage", "")
        stage_labels = {
            "FINAL": "🏅 Finale", "SEMI_FINALS": "Demi",
            "QUARTER_FINALS": "1/4", "LAST_16": "1/8",
            "LAST_32": "1/16", "LAST_64": "1/32",
        }
        stage_str = f" ({stage_labels[stage]})" if stage in stage_labels else ""

        # Cotes
        cotes = match_odds(home, away, odds_data)
        if cotes and status not in ("FINISHED", "IN_PLAY", "PAUSED"):
            c1 = cotes.get("1", "-")
            cn = cotes.get("N", "-")
            c2 = cotes.get("2", "-")
            bk = cotes.get("bk", "")
            cotes_str = f"\n      📊 {bk}: {c1} | {cn} | {c2}"
        else:
            cotes_str = ""

        line = f"  • {home} vs {away} — {heure_str}{score_str}{stage_str}{cotes_str}"
        par_comp[code].append((heure_str, line))

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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ Message Telegram envoyé !")
    else:
        print(f"❌ Erreur Telegram: {response.text}")


def main():
    print("=" * 50)
    print("🔄 Récupération des matchs et cotes...")
    print(f"🔑 Football API: {'Oui' if API_KEY else 'NON'}")
    print(f"🎰 Odds API: {'Oui' if ODDS_API_KEY else 'NON'}")
    print("=" * 50)

    odds_data = get_odds()
    matches = get_fixtures()
    print(f"\n📋 {len(matches)} matchs trouvés")

    message = format_message(matches, odds_data)
    print("\n" + message)
    send_telegram(message)


if __name__ == "__main__":
    main()
