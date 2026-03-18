# SETUP_GUIDE.md — Instructions for Claude Code

> **This file is instructions for Claude Code, not a regular README.**
> When a user asks you to help set up this project, follow these sections in order.
> Ask questions ONE AT A TIME. Never skip ahead. Never assume — always ask and confirm.
> Execute commands on the user's behalf when possible. Explain what you're doing before doing it.

---

## 1. WELCOME

**EXPLAIN to the user:**

This is a Python job alert bot. Here's what it does:

- Scrapes **Indeed**, **LinkedIn**, and **Google Jobs** for intern/co-op positions (configurable roles and locations)
- Deduplicates jobs using an MD5 hash of `title|company` stored in a local SQLite database (`jobs_seen.db`)
- Filters out garbage titles (nursing, sales, accounting, etc.), reposts, and outdated seasonal listings
- Scores remaining jobs against the user's resume using **TF-IDF cosine similarity** (`scikit-learn`)
- Sends matching alerts to **Telegram** with match scores, priority location tags, and sponsorship/citizenship warnings
- Runs on a **30-minute schedule** during active hours (default: 7 AM – 11 PM local system time)
- Logs to both console (INFO) and rotating file at `logs/job_alert.log` (DEBUG, 5 MB x 3 backups)

The pipeline per scan: `main.run_scan()` iterates all search term + location combos → `scraper.get_new_jobs()` fetches and filters → `main.compute_match_score()` scores against resume → `notifier.send_telegram_alert()` sends to Telegram.

**ASK:**
- "Have you used this bot before, or is this a completely fresh setup?"
  - If fresh: proceed through all sections
  - If returning: ask what they want to change and skip to the relevant section

---

## 2. PREREQUISITES CHECK

**EXPLAIN:**
- Requires **Python 3.9+** (tested on 3.11). The `python-jobspy` scraper may have compatibility issues on older versions.
- **Docker** is optional — only needed for containerized local deployment or Railway.
- A **Telegram account** is required for receiving alerts.
- No GPU needed — scoring is TF-IDF (CPU-based via scikit-learn), not deep learning.
- Internet access is required at runtime (scrapes live job boards).

**DO — run these checks:**
```bash
python --version
pip --version
```

**ASK:**
- "Do you plan to run this **locally** (just `python main.py`), with **Docker** (`docker compose`), or deploy to **Railway** (cloud)?"
  - Store the answer — it determines which sections to emphasize later (Section 9).

**If Docker chosen, also run:**
```bash
docker --version
docker compose version
```

**WARNINGS:**
- If Python < 3.9: warn that `python-jobspy` may fail. Recommend upgrading.
- If on Windows: note that `datetime.now()` is used throughout (`main.py`, `scraper.py`) — active hours are based on the machine's **local system time**, not a specific timezone. The comment in `config.py` says "(ET)" but the code has no timezone handling.

---

## 3. ENVIRONMENT SETUP

**DO — execute these commands in order:**

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate it:
   - **Windows:** `venv\Scripts\activate`
   - **macOS/Linux:** `source venv/bin/activate`

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create the `.env` file:
   - **macOS/Linux:** `cp .env.example .env`
   - **Windows:** `copy .env.example .env`

**EXPLAIN:**
- `requirements.txt` installs 5 packages:
  - `python-jobspy` — job board scraper (Indeed, LinkedIn, Google)
  - `python-telegram-bot` — **listed but unused** by the actual code. `notifier.py` uses `requests` directly to call the Telegram API. This is a vestigial dependency (~15 MB). Harmless but unnecessary.
  - `schedule` — cron-like scheduler for the 30-minute scan loop
  - `scikit-learn` — TF-IDF vectorizer + cosine similarity for resume matching
  - `requests` — HTTP POST calls to Telegram Bot API
