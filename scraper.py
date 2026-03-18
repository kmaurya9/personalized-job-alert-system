import sqlite3
import hashlib
import re
import time
import logging
from datetime import datetime, date
from jobspy import scrape_jobs
from config import DB_PATH

logger = logging.getLogger(__name__)

# Drop ZipRecruiter — constant 502 errors
SITES = ["indeed", "linkedin", "google"]

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

def is_us_based(row, search_location=""):
    state = str(row.get("state", "") or "").strip().upper()
    if state in US_STATES:
        return True

    country = str(row.get("country", "") or "").strip().lower()
    if country in ("us", "usa", "united states", "united states of america"):
        return True

    # Explicit non-US country — always reject
    if country != "":
        return False

    # No country info — use search context
    city = str(row.get("city", "") or "").strip().lower()
    if "remote" in search_location.lower():
        # Remote search: only allow if city is empty or says "remote"
        return city == "" or "remote" in city
    else:
        # City-specific US search (e.g. "Boston, MA") — trust the search constraint
        return True

_scan_seen = set()

def reset_scan_tracker():
    global _scan_seen
    _scan_seen = set()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs_seen (
            hash TEXT PRIMARY KEY,
            site TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            job_url TEXT,
            description TEXT,
            first_seen_at TEXT,
            match_score REAL DEFAULT 0,
            alerted INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def make_hash(title, company):
    raw = f"{title}|{company}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()

def is_new_job(job_hash):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT 1 FROM jobs_seen WHERE hash = ?", (job_hash,))
    exists = cursor.fetchone() is not None
    conn.close()
    if exists:
        return False
    if job_hash in _scan_seen:
        return False
    return True

def mark_seen_in_scan(job_hash):
    _scan_seen.add(job_hash)

def save_job(job_hash, job_data):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO jobs_seen
        (hash, site, title, company, location, job_url, description, first_seen_at, match_score, alerted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_hash,
        job_data.get("site", ""),
        job_data.get("title", ""),
        job_data.get("company", ""),
        job_data.get("location", ""),
        job_data.get("job_url", ""),
        job_data.get("description", ""),
        datetime.now().isoformat(),
        job_data.get("match_score", 0),
        job_data.get("alerted", 0),
    ))
    conn.commit()
    conn.close()

def cleanup_old_jobs(days=30):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        DELETE FROM jobs_seen
        WHERE first_seen_at < datetime('now', ?)
    """, (f'-{days} days',))
    conn.commit()
    conn.close()

def get_hours_since_midnight():
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hours = (now - midnight).total_seconds() / 3600
    return max(1, int(hours))

def is_posted_today(date_posted):
    if date_posted is None:
        return True
    try:
        if hasattr(date_posted, 'date'):
            posted_date = date_posted.date()
        elif isinstance(date_posted, date):
            posted_date = date_posted
        elif isinstance(date_posted, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
                try:
                    posted_date = datetime.strptime(date_posted, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                return True
        else:
            return True
        return posted_date == date.today()
    except Exception:
        return True

def is_outdated_season(title):
    """Catch jobs like 'Summer 2025' when it's 2026."""
    current_year = date.today().year
    years = re.findall(r'20\d{2}', title)
    for year_str in years:
        year = int(year_str)
        if year < current_year:
            return True
    return False

def is_intern_or_coop(title):
    title_lower = title.lower()
    keywords = ["intern", "co-op", "coop", "co op", "summer", "apprentice", "trainee"]
    return any(kw in title_lower for kw in keywords)

def is_strong_title_match(title):
    title_lower = title.lower()
    strong_role_keywords = [
        # SWE / Backend
        "software engineer", "backend engineer", "backend developer",
        "full stack", "fullstack", "full-stack",
        # GenAI / Agentic
        "generative ai", "gen ai", "genai",
        "llm engineer", "large language model",
        "agentic ai", "agentic", "ai agent",
        # AI Engineering (broad — JD will determine if it's GenAI)
        "ai engineer", "ai intern", "ai developer", "ai software",
    ]
    return any(kw in title_lower for kw in strong_role_keywords)

def is_total_garbage(title):
    title_lower = title.lower()
    garbage = [
        "psychology", "psychiatry", "clinical trial", "nursing",
        "pharmacy", "dental", "veterinary",
        "sales intern", "sales summer", "marketing intern",
        "graphic design", "interior design",
        "accounting intern", "audit intern", "tax intern",
        "fleet operations", "warehouse intern",
        "qc operations", "quality control",
        "investor relations",
        "behavioral specialist",
        "site planning",
    ]
    return any(g in title_lower for g in garbage)

