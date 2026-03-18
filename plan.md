# Job Alert System v4.0 — Implementation Plan

## Context

Sanket runs a job alert bot (v3.1) that scrapes LinkedIn, Indeed, and Google Jobs every 60 minutes and sends Telegram alerts for intern/co-op roles in Data/ML/AI. The system works but has critical gaps:

1. **No sponsorship filter** — As an F1 student, jobs requiring US citizenship or offering no sponsorship are dead ends, yet they still trigger alerts (wasted time)
2. **60-min scan interval** — Too slow for being a first applicant
3. **No logging** — Only print() statements; no audit trail, no debugging on a server
4. **Hardcoded secrets** — Telegram token in config.py; can't deploy safely to cloud
5. **No error recovery** — Network failures crash the scan
6. **No deployment setup** — Runs only on local PC; dies when laptop closes

**Goal:** Make the bot smarter (sponsorship awareness), faster (30-min scans), more resilient (retry + logging), and deployable to a free cloud server (Railway with sleep schedule).

---

## Scope (In / Out)

**IN:**
- Sponsorship/Citizenship filter (NEW — highest value)
- Null date tagging in alerts
- Scan interval: 60 → 30 minutes
- Logging overhaul (all print → logging module)
- Secrets to environment variables
- Error recovery with retry logic
- Sleep schedule (7 AM – 11 PM ET) for free-tier compliance
- Docker + Railway deployment config

**OUT (deprioritized):**
- Ollama semantic embeddings (no GPU on server; TF-IDF stays)
- Handshake/NUworks (SSO auth wall)
- Auto-Apply with Playwright (account ban risk)
- Per-Role Resume Matching
- Daily Digest Mode

---

## Implementation Order

Each phase produces a working system. Rollback is isolated per phase.

### Phase 1: Logging Overhaul

**Why first:** Every subsequent change benefits from proper logging.

**Create `logger_setup.py`** (new file):
- `setup_logging()` function
- Console handler: INFO level, human-readable format `"%(asctime)s [%(levelname)s] %(message)s"`
- File handler: `RotatingFileHandler("logs/job_alert.log", maxBytes=5MB, backupCount=3)`, DEBUG level
- Auto-create `logs/` directory

**Modify `main.py`** (~9 print statements → logging):
- Call `setup_logging()` at start of `main()`
- `logger = logging.getLogger(__name__)`
- Scan header, search combos, summary → `logger.info()`
- Per-job skip messages → `logger.debug()`

**Modify `scraper.py`** (~4 print statements → logging):
- Scraping errors → `logger.error()`
- Garbage/repost/outdated rejections → `logger.debug()`

**Modify `notifier.py`** (~3 print statements → logging):
- Alert sent → `logger.info()`
- Telegram API errors → `logger.error()`

---

### Phase 2: Secrets to Environment Variables

**Modify `config.py`:**
```python
import os
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "<current-value>")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "<current-value>")
DB_PATH = os.environ.get("DB_PATH", "jobs_seen.db")
```