- The `.env` file holds 3 variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DB_PATH`. These override the hardcoded defaults in `config.py`.

**WARNING — CRITICAL SECURITY ISSUE:**
- `config.py` lines 5–6 contain **hardcoded fallback Telegram credentials**:
  ```python
  TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8633219125:AAELaaXsms_1iTY2E3i1-6FRffDWOQadnE4")
  TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8616520610")
  ```
  These are **real tokens** belonging to the original project owner. If the user runs the bot without setting `.env`, alerts go to the **wrong person**.
- Tell the user: "The `.env` file is in `.gitignore` so it won't be committed, but the fallback values in `config.py` are committed to git. After setup, we'll replace those fallback strings with empty strings so the bot fails loudly if `.env` is missing, rather than silently sending to someone else."

**DO NOT ask questions here — move to the next section.**

---

## 4. RESUME

**EXPLAIN:**
- The bot compares each job description against the contents of `resume.txt` (path set by `config.RESUME_PATH`, default: `"resume.txt"` in project root) using TF-IDF cosine similarity.
- The current `resume.txt` contains the **original project owner's resume** (Sanket Koli). The user must replace it with their own.
- The file must be **plain text** — not PDF, not DOCX. No special formatting needed. Just the raw text content of their resume.
- More content = better matching. Include skills, projects, work experience, coursework — anything with keywords relevant to target jobs.

**ASK:**
- "Paste your full resume text below, or give me the file path to a `.txt` file with your resume, and I'll copy it into `resume.txt`."

**DO:**
- Overwrite `resume.txt` with the user's content.

**WARNINGS:**
- If the resume is under 200 characters, warn: "This is very short for TF-IDF matching. The scorer works on keyword overlap — more content gives better results. Consider adding project descriptions, skills sections, or coursework."
- If the user provides a PDF path, suggest: "I can't read PDFs directly into plain text reliably. You can use an online converter or `pdftotext` to extract the text, then paste it here."

---

## 5. JOB PREFERENCES

**EXPLAIN:**
- All tunable settings live in `config.py`. Walk through each one and ask the user to confirm or change.

**ASK and DO — one at a time:**

### 5a. Search Terms (`config.py` → `SEARCH_TERMS`)

**Current defaults (12 terms):**
```python
SEARCH_TERMS = [
    "Data Analyst Intern", "Data Analyst Co-op",
    "Data Scientist Intern", "Data Scientist Co-op",
    "ML Engineer Intern", "Machine Learning Intern",
    "AI Engineer Intern", "AI Intern Co-op",
    "Data Engineer Intern", "Data Engineer Co-op",
    "Summer Data Analyst", "Summer Data Science",
]
```

**ASK:** "What job roles are you looking for? Here are the current 12 search terms. Want to keep them, remove any, or add new ones?"

**WARNING:** Each search term is queried against each location on each job board. Total queries per scan = `len(SEARCH_TERMS) * len(LOCATIONS)`. Currently 12 x 3 = 36 queries. Adding terms multiplies this — 20 terms x 5 locations = 100 queries, which can take 30+ minutes per scan and risk rate limiting.

**WARNING:** The title filter `is_intern_or_coop()` in `scraper.py` **requires** one of these keywords in the job title: `intern`, `co-op`, `coop`, `co op`, `summer`, `apprentice`, `trainee`. If the user wants **full-time roles**, this filter will block everything. They would need to modify `scraper.py:is_intern_or_coop()`.

**WARNING:** `is_total_garbage()` in `scraper.py` blocks titles containing: psychology, psychiatry, clinical, nursing, pharmacy, dental, veterinary, sales intern, marketing intern, graphic design, interior design, accounting intern, audit intern, tax intern, fleet operations, warehouse, quality control, investor relations, behavioral specialist, site planning intern. If the user's target roles overlap with these (unlikely for data/ML), the filter needs updating.

**WARNING:** `is_strong_title_match()` in `scraper.py` has a hardcoded list of 25 role keywords (data analyst, data scientist, machine learning, ml engineer, ai engineer, etc.). Jobs matching these get auto-alerted regardless of TF-IDF score. If the user targets different roles (e.g., "frontend developer"), this list won't help them — they'd need to update it.

### 5b. Locations (`config.py` → `LOCATIONS`)

**Current defaults:**
```python
LOCATIONS = [
    "Boston, MA",
    "Chicago, IL",
    "Remote",
]
```

**ASK:** "What locations do you want to search? Current: Boston, Chicago, Remote."

**IMPORTANT:** If the user changes locations, also ask: "Which of these locations should be tagged as PRIORITY in Telegram alerts?" Then update the priority check in `notifier.py` (the `if` condition that checks for `"boston"` or `"chicago"` in the location string). The current code:
```python
if "boston" in loc or "chicago" in loc:
    priority = "⭐ PRIORITY LOCATION"
