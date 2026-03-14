import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

def send_telegram_alert(job_data, match_score, reason=""):
    location = job_data.get("location", "").lower()
    if "boston" in location or "chicago" in location:
        priority = "⭐ PRIORITY LOCATION"
    else:
        priority = "🌐 US / Remote"

    if reason == "TITLE MATCH":
        score_text = "🎯 Strong title match"
    elif reason == "NO DESC":
        score_text = "📝 No description (check manually)"
    elif match_score == -1:
        score_text = "📝 No description"
    elif match_score >= 0.5:
        score_text = f"🟢 Match: {match_score:.0%}"
    elif match_score >= 0.3:
        score_text = f"🟡 Match: {match_score:.0%}"
    else:
        score_text = f"🟠 Match: {match_score:.0%}"

    # Build tags for sponsorship and date verification
    tags = []
    sponsorship = job_data.get("sponsorship_flag")
    if sponsorship == "warning":
        tags.append("⚠️ May require US citizenship/clearance")
    elif sponsorship == "positive":
        tags.append("✅ Visa sponsorship indicated")

    date_verified = job_data.get("date_verified", True)
    if not date_verified:
        tags.append("❓ Unverified posting date")

    tags_text = "\n".join(tags)
    if tags_text:
        tags_text = "\n" + tags_text

    message = (
        f"🚨 *NEW JOB ALERT*\n\n"
        f"*{job_data['title']}*\n"
        f"🏢 {job_data['company']}\n"
        f"📍 {job_data['location']}\n"
        f"🌐 {job_data['site'].capitalize()}\n"
        f"{score_text}\n"
        f"{priority}{tags_text}\n\n"
        f"[Apply Now]({job_data['job_url']})"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            logger.info("[%s] %s @ %s", reason, job_data["title"], job_data["company"])
        else:
            logger.error("Telegram API error: %s", resp.text)
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