**Create `.env.example`** (new file):
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DB_PATH=jobs_seen.db
```

Hardcoded values serve as fallbacks for local dev. On Railway, env vars are set via dashboard.

---

### Phase 3: Scan Interval + Sleep Schedule

**Modify `config.py`:**
- `CHECK_INTERVAL_MINUTES = 30`
- Add `ACTIVE_HOURS_START = 7` and `ACTIVE_HOURS_END = 23` (7 AM – 11 PM ET)

**Modify `main.py`:**
- Add `is_within_active_hours()` check before running scan
- During sleep hours: log "Outside active hours, sleeping until 7 AM" and skip
- This keeps Railway free tier usage at ~496 hours/month (under 500 limit)

`get_hours_since_midnight()` in scraper.py needs no change — it already works correctly with 30-min intervals.

---

### Phase 4: Sponsorship/Citizenship Filter (CORE FEATURE)

**Add to `scraper.py` — new function `check_sponsorship(description)`:**
- Returns `"warning"`, `"positive"`, or `None`
- **Negative signals** (→ ⚠️ tag): `"us citizen"`, `"u.s. citizen"`, `"permanent resident"`, `"green card"`, `"no sponsorship"`, `"not sponsor"`, `"without sponsorship"`, `"security clearance"`, `"us person"`, `"u.s. person"`, `"itar"`, `"authorized to work without"`
- **Positive signals** (→ ✅ tag): `"visa sponsorship available"`, `"will sponsor"`, `"international students welcome"` + regex `\bopt\b`, `\bcpt\b` for short tokens (avoids matching "OPTional", "OPTimize")
- Check positive signals FIRST (a posting saying "We will sponsor" that also mentions "US citizenship" is accessible to F1 students)
- If no description available → return `None` (can't check)

**Insert in `get_new_jobs()` pipeline** (after outdated season filter, before `is_strong_title_match`):
- Call `check_sponsorship(description)`
- Add `sponsorship_flag` to `job_data` dict

**No auto-rejection** — jobs still alert, just tagged.

---

### Phase 5: Null Date Tagging

**Modify `scraper.py` `get_new_jobs()`:**
- Track `date_verified = (date_posted is not None)` before the `is_posted_today()` check
- Add `date_verified` to `job_data` dict
- `is_posted_today()` behavior unchanged (still lets None dates through)

---

### Phase 6: Telegram Alert Format Update

**Modify `notifier.py` `send_telegram_alert()`:**
- Read `job_data.get("sponsorship_flag")` and `job_data.get("date_verified", True)`
- Build tags block:
  - `⚠️ May require US citizenship/clearance` (if sponsorship == "warning")
  - `✅ Visa sponsorship indicated` (if sponsorship == "positive")
  - `❓ Unverified posting date` (if date_verified == False)
- Insert tags between priority line and Apply link
- Keep existing message structure intact

---

### Phase 7: Error Recovery

**Modify `scraper.py` `fetch_jobs()`:**
- Retry loop: try once, on failure wait 30s, retry once more
- After 2 failures: log error, return `None`, move to next search combo
- Never crash the entire scan

**Modify `main.py` `run_scan()`:**
- Wrap the inner loop body (per search_term + location) in try/except
- On exception: log error, `continue` to next combo
- Wrap `send_telegram_alert()` call in try/except as additional safety net

---

### Phase 8: Docker + Railway Deployment

**New files (zero changes to existing code):**

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.11-slim, install deps, create logs dir, CMD python main.py |
| `docker-compose.yml` | Local testing: env vars from .env, volume for DB + logs, restart: unless-stopped |
| `railway.toml` | Railway config: Dockerfile builder, restart on failure |
| `.dockerignore` | Exclude jobs_seen.db, .env, logs/, __pycache__, .git |
| `.gitignore` | Exclude jobs_seen.db, .env, logs/, __pycache__ |
| `.env.example` | Template for required env vars |

**Update `requirements.txt`:** Add `requests` explicitly (used by notifier.py but not listed).

**Railway deployment steps** (for user):
1. Push code to GitHub
2. Connect repo to Railway
3. Set env vars in Railway dashboard (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_PATH=/data/jobs_seen.db)
4. Attach a persistent volume mounted at `/data`
5. Deploy — Railway builds from Dockerfile and auto-restarts on failure

---

## Files Modified / Created

| File | Action | Changes |
|------|--------|---------|
| `config.py` | Modify | Env vars, interval 30min, active hours config |
| `scraper.py` | Modify | `check_sponsorship()`, date_verified tracking, retry in `fetch_jobs()`, logging |
| `notifier.py` | Modify | Sponsorship/date tags in alert format, logging |
| `main.py` | Modify | Logging setup, sleep schedule, error wrapping, logging |
| `logger_setup.py` | **Create** | Logging configuration module |
| `Dockerfile` | **Create** | Docker image definition |
| `docker-compose.yml` | **Create** | Local Docker testing |
| `railway.toml` | **Create** | Railway deployment config |
| `.dockerignore` | **Create** | Docker build exclusions |
| `.gitignore` | **Create** | Git exclusions |
| `.env.example` | **Create** | Env var template |
| `requirements.txt` | Modify | Add `requests` |

**No database schema changes needed.** Sponsorship flag and date_verified are transient metadata passed through `job_data` — not persisted in DB.

---

## Key Existing Code to Reuse

- `scraper.py:is_strong_title_match()` — Pattern for keyword-in-description checks; sponsorship filter follows same style
- `scraper.py:is_total_garbage()` — Same lowered-string-in-list pattern
- `scraper.py:get_new_jobs()` — Pipeline structure where new filter slots in naturally
- `notifier.py:send_telegram_alert()` — Existing message template; tags append to it
- `config.py` — All new settings go here (active hours, etc.)

---

## Pitfalls to Watch

1. **OPT/CPT false positives** — Use `re.search(r'\bopt\b', text)` not `"opt" in text` (would match "OPTional")
2. **Telegram Markdown escaping** — Existing issue with special chars in company names; don't make it worse. Keep tags as plain emoji + text
3. **Retry sleep stacking** — Worst case 36 combos x 30s = 18min of retry delays. Unlikely but logged
4. **Railway volume** — Must attach volume at `/data` or DB resets on every redeploy

---

## Verification Plan

### Local Testing
1. Run `python main.py` — verify logging output appears in console AND `logs/job_alert.log`
2. Check a scan completes with no crashes
3. Verify Telegram alerts show sponsorship tags (⚠️/✅) and date tags (❓) correctly
4. Verify TF-IDF matching still works (no regression)
5. Simulate network failure — verify retry logic logs warning, retries, and continues

### Sponsorship Filter Testing
1. Create test job descriptions with known phrases ("must be US citizen", "we will sponsor OPT")
2. Run `check_sponsorship()` against them — verify correct return values
3. Verify "OPTional" does NOT trigger a false positive
4. Verify jobs with no description return `None` (no crash)

### Deployment Testing
1. `docker compose up` locally — verify bot runs in container
2. Check volume persistence: stop container, restart, verify jobs_seen.db retained
3. Verify sleep schedule: set active hours to a narrow window, confirm bot skips scans outside it
4. Push to Railway, set env vars, verify alerts arrive on Telegram

### Regression Checks
- Jobs processed per scan still ~66
- Alerts sent per scan still ~24 (may change slightly with sponsorship tags — that's fine, they're not filtered out)
- Dedup still works across boards
- 30-day cleanup still runs
- Existing filter pipeline (garbage, repost, outdated, title match) unchanged