```
Update this to match the user's priority cities (lowercase matching).

### 5c. Match Threshold (`config.py` → `MATCH_THRESHOLD`)

**Current default:** `0.25` (25%)

**EXPLAIN:** Jobs are alerted if ANY of these are true:
1. Strong title match (bypasses scoring entirely)
2. No description available (score = -1, alerts with "check manually" tag)
3. TF-IDF cosine similarity score >= `MATCH_THRESHOLD`

**ASK:** "The match threshold is 0.25 (25%). Lower = more alerts but more noise. Higher = fewer but more relevant. Want to adjust? (0.15–0.35 is the useful range)"

### 5d. Scan Interval (`config.py` → `CHECK_INTERVAL_MINUTES`)

**Current default:** `30` minutes

**ASK:** "The bot scans every 30 minutes. Want to change this? (15–60 minutes is reasonable)"

**WARNING:** The scraper has built-in retry logic — 2 attempts with 30-second sleep between failures (`scraper.py:fetch_jobs()`). With 36 queries and worst-case failures, a single scan could take 36 minutes. Setting the interval below 30 minutes could cause overlapping scans.

### 5e. Active Hours (`config.py` → `ACTIVE_HOURS_START`, `ACTIVE_HOURS_END`)

**Current defaults:** `ACTIVE_HOURS_START = 7`, `ACTIVE_HOURS_END = 23`

**EXPLAIN:** The bot only scans between these hours. Outside this window, `run_scan()` returns immediately. This saves resources (important for Railway's free tier: 16 hours/day = ~496 hours/month, under the 500-hour limit).

**IMPORTANT:** These use `datetime.now().hour` — your **system's local time**, not any specific timezone. If deployed to a cloud server in UTC, "7 AM" means 7 AM UTC (= 2 AM ET). Adjust accordingly, or set the `TZ` environment variable on the server (e.g., `TZ=America/New_York`).

**ASK:** "Active hours are 7 AM to 11 PM (local system time). Want to adjust?"

### 5f. Job Boards (`config.py` → `SITES` vs `scraper.py` → `SITES`)

**EXPLAIN — this is a known quirk:**
- `config.py` defines: `SITES = ["indeed", "linkedin", "zip_recruiter", "google"]`
- But `scraper.py` line 13 **overrides** this with: `SITES = ["indeed", "linkedin", "google"]`
- ZipRecruiter is **excluded** because it returns 502 errors consistently.
- The scraper uses its own `SITES` variable, NOT the one from config. The config value is effectively dead code.

**ASK:** "Job boards: Indeed, LinkedIn, and Google are active. ZipRecruiter is disabled due to errors. Want to keep this as-is?" (If they want to re-enable ZipRecruiter, warn about the 502 errors.)

### 5g. HOURS_OLD (`config.py` → `HOURS_OLD`)

**EXPLAIN — this value is unused:**
- `config.py` defines `HOURS_OLD = 24`, but the scraper **never imports or uses it**.
- Instead, `scraper.py:fetch_jobs()` calls `get_hours_since_midnight()` which dynamically calculates hours since midnight.
- No action needed. Mentioning for transparency only.

**DO:** After all preferences are confirmed, edit `config.py` with the user's values. If locations changed, also edit `notifier.py`'s priority location check.

---

## 6. TELEGRAM SETUP

**EXPLAIN:**
- The bot sends alerts via Telegram's Bot API using raw HTTP POST requests. `notifier.py` calls `requests.post()` to `https://api.telegram.org/bot{TOKEN}/sendMessage` with Markdown formatting.
- Two values are needed: a **Bot Token** (from BotFather) and a **Chat ID** (your personal chat with the bot).

**GUIDE — step by step, ask the user to confirm each:**

### Step 6a: Create the bot
**TELL the user:**
1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow the prompts — choose a name and username for your bot
4. BotFather will reply with a token like `123456789:ABCdefGhIjKlMnOpQrStUvWxYz`

**ASK:** "Paste your bot token here."

### Step 6b: Get the Chat ID
**TELL the user:**
1. Open your new bot in Telegram and send it any message (e.g., `/start` or "hello")
2. Then open this URL in your browser (replace `<YOUR_TOKEN>` with your actual token):
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. In the JSON response, look for `"chat":{"id":XXXXXXXXXX}` — that number is your Chat ID.

