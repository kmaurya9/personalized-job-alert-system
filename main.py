import time
import logging
from datetime import datetime
import schedule
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import (
    SEARCH_TERMS, LOCATIONS, MATCH_THRESHOLD,
    CHECK_INTERVAL_MINUTES, RESUME_PATH,
    ACTIVE_HOURS_START, ACTIVE_HOURS_END,
)
from scraper import init_db, get_new_jobs, save_job
from notifier import send_telegram_alert
from logger_setup import setup_logging

logger = logging.getLogger(__name__)

def load_resume():
    with open(RESUME_PATH, "r", encoding="utf-8") as f:
        return f.read()

def compute_match_score(resume_text, job_description):
    if not job_description or job_description.strip() == "" or job_description == "nan":
        return -1

    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    try:
        tfidf_matrix = vectorizer.fit_transform([resume_text, job_description])
        score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(score)
    except Exception:
        return -1

def is_within_active_hours():
    current_hour = datetime.now().hour
    return ACTIVE_HOURS_START <= current_hour < ACTIVE_HOURS_END

def run_scan():
    if not is_within_active_hours():
        logger.info(
            "Outside active hours (%d:00-%d:00). Skipping scan.",
            ACTIVE_HOURS_START, ACTIVE_HOURS_END,
        )
        return

    from scraper import reset_scan_tracker, cleanup_old_jobs
    reset_scan_tracker()
    cleanup_old_jobs(30)

    now = datetime.now()
    logger.info("=" * 50)
    logger.info(
        "Scanning at %s — only jobs from TODAY (%s)",
        now.strftime("%I:%M %p"), now.strftime("%b %d, %Y"),
    )
    logger.info("=" * 50)

    resume_text = load_resume()
    total_new = 0
    total_alerted = 0
    total_skipped = 0

    for search_term in SEARCH_TERMS:
        for location in LOCATIONS:
            try:
                logger.info("'%s' in '%s'...", search_term, location)
                new_jobs = get_new_jobs(search_term, location)

                if not new_jobs:
                    logger.debug("nothing new")
                    continue

                for job_hash, job_data in new_jobs:
                    total_new += 1
                    strong = job_data.pop("strong_title_match", False)
                    score = compute_match_score(resume_text, job_data["description"])

                    should_alert = False
                    reason = ""

                    if strong:
                        should_alert = True
                        reason = "TITLE MATCH"
                    elif score == -1:
                        should_alert = True
                        reason = "NO DESC"
                    elif score >= MATCH_THRESHOLD:
                        should_alert = True
                        reason = f"DESC MATCH {score:.0%}"

                    if should_alert:
                        job_data["match_score"] = max(score, 0)
                        try:
                            send_telegram_alert(job_data, score, reason)
                        except Exception as e:
                            logger.error("Failed to send alert for %s: %s", job_data["title"], e)
                        job_data["alerted"] = 1
                        total_alerted += 1
                        time.sleep(1)
                    else:
                        total_skipped += 1
                        logger.debug(
                            "Skipped (%s): %s @ %s",
                            f"{score:.0%}" if score >= 0 else "N/A",
                            job_data["title"], job_data["company"],
                        )
                        job_data["match_score"] = score

                    save_job(job_hash, job_data)

            except Exception as e:
                logger.error(
                    "Error processing '%s' in '%s': %s. Continuing.",
                    search_term, location, e,
                )
                continue

    logger.info("Done: %d relevant intern/co-op jobs found", total_new)
    logger.info("  %d alerts sent to Telegram", total_alerted)
    logger.info("  %d skipped (weak title + low desc match)", total_skipped)
    logger.info("Next scan in %d minutes...", CHECK_INTERVAL_MINUTES)

def main():
    setup_logging()

    now = datetime.now()
    logger.info("Job Alert System v4.0 — Intern/Co-op Edition")
    logger.info("  Date: %s", now.strftime("%B %d, %Y"))
    logger.info("  Freshness: ONLY today's jobs (reposts blocked)")
    logger.info("  Checking every %d min", CHECK_INTERVAL_MINUTES)
    logger.info("  Active hours: %d:00 - %d:00", ACTIVE_HOURS_START, ACTIVE_HOURS_END)
    logger.info("  Roles: %d search terms", len(SEARCH_TERMS))
    logger.info("  Locations: %s", ", ".join(LOCATIONS))
    logger.info("  Sponsorship filter: ENABLED")

    init_db()
    run_scan()

    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_scan)

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
