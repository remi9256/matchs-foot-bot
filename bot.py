import requests
import os
import json
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_KEY = os.environ.get("FOOTBALL_DATA_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Championnats + Coupes + Coupes d'Europe
COMPETITIONS = {
    "FL1": "🇫🇷 Ligue 1", "PL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "PD": "🇪🇸 La Liga", "SA": "🇮🇹 Serie A", "BL1": "🇩🇪 Bundesliga",
    "FAC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 FA Cup", "DFB": "🇩🇪 DFB-Pokal",
    "CIT": "🇮🇹 Coppa Italia", "CDR": "🇪🇸 Copa del Rey",
    "FLC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League Cup",
    "CL": "🏆 Champions League", "EL": "🏆 Europa League",
    "UCL": "🏆 Conference League",
}

TV_CHANNELS = {
    "FL1": "📺 Ligue 1+ / beIN", "PL": "📺 Canal+",
    "PD": "📺 beIN Sports", "SA": "📺 DAZN",
    "BL1": "📺 beIN Sports", "FAC": "📺 Canal+",
    "DFB": "📺 beIN Sports", "CIT": "📺 DAZN",
    "CDR": "📺 beIN Sports", "FLC": "📺 Canal+",
    "CL": "📺 Canal+", "EL": "📺 Canal+", "UCL": "📺 Canal+",
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
                matches = response.json().get("matches", [])
                if matches:
                    all_matches.extend(matches)
                    print(f"✅ {name}: {len(matches)} matchs")
            elif response.status_code == 403:
                print(f"🔒 {name}: plan payant")
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


def build_match_list_for_ai(matches):
    """Construit une liste de matchs pour l'analyse IA."""
    tz_fr = timezone(timedelta(hours=1))
    scheduled = []

    for match in matches:
        if match["status"] not in ("SCHEDULED", "TIMED"):
            continue

        utc_time = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
        heure_fr = utc_time.astimezone(tz_fr)

        home = match["homeTeam"].get("shortName") or match["homeTeam"]["name"]
        away = match["awayTeam"].get("shortName") or match["awayTeam"]["name"]
        comp = match["competition"]["name"]

        scheduled.append(f"- {home} vs {away} ({comp}, {heure_fr.strftime('%Hh%M')})")

    return scheduled


def get_ai_analysis(match_list):
    """Analyse les matchs via Gemini AI."""
    if not GEMINI_API_KEY or not match_list:
        return None

    matches_text = "\n".join(match_list)

    prompt = f"""Tu es un expert en analyse de football et paris sportifs. Voici les matchs du jour :

{matches_text}

Analyse ces matchs et identifie les 3 à 5 meilleures opportunités de paris. Pour chaque pari recommandé :

1. Indique le match et le type de pari (résultat 1N2, total buts, les deux équipes marquent, etc.)
2. Donne ta probabilité estimée (en %)
3. Donne une note de confiance sur 10
4. Utilise le système feu tricolore : 🟢 (8-10/10), 🟡 (6-7/10), 🔴 (4-5/10)
5. Explique brièvement pourquoi en 1-2 lignes

RÈGLES STRICTES :
- JAMAIS de paris handicap
- JAMAIS de cotes entre 1.01 et 1.10
- Privilégie la probabilité de réussite
- Si aucun match n'inspire confiance, dis "PAS DE PARI AUJOURD'HUI"
- Sois honnête et prudent
- Rappelle que les paris comportent des risques

Format ta réponse de manière concise pour Telegram (pas de markdown complexe, juste des emojis et du texte simple). Maximum 1500 caractères."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }

    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"✅ Analyse IA générée ({len(text)} caractères)")
            return text
        else:
            print(f"❌ Erreur Gemini: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Erreur Gemini: {e}")
        return None


def send_telegram(message):
    """Envoie un message via Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Telegram limite à 4096 caractères
    if len(message) > 4096:
        message = message[:4090] + "\n..."
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ Message Telegram envoyé !")
    else:
        # Retry sans markdown si erreur de parsing
        print(f"⚠️ Erreur Markdown, retry sans formatage...")
        payload["parse_mode"] = ""
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Message envoyé (sans formatage)")
        else:
            print(f"❌ Erreur Telegram: {response.text[:200]}")


def main():
    print("=" * 50)
    print("🔄 Récupération des matchs...")
    print(f"🔑 Football API: {'Oui' if API_KEY else 'NON'}")
    print(f"🤖 Gemini API: {'Oui' if GEMINI_API_KEY else 'NON'}")
    print("=" * 50)

    # 1. Récupérer et envoyer les matchs
    matches = get_fixtures()
    print(f"\n📋 {len(matches)} matchs trouvés")

    message = format_message(matches)
    print(message)
    send_telegram(message)

    # 2. Analyse IA des matchs à venir
    match_list = build_match_list_for_ai(matches)
    if match_list:
        print(f"\n🤖 Analyse IA de {len(match_list)} matchs à venir...")
        analysis = get_ai_analysis(match_list)
        if analysis:
            ai_message = f"🤖 *Analyse IA — Paris du jour*\n\n{analysis}\n\n⚠️ _Rappel : les paris sportifs comportent des risques. Ne misez que ce que vous pouvez perdre._"
            send_telegram(ai_message)
        else:
            print("⚠️ Pas d'analyse IA disponible")
    else:
        print("ℹ️ Aucun match à venir à analyser")


if __name__ == "__main__":
    main()