**Alternative method:** Search for `@userinfobot` on Telegram, send it `/start`, and it will reply with your numeric user ID. This is the same as your Chat ID for personal messages.

**ASK:** "Paste your Chat ID here."

### Step 6c: Save credentials
**DO:**
1. Write the token and chat ID into `.env`:
   ```
   TELEGRAM_BOT_TOKEN=<user's token>
   TELEGRAM_CHAT_ID=<user's chat id>
   ```
2. Replace the hardcoded fallbacks in `config.py` lines 5–6. Change to:
   ```python
   TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
   TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
   ```
   This ensures the bot fails loudly if `.env` is missing, rather than silently sending to the original owner.

### Step 6d: Test the connection
**DO — run this test:**
```bash
python -c "
import requests
token = '<USER_TOKEN>'
chat_id = '<USER_CHAT_ID>'
url = f'https://api.telegram.org/bot{token}/sendMessage'
resp = requests.post(url, json={'chat_id': chat_id, 'text': 'Job Alert Bot setup test - if you see this, Telegram is working!'})
print(resp.status_code, resp.json())
"
```

**CHECK:**
- Status 200 + user confirms they received the message in Telegram = success.
- Status 401 = token is wrong. Re-check with BotFather.
- Status 400 "chat not found" = Chat ID is wrong, or the user hasn't messaged the bot yet. Have them send `/start` to the bot first, then retry.

---

## 7. ALL OTHER ENV VARIABLES

**EXPLAIN:**
- The `.env` file has 3 variables. Two are done (Telegram). The third:

### `DB_PATH`
- **Default:** `jobs_seen.db` (relative to project root)
- **What it does:** Path to the SQLite database that stores seen job hashes, preventing duplicate alerts.
- **For local runs:** Keep the default `jobs_seen.db`.
- **For Docker:** Set to `/data/jobs_seen.db` — the `docker-compose.yml` mounts a named volume `job_data` at `/data` so the DB persists across container restarts.
- **For Railway:** Set to `/data/jobs_seen.db` — requires attaching a persistent volume at `/data` in Railway's dashboard.

**DO:** Set the appropriate value in `.env`.

**WARNING — existing database:**
- A `jobs_seen.db` file (487 KB) already exists in the repo from the original owner's runs. It contains their job history.
- **For a fresh start:** Delete it before the first run. The bot auto-creates a new one via `scraper.init_db()`.
  ```bash
  rm jobs_seen.db   # or: del jobs_seen.db (Windows)
  ```
- The DB file is in `.gitignore`, but this copy was committed before the ignore rule existed. It will persist in git history.

**DO:** Verify the final `.env` file. Read it back and confirm all 3 variables are populated:
```
TELEGRAM_BOT_TOKEN=<set>
TELEGRAM_CHAT_ID=<set>
DB_PATH=<set>
```

---

## 8. LOCAL TEST

### Pre-flight checks
**DO — verify these before running:**
1. `.env` exists and has all 3 variables populated (non-empty)
2. `resume.txt` has been updated with the user's resume (not the original owner's)
3. `config.py` has the user's preferred search terms, locations, and threshold
4. Virtual environment is activated (`which python` should point to `venv/`)
5. Old `jobs_seen.db` has been deleted (for fresh start)

### Run the bot
**DO:**
```bash
python main.py
```

### Expected output
**EXPLAIN:** You should see something like:
```
YYYY-MM-DD HH:MM:SS [INFO] ============================================================
YYYY-MM-DD HH:MM:SS [INFO] Job Alert System v4.0 — Intern/Co-op Edition
YYYY-MM-DD HH:MM:SS [INFO] ============================================================
YYYY-MM-DD HH:MM:SS [INFO]   Date: <today's date>
YYYY-MM-DD HH:MM:SS [INFO]   Freshness: ONLY today's jobs (reposts blocked)
YYYY-MM-DD HH:MM:SS [INFO]   Checking every 30 min
YYYY-MM-DD HH:MM:SS [INFO]   Active hours: 7:00 - 23:00
YYYY-MM-DD HH:MM:SS [INFO]   Roles: 12 search terms
YYYY-MM-DD HH:MM:SS [INFO]   Locations: Boston, MA | Chicago, IL | Remote
YYYY-MM-DD HH:MM:SS [INFO]   Sponsorship filter: ENABLED
YYYY-MM-DD HH:MM:SS [INFO] ============================================================
YYYY-MM-DD HH:MM:SS [INFO] Scanning at HH:MM ...
YYYY-MM-DD HH:MM:SS [INFO] 'Data Analyst Intern' in 'Boston, MA'...
```

