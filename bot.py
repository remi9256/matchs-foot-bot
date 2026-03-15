import requests
import os
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_KEY = os.environ.get("FOOTBALL_DATA_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

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


def get_mode():
    """Determine si on est en mode matin ou soir."""
    manual = os.environ.get("MANUAL_MODE", "")
    if manual:
        return manual

    cron = os.environ.get("CRON_SCHEDULE", "")
    if "22" in cron:
        return "evening"
    return "morning"


def get_fixtures(include_finished=False):
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
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                matches = resp.json().get("matches", [])
                if matches:
                    all_matches.extend(matches)
                    print(f"✅ {name}: {len(matches)} matchs")
            elif resp.status_code == 403:
                print(f"🔒 {name}: plan payant")
        except Exception as e:
            print(f"❌ {name}: {e}")

    return all_matches


def format_message(matches):
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


def build_results_for_ai(matches):
    """Construit la liste des resultats pour le bilan du soir."""
    tz_fr = timezone(timedelta(hours=1))
    results = []
    for match in matches:
        if match["status"] != "FINISHED":
            continue
        home = match["homeTeam"].get("shortName") or match["homeTeam"]["name"]
        away = match["awayTeam"].get("shortName") or match["awayTeam"]["name"]
        h = match["score"]["fullTime"]["home"]
        a = match["score"]["fullTime"]["away"]
        comp = match["competition"]["name"]
        results.append(f"- {home} {h}-{a} {away} ({comp})")
    return results


def get_ai_analysis(match_list):
    if not GROQ_API_KEY or not match_list:
        return None

    matches_text = "\n".join(match_list)

    prompt = f"""Tu es un expert francais en analyse de football et paris sportifs. Voici les matchs du jour :

{matches_text}

Ta mission : analyser ces matchs et proposer une STRATEGIE DE PARIS claire et structuree.

STRUCTURE DE TA REPONSE :

1) D'abord, liste tes PARIS SIMPLES recommandes (3 a 5 max) :
Pour chaque pari simple, indique :
- Le match et le type de pari (resultat 1N2, total buts, BTTS, etc.)
- Ta probabilite estimee (en %)
- Note de confiance /10
- Feu : 🟢 VERT (8-10/10), 🟡 JAUNE (6-7/10), 🔴 ROUGE (4-5/10)
- Justification en 1 ligne

2) Ensuite, propose UN COMBINE si pertinent (2-3 selections max) :
- Liste les selections du combine
- La cote totale estimee
- La note de confiance globale /10
- Pourquoi ce combine fait sens

3) Termine par ton VERDICT :
- Indique clairement ta preference : "PARIS SIMPLES recommandes" ou "COMBINE recommande" ou "MIX des deux"
- Explique pourquoi en 1 ligne

REGLES STRICTES :
- JAMAIS de paris handicap
- JAMAIS de cotes entre 1.01 et 1.10
- Privilegie TOUJOURS les paris simples (plus surs)
- Ne propose un combine QUE si les selections sont tres solides
- Si aucun match n'inspire confiance : "PAS DE PARI AUJOURD'HUI"
- Sois honnete et prudent
- Reponds en francais
- Pas de markdown, juste du texte simple avec des emojis
- Maximum 2000 caracteres"""

    return call_groq(prompt)


def get_ai_results_review(results_list):
    """Demande a l'IA de faire le bilan de ses paris."""
    if not GROQ_API_KEY or not results_list:
        return None

    results_text = "\n".join(results_list)

    prompt = f"""Tu es un expert francais en analyse de football et paris sportifs. Voici les RESULTATS des matchs du jour :

{results_text}

Ta mission : faire le BILAN de la journee de paris.

Pour chaque resultat :
1) Analyse si les favoris ont gagne ou s'il y a eu des surprises
2) Identifie les resultats previsibles (qui auraient ete des paris gagnants)
3) Identifie les surprises (qui auraient ete des pieges)

Puis donne :
- Un BILAN GLOBAL de la journee (journee previsible ou pleine de surprises ?)
- Les LECONS a retenir pour les prochains paris
- Une NOTE de la journee pour les parieurs /10 (10 = tout etait previsible)

FORMAT :
- Reponds en francais
- Pas de markdown, juste du texte simple avec des emojis
- Sois concis, maximum 1500 caracteres
- Utilise ✅ pour les resultats previsibles et ❌ pour les surprises"""

    return call_groq(prompt)


def call_groq(prompt):
    """Appel generique a l'API Groq."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000
    }

    try:
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            print(f"✅ Reponse IA ({len(text)} caracteres)")
            return text
        else:
            print(f"❌ Erreur Groq: {resp.status_code} - {resp.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ Erreur Groq: {e}")
        return None


def format_results_message(matches):
    """Formate les resultats du soir."""
    tz_fr = timezone(timedelta(hours=1))
    today = datetime.now(tz_fr).strftime("%d/%m/%Y")
    message = f"🏁 Resultats du jour — {today}\n\n"

    par_comp = {}
    for match in matches:
        if match["status"] != "FINISHED":
            continue
        code = match["competition"]["code"]
        if code not in par_comp:
            par_comp[code] = []

        home = match["homeTeam"].get("shortName") or match["homeTeam"]["name"]
        away = match["awayTeam"].get("shortName") or match["awayTeam"]["name"]
        h = match["score"]["fullTime"]["home"]
        a = match["score"]["fullTime"]["away"]

        par_comp[code].append(f"  • {home} {h}-{a} {away}")

    for code in DISPLAY_ORDER:
        if code in par_comp:
            message += f"{COMPETITIONS[code]}\n"
            for m in par_comp[code]:
                message += f"{m}\n"
            message += "\n"

    if not any(par_comp.values()):
        message += "Aucun resultat disponible."

    return message


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if len(message) > 4096:
        message = message[:4090] + "\n..."
    payload = {"chat_id": CHAT_ID, "text": message}
    resp = requests.post(url, json=payload)
    if resp.status_code == 200:
        print("✅ Message Telegram envoye !")
    else:
        print(f"❌ Erreur Telegram: {resp.text[:200]}")


def morning():
    """Envoi du matin : matchs + analyse IA."""
    print("☀️ MODE MATIN")
    matches = get_fixtures()
    print(f"\n📋 {len(matches)} matchs trouves")

    message = format_message(matches)
    send_telegram(message)

    match_list = build_match_list_for_ai(matches)
    if match_list:
        print(f"\n🤖 Analyse IA de {len(match_list)} matchs a venir...")
        analysis = get_ai_analysis(match_list)
        if analysis:
            ai_message = f"🤖 ANALYSE IA — Paris du jour\n\n{analysis}"
            send_telegram(ai_message)
    else:
        print("ℹ️ Aucun match a venir a analyser")


def evening():
    """Envoi du soir : resultats + bilan IA."""
    print("🌙 MODE SOIR")
    matches = get_fixtures()
    print(f"\n📋 {len(matches)} matchs trouves")

    # 1. Envoyer les resultats
    results_msg = format_results_message(matches)
    send_telegram(results_msg)

    # 2. Bilan IA
    results_list = build_results_for_ai(matches)
    if results_list:
        print(f"\n🤖 Bilan IA de {len(results_list)} matchs termines...")
        review = get_ai_results_review(results_list)
        if review:
            review_msg = f"🤖 BILAN IA — Analyse des resultats\n\n{review}"
            send_telegram(review_msg)
    else:
        print("ℹ️ Aucun match termine a analyser")


def main():
    mode = get_mode()
    print("=" * 50)
    print(f"🔄 Mode: {mode}")
    print(f"🔑 Football API: {'Oui' if API_KEY else 'NON'}")
    print(f"🤖 Groq API: {'Oui' if GROQ_API_KEY else 'NON'}")
    print("=" * 50)

    if mode == "evening":
        evening()
    else:
        morning()


if __name__ == "__main__":
    main()