def check_sponsorship(description):
    """
    Scan job description for sponsorship/citizenship signals.
    Returns: "warning", "positive", or None
    """
    if not description or description.strip() == "" or str(description) == "nan":
        return None

    desc_lower = description.lower()

    # Check positive signals FIRST — if a job says "will sponsor",
    # it's accessible to F1 students even if it also mentions "US citizen"
    positive_phrases = [
        "visa sponsorship available",
        "will sponsor visa",
        "will sponsor work",
        "we will sponsor",
        "we sponsor",
        "sponsorship is available",
        "international students welcome",
        "international students encouraged",
    ]
    for phrase in positive_phrases:
        if phrase in desc_lower:
            return "positive"

    # Short tokens need word-boundary regex to avoid false positives
    # ("OPTional" should NOT match, but "OPT/CPT welcome" should)
    if re.search(r'\bopt\b', desc_lower) or re.search(r'\bcpt\b', desc_lower):
        return "positive"

    # Check negative signals
    negative_phrases = [
        "us citizen",
        "u.s. citizen",
        "permanent resident",
        "green card",
        "no sponsorship",
        "not sponsor",
        "without sponsorship",
        "does not sponsor",
        "unable to sponsor",
        "cannot sponsor",
        "security clearance",
        "us person",
        "u.s. person",
        "itar",
        "authorized to work without",
        "authorized to work in the united states without",
        "work authorization required",
    ]
    for phrase in negative_phrases:
        if phrase in desc_lower:
            return "warning"

    return None

def fetch_jobs(search_term, location):
    hours = get_hours_since_midnight()
    max_retries = 2

    for attempt in range(max_retries):
        try:
            jobs_df = scrape_jobs(
                site_name=SITES,
                search_term=search_term,
                location=location,
                results_wanted=25,
                hours_old=hours,
                country_indeed="USA",
                linkedin_fetch_description=True,
            )
            return jobs_df
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "Scraping failed for '%s' in '%s' (attempt %d/%d): %s. Retrying in 30s...",
                    search_term, location, attempt + 1, max_retries, e,
                )
                time.sleep(30)
            else:
                logger.error(
                    "Scraping failed for '%s' in '%s' after %d attempts: %s. Skipping.",
                    search_term, location, max_retries, e,
                )
                return None

def get_new_jobs(search_term, location):
    jobs_df = fetch_jobs(search_term, location)

    if jobs_df is None or jobs_df.empty:
        return []

    new_jobs = []
    for _, row in jobs_df.iterrows():
        title = str(row.get("title", ""))
        company = str(row.get("company", ""))
        loc = str(row.get("city", "")) + ", " + str(row.get("state", ""))

        # Create hash early — we save EVERYTHING to DB
        job_hash = make_hash(title, company)

        # Already seen? Skip silently
        if not is_new_job(job_hash):
            continue

        # Mark seen immediately
        mark_seen_in_scan(job_hash)

        # FILTER 1: Must be US-based
        if not is_us_based(row, location):
            logger.debug("Non-US job skipped: %s @ %s (%s, %s)", title, company, row.get("city", ""), row.get("country", ""))
            save_job(job_hash, {
                "site": str(row.get("site", "")), "title": title,
                "company": company, "location": loc,
                "job_url": "", "description": "", "match_score": 0, "alerted": 0,
            })
            continue

        # FILTER 2: Must be intern/co-op
        if not is_intern_or_coop(title):
            save_job(job_hash, {
                "site": str(row.get("site", "")), "title": title,
                "company": company, "location": loc,
                "job_url": "", "description": "", "match_score": 0, "alerted": 0,
            })
            continue

        # FILTER 3: Block garbage
        if is_total_garbage(title):
            logger.debug("Garbage: %s @ %s", title, company)
            save_job(job_hash, {
                "site": str(row.get("site", "")), "title": title,
                "company": company, "location": loc,
                "job_url": "", "description": "", "match_score": 0, "alerted": 0,
            })
            continue

        # FILTER 4: Check if actually posted today (anti-repost by date)
        date_posted = row.get("date_posted", None)
        date_verified = date_posted is not None
        if not is_posted_today(date_posted):
            logger.debug("Repost (posted %s): %s @ %s", date_posted, title, company)
            save_job(job_hash, {
                "site": str(row.get("site", "")), "title": title,
                "company": company, "location": loc,
                "job_url": "", "description": "", "match_score": 0, "alerted": 0,
            })
            continue

        # FILTER 5: Catch outdated season (e.g. "Summer 2025" in 2026)
        if is_outdated_season(title):
            logger.debug("Outdated: %s @ %s", title, company)
            save_job(job_hash, {
                "site": str(row.get("site", "")), "title": title,
                "company": company, "location": loc,
                "job_url": "", "description": "", "match_score": 0, "alerted": 0,
            })
            continue

        # Sponsorship/citizenship check (annotation only — no rejection)
        description = str(row.get("description", ""))
        sponsorship_flag = check_sponsorship(description)
        if sponsorship_flag:
            logger.debug("Sponsorship [%s]: %s @ %s", sponsorship_flag, title, company)

        strong_match = is_strong_title_match(title)

        job_data = {
            "site": str(row.get("site", "")),
            "title": title,
            "company": company,
            "location": loc,
            "job_url": str(row.get("job_url", "")),
            "description": description,
            "strong_title_match": strong_match,
            "sponsorship_flag": sponsorship_flag,
            "date_verified": date_verified,
        }
        new_jobs.append((job_hash, job_data))

    return new_jobs