Then scanning proceeds through all search term + location combos. Each combo logs results. At the end:
```
YYYY-MM-DD HH:MM:SS [INFO] Done: X relevant intern/co-op jobs found, Y alerts sent, Z skipped (below threshold)
```

### Watch for Telegram messages
- Alerts should start arriving as jobs are found and scored.
- The bot sleeps 1 second between sends (`main.py` line 100) to avoid Telegram rate limits.

### Stop the bot
- Press **Ctrl+C**. The bot runs in an infinite `while True` loop (`main.py` lines 142–144).

### Common Errors and Fixes

**Error 1: "Outside active hours. Skipping scan."**
- Cause: Running outside the `ACTIVE_HOURS_START` (7) to `ACTIVE_HOURS_END` (23) window.
- Fix: Temporarily set `ACTIVE_HOURS_START = 0` and `ACTIVE_HOURS_END = 24` in `config.py` for testing.

**Error 2: `ModuleNotFoundError: No module named 'jobspy'`**
- Cause: Dependencies not installed or venv not activated.
- Fix: Activate venv and run `pip install -r requirements.txt`.

**Error 3: `FileNotFoundError: [Errno 2] No such file or directory: 'resume.txt'`**
- Cause: `resume.txt` is missing.
- Fix: Create the file with the user's resume content.

**Error 4: `Telegram 401 Unauthorized`**
- Cause: Bot token is wrong.
- Fix: Re-check the token from BotFather. Verify `.env` is being read (not falling back to config.py defaults).

**Error 5: `Telegram 400 Bad Request: chat not found`**
- Cause: Chat ID is wrong, or user hasn't sent a message to the bot yet.
- Fix: Open the bot in Telegram, send `/start`, then re-verify the Chat ID.

**Error 6: `Scraping failed for '...' (attempt 1/2): ...`**
- Cause: Network issue or job board rate limiting/blocking.
- Info: The bot retries once after 30 seconds (`scraper.py:fetch_jobs()`). If both attempts fail, it logs an error and moves to the next search combo. This is expected behavior — not a crash bug.

**Error 7: Scan completes but 0 alerts sent**
- Cause: All jobs filtered out, or scoring threshold too high, or no new jobs posted today.
- Fix: Check the "Done" summary line. If jobs were found but all skipped, try lowering `MATCH_THRESHOLD` to 0.15. Also check if running on a weekend/holiday when fewer jobs are posted.

**Error 8: "Done: 0 relevant intern/co-op jobs found"**
- Cause: Aggressive filter pipeline. Could be `is_intern_or_coop()` rejecting titles, `is_posted_today()` rejecting non-today posts, or `is_total_garbage()` catching false positives.
- Fix: Check `logs/job_alert.log` at DEBUG level for per-job filter decisions.

---

## 9. DEPLOYMENT

### 9a. Docker Compose (Local Persistent)

**EXPLAIN:**
- `docker-compose.yml` defines a single service `job-alert` that builds from the `Dockerfile`.
- The Dockerfile uses `python:3.11-slim`, copies everything, creates `logs/`, and runs `python main.py`.
- A named volume `job_data` is mounted at `/data` inside the container for database persistence.
- Logs are mounted at `./logs:/app/logs` so they're accessible on the host.
- `restart: unless-stopped` means auto-restart on crash, but not on manual `docker compose stop`.

**DO:**
1. Verify `.env` has all 3 variables (Docker Compose reads `.env` automatically from the same directory).
2. Make sure `DB_PATH=/data/jobs_seen.db` in `.env` (not the default `jobs_seen.db`).
3. Build and start:
```bash
docker compose up -d
```
4. Check logs:
```bash
docker compose logs -f job-alert
```
5. Verify Telegram alerts are arriving.

**To stop:**
```bash
docker compose stop
```

**To rebuild (e.g., after changing resume.txt or code):**
```bash
docker compose build && docker compose up -d
```

**WARNING:** `.dockerignore` excludes `.env`, `jobs_seen.db`, `logs/`, `.git/`, `.claude/`, and all `*.md` files. But `resume.txt` IS copied into the image. If the user updates their resume, they must rebuild the image.

### 9b. Railway (Cloud)

**EXPLAIN:**
- Railway is a cloud platform with a free tier (500 hours/month). The bot's sleep schedule (16 hours/day active = ~496 hours/month) fits within this limit.
- `railway.toml` configures: Dockerfile builder, `python main.py` as start command, restart on failure (max 10 retries).
- Auto-deploy: pushing to GitHub triggers a new deployment.

**GUIDE — step by step:**

1. **Create Railway account:**
   - Go to https://railway.app
   - Login with GitHub, authorize Railway.

2. **Create project from GitHub repo:**
   - Dashboard → "New Project" → "Deploy from GitHub Repo"
   - Select the repo. Railway auto-detects the Dockerfile and builds.

3. **Set environment variables** (Railway dashboard → service → Variables tab):
   ```
   TELEGRAM_BOT_TOKEN = <user's token>
   TELEGRAM_CHAT_ID   = <user's chat id>
   DB_PATH            = /data/jobs_seen.db
   ```

4. **Add a persistent volume** (Railway dashboard → service → Volumes tab):
   - Mount path: `/data`
   - Name: `job-data`

5. **Verify:**
   - Deployments tab → click latest deployment → check logs
   - Should see the "Job Alert System v4.0" startup banner
   - Telegram alerts should start arriving

**WARNINGS:**
- **Without a volume at `/data`, the SQLite database resets on every deploy.** This means full re-alerting of all jobs after each push. Always attach the volume.
- If Railway requires a credit card, alternatives: **Render.com** (free background worker) or **local Docker** (always free).
- `DEPLOY_INSTRUCTIONS.txt` in the repo contains the original owner's Telegram credentials as example values. The user should use their own.
- To set timezone on Railway, add env var: `TZ=America/New_York` (or their timezone). Without this, active hours use UTC.

---

## 10. FINAL VERIFICATION

**DO — present this checklist to the user:**
```
Setup Checklist:
[ ] Python 3.9+ installed
[ ] Virtual environment created and activated
[ ] Dependencies installed (pip install -r requirements.txt)
[ ] .env file created with TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_PATH
[ ] config.py fallback credentials replaced with empty strings (lines 5-6)
[ ] resume.txt updated with your resume
[ ] config.py search terms and locations customized
[ ] notifier.py priority location check updated (if locations changed)
[ ] Telegram bot created and test message received
[ ] Old jobs_seen.db deleted (fresh start)
[ ] python main.py ran successfully
[ ] Telegram alerts received
[ ] (If Docker) docker compose up -d running
[ ] (If Railway) Deployed with volume attached
```

**EXPLAIN — tips for ongoing use:**

- **Logs:** `logs/job_alert.log` has DEBUG-level detail (every filter decision per job). Console shows INFO-level summaries. Log files rotate at 5 MB with 3 backups.
- **In-memory dedup:** `scraper._scan_seen` (a module-level `set()`) prevents cross-query duplicates within a single scan cycle. It resets at the start of each `run_scan()` via `reset_scan_tracker()`. This is separate from the SQLite dedup which persists across cycles.
- **DB auto-cleanup:** Jobs older than 30 days are automatically deleted via `cleanup_old_jobs(30)` called at the start of each scan.
- **Never delete `jobs_seen.db` while the bot is running.** It's the dedup memory. The longer it runs, the fewer duplicate alerts you get.
- **Updating preferences:** Edit `config.py` and restart the bot. For Docker: rebuild with `docker compose build && docker compose up -d`. For Railway: push to GitHub (auto-deploys).
- **Updating resume:** Edit `resume.txt` and restart. For Docker: must rebuild the image (resume is baked in at build time via `COPY . .`).

---

## 11. TROUBLESHOOTING

These are real issues derived from the actual code, not generic advice.

### `python-telegram-bot` in requirements.txt but unused
- **What:** `requirements.txt` lists `python-telegram-bot`, but `notifier.py` imports only `requests` and calls the Telegram API directly via `requests.post()`. The package is never imported anywhere.
- **Impact:** None — it installs harmlessly but adds ~15 MB of unused code.
- **Fix (optional):** Remove `python-telegram-bot` from `requirements.txt`.

### ZipRecruiter is dead code
- **What:** `config.py` lists `"zip_recruiter"` in `SITES`, but `scraper.py` line 13 defines its own `SITES = ["indeed", "linkedin", "google"]`, completely ignoring the config. ZipRecruiter was removed due to persistent 502 errors.
- **Impact:** None. The config value is never read by the scraper.
- **Fix (optional):** Remove `"zip_recruiter"` from `config.SITES` to avoid confusion.

### Alerts going to the wrong person
- **What:** If `.env` is missing or has empty/unset Telegram variables, `os.environ.get()` falls through to the hardcoded defaults in `config.py` — the **original owner's** bot token and chat ID.
- **Fix:** Always verify `.env` is populated. Replace the hardcoded fallbacks in `config.py` with empty strings (done in Section 6c).

### "Outside active hours" on a cloud server
- **What:** `is_within_active_hours()` in `main.py` uses `datetime.now().hour`. On a cloud server in UTC, "7 AM" means 7 AM UTC, not 7 AM in the user's timezone.
- **Fix:** Either adjust `ACTIVE_HOURS_START`/`ACTIVE_HOURS_END` to UTC equivalents, or set the `TZ` environment variable (e.g., `TZ=America/New_York`) on the server.

### Same jobs appearing repeatedly
- **What:** `is_posted_today()` in `scraper.py` returns `True` when `date_posted` is `None` (benefit of the doubt). Some boards consistently return `None` dates. These jobs pass the date filter every scan BUT are still deduplicated by the SQLite hash check (`is_new_job()`). If the user sees genuine repeats, the hash might differ between scrapes (e.g., company name has trailing whitespace on some runs).
- **Fix:** Check `logs/job_alert.log` at DEBUG level for the specific job's hash values.

### Very few or no alerts despite many jobs existing
- **What:** The filter pipeline is intentionally aggressive. Five sequential filters must pass:
  1. `is_intern_or_coop()` — title must contain: intern, co-op, coop, co op, summer, apprentice, trainee
  2. `is_total_garbage()` — title must NOT contain: nursing, sales, accounting, etc. (22 blocked keywords)
  3. `is_posted_today()` — job must be posted today (based on `date.today()`)
  4. `is_outdated_season()` — title must NOT contain a year earlier than the current year
  5. After filters, `compute_match_score()` must return >= `MATCH_THRESHOLD` (0.25), unless strong title match or missing description
- **Fix:** Lower `MATCH_THRESHOLD`, broaden search terms, or check if filters are catching false positives. Run on a weekday — fewer jobs are posted on weekends.

### `sqlite3.OperationalError: database is locked`
- **What:** SQLite connections are opened/closed per operation in `scraper.py` (no connection pooling). This is fine for single-threaded use, but breaks if two bot instances run simultaneously.
- **Fix:** Ensure only one instance of `main.py` runs at a time.

### Scan takes extremely long
- **What:** Total scan time = `(search terms) * (locations) * (time per query)`. With 12 terms x 3 locations = 36 queries across 3 job boards. On failure, retry waits 30 seconds. Worst case (all failures): 36 queries x 2 attempts x 30s wait = 36 minutes.
- **Fix:** Reduce search terms or locations. Or accept the wait — the scheduler handles overlap gracefully.

### Telegram messages have broken formatting
- **What:** `notifier.py` sends messages with `parse_mode: "Markdown"`. If a job title or company name contains Markdown special characters (`*`, `_`, `` ` ``, `[`, `]`), the message may fail to send or render incorrectly. The code does not escape these characters.
- **Fix:** Add Markdown escaping in `notifier.py` before constructing the message, or switch `parse_mode` to `"HTML"`.

### Sponsorship detection false positives
- **What:** `check_sponsorship()` in `scraper.py` does case-insensitive substring matching. It checks positive signals first (e.g., "will sponsor visa"), then negative signals (e.g., "no sponsorship"). A job that says both "We sponsor visas" AND "Must be a US citizen" will be tagged as **positive** (because positive is checked first).
- **Impact:** The sponsorship flag is an annotation only — it never blocks a job from being alerted. But the tag in the Telegram message could be misleading.
- **Fix:** If important, refactor `check_sponsorship()` to weigh negative signals more heavily, or return both flags.
