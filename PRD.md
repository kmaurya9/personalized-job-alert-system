Here's a clean PRD formatted for Claude Code. I've restructured it to be actionable — separating what exists today from what needs to be built, with clear acceptance criteria.

---

# Product Requirements Document: Job Alert System v4.0

## 1. Product Summary

**Product:** Automated job monitoring system for Data/ML/AI intern and co-op positions.

**Owner:** Sanket Koli

**Current Version:** v3.1 (stable, running in production since March 11, 2026)

**What it does:** Scrapes LinkedIn, Indeed, and Google Jobs on a 60-minute polling cycle. Filters for relevant intern/co-op roles, deduplicates across boards, detects reposts and outdated listings, scores remaining jobs against a resume using TF-IDF, and delivers real-time alerts via Telegram.

**Core value proposition:** Apply within hours of posting, not days. Research shows early applicants receive significantly more callbacks and OA invitations.

---

## 2. Current Architecture

```
Job Boards (LinkedIn, Indeed, Google)
        │
        ▼
   Scraper (python-jobspy)
        │
        ▼
   Dedup + Storage (SQLite - jobs_seen.db)
        │
        ▼
   Filter Pipeline (7 stages, executed in order):
        1. is_new_job()           → DB + in-memory scan check
        2. is_intern_or_coop()    → title keyword gate
        3. is_total_garbage()     → irrelevant field rejection
        4. is_posted_today()      → date verification (anti-repost)
        5. is_outdated_season()   → year check in title (e.g. "Summer 2025" in 2026)
        6. is_strong_title_match()→ role keyword match → auto-alert
        7. compute_match_score()  → TF-IDF fallback → alert if ≥ 25%
        │
        ▼
   Telegram Notifier (Bot API)
```

### File Structure
```
job-alert/
├── config.py          # Settings: tokens, roles, locations, thresholds
├── scraper.py         # Scraping, dedup, filtering, DB operations
├── notifier.py        # Telegram alert formatting and delivery
├── main.py            # Orchestrator: scheduling, matching, scan loop
├── requirements.txt   # Dependencies
├── resume.txt         # Plain text resume for matching
└── jobs_seen.db       # SQLite DB (auto-created, persistent — never delete)
```

### Tech Stack
- **Scraping:** `python-jobspy` (LinkedIn, Indeed, Google)
- **Database:** SQLite
- **Matching:** TF-IDF + Cosine Similarity via `scikit-learn`
- **Alerts:** Telegram Bot API
- **Scheduling:** `schedule` library (60-min polling)
- **Language:** Python 3.x

---

## 3. Current Configuration (`config.py`)

| Setting | Default | Notes |
|---|---|---|
| `SEARCH_TERMS` | 12 terms | Role + type combos (e.g. "Data Analyst Intern") |
| `LOCATIONS` | Boston, Chicago, Remote | Priority cities + remote |
| `SITES` | indeed, linkedin, google | Active boards |
| `HOURS_OLD` | 24 | Fallback max age for scraper query |
| `MATCH_THRESHOLD` | 0.25 | Min TF-IDF score for weak-title jobs |
| `CHECK_INTERVAL_MINUTES` | 60 | Scan frequency |
| `DB_PATH` | jobs_seen.db | SQLite path |
| `RESUME_PATH` | resume.txt | Plain text resume |

---

## 4. Known Limitations (v3.1)

These are problems that currently exist and should be considered when building new features:

1. **LinkedIn repost blind spot:** If LinkedIn marks a repost with today's date and the system has never seen it, it alerts once. No API exposes repost status. The DB prevents re-alerting on subsequent scans.
2. **Null date_posted:** Some jobs return `None` for date. System currently gives benefit of the doubt and lets them through.
3. **TF-IDF matching is shallow:** Keyword-based matching misses semantic similarity. A job description about "building predictive models" won't match well against a resume that says "machine learning pipelines" even though they're conceptually identical.
4. **No Northeastern-specific boards:** Handshake and NUworks are not scraped.
5. **Single resume matching:** Same resume is compared against all role types, even though different roles (data analyst vs ML engineer) warrant different emphasis.
6. **No error recovery:** If a scan fails mid-way (network error, API rate limit), there's no retry logic or partial recovery.
7. **No observability:** No logging framework, no metrics beyond print statements, no way to audit historical scan performance.

---

## 5. Planned Improvements (v4.0 Scope)

Below are the features to implement, ordered by priority. Each feature is independent — implement them incrementally, not all at once.

---

### 5.1 — Replace TF-IDF with Local Semantic Embeddings

**Priority:** High

**Why:** TF-IDF misses synonyms and conceptual similarity. Semantic embeddings will dramatically improve matching for vague job titles and descriptions that use different vocabulary than the resume.

**Requirements:**
- Use Ollama with a local embedding model (the machine has an RTX 4050 GPU available)
- Replace `compute_match_score()` in `scraper.py` with an embedding-based cosine similarity function
- Keep the same threshold interface (`MATCH_THRESHOLD` in config), but the threshold value will likely need retuning
- Fall back gracefully to TF-IDF if Ollama is not running or unavailable
- Embedding computation should not block the scan loop — if a single embedding call takes too long, skip and use TF-IDF for that job

**Acceptance Criteria:**
- Running `main.py` with Ollama active uses semantic embeddings for matching
- Running `main.py` without Ollama falls back to TF-IDF silently (no crash)
- Telegram alerts still show match percentage and match type indicator
- Matching latency per job stays under 2 seconds on RTX 4050

---

### 5.2 — Handshake / NUworks Integration

**Priority:** High

**Why:** Northeastern-specific job boards have exclusive postings not found on LinkedIn/Indeed/Google. These are high-signal, low-competition opportunities.

**Requirements:**
- Research and implement scraping or API access for Handshake and NUworks
- These may require authentication (university SSO). If direct scraping is infeasible, document why and propose alternatives (e.g. email parsing, RSS feeds, browser automation)
- Integrate discovered jobs into the same filter pipeline — no separate path
- Add `handshake` and `nuworks` as options in `config.py` `SITES` list
- Deduplication must work across these new sources and existing ones (same `hash(title + company)` logic)

**Acceptance Criteria:**
- Jobs from Handshake/NUworks appear in Telegram alerts with correct source attribution
- Dedup works across all 5 sources
- If auth is required, credentials are stored securely (env vars, not hardcoded)

---

### 5.3 — Auto-Apply Pipeline (Playwright)

**Priority:** Medium

**Why:** Reduces the time from alert to application from minutes to seconds. Even a partial auto-fill (name, email, resume upload) saves significant effort.

**Requirements:**
- Use Playwright for browser automation
- Start with "Easy Apply" flows on LinkedIn and Indeed only
- The system should pre-fill standard fields (name, email, phone, resume upload, university, graduation date) from a profile config
- **Never auto-submit.** Pause at the final confirmation step and alert via Telegram with a screenshot or summary of what was filled, plus a "review and submit" link
- If the application flow is non-standard or has unexpected fields, abort and send a normal alert instead (graceful degradation)
- Add an `AUTO_APPLY_ENABLED` flag in config (default: `False`)
- Log every auto-apply attempt with timestamp, job, company, and outcome (filled/aborted/error)

**Acceptance Criteria:**
- With `AUTO_APPLY_ENABLED=True`, LinkedIn Easy Apply jobs get pre-filled and paused before submission
- User receives Telegram notification with apply status
- Non-standard flows fall back to regular alert with no crash
- All attempts are logged

---

### 5.4 — Daily Digest Mode

**Priority:** Medium

**Why:** Real-time pings are valuable during active job hunting, but sometimes a single morning summary is less disruptive and easier to review.

**Requirements:**
- Add `ALERT_MODE` config option with values: `realtime` (current behavior) or `digest`
- In digest mode, accumulate all passing jobs during the day and send a single formatted Telegram message at a configurable time (default: 8:00 AM ET)
- Digest message should be organized by match quality (strong title matches first, then by descending score)
- Include a count summary at the top (e.g. "12 new jobs found yesterday")
- Each job in the digest should still have its apply link
- If zero jobs found, send a short "No new jobs found" message (so the user knows the system is alive)

**Acceptance Criteria:**
- `ALERT_MODE=digest` suppresses real-time alerts and sends one daily message
- `ALERT_MODE=realtime` works exactly as it does now (no regression)
- Digest arrives at the configured time
- Digest is readable on mobile (no excessively long messages — paginate if >20 jobs)

---

### 5.5 — Per-Role Resume Matching

**Priority:** Low

**Why:** A data analyst resume emphasizes SQL and dashboards. An ML engineer resume emphasizes PyTorch and model training. Using one resume for all roles dilutes match quality.

**Requirements:**
- Support multiple resume files in a `resumes/` directory, each mapped to role categories in config
- Example config structure:
  ```python
  RESUME_MAP = {
      "data_analyst": "resumes/resume_da.txt",
      "ml_engineer": "resumes/resume_ml.txt",
      "data_scientist": "resumes/resume_ds.txt",
      "default": "resumes/resume_general.txt"
  }
  ```
- Role categorization should be derived from the job title (reuse `is_strong_title_match()` logic)
- If no category matches, use `default`
- Telegram alert should indicate which resume variant was used for matching

**Acceptance Criteria:**
- Jobs matching "data analyst" titles are scored against `resume_da.txt`
- Jobs matching "ML engineer" titles are scored against `resume_ml.txt`
- Unmatched titles fall back to `resume_general.txt`
- System works fine with a single resume file (backward compatible)

---

## 6. Non-Functional Requirements (Apply to All Features)

**Error Handling:**
- No feature should crash the main scan loop. All new code must be wrapped in try/except with meaningful error logging.
- If a new feature fails (Ollama down, Playwright timeout, Handshake auth expired), the system should degrade to v3.1 behavior, not stop running.

**Logging:**
- Replace all `print()` statements with Python's `logging` module.
- Use levels appropriately: `DEBUG` for per-job filter decisions, `INFO` for scan summaries, `WARNING` for recoverable failures, `ERROR` for things that need attention.
- Log to both console and a rotating file (`logs/job_alert.log`).

**Configuration:**
- All new settings go in `config.py`.
- Sensitive values (API tokens, passwords) should be read from environment variables, not hardcoded.

**Database:**
- `jobs_seen.db` is sacred. Never drop tables or change schemas in a way that breaks existing data.
- Any schema changes must use `ALTER TABLE` migrations, not recreation.
- The 30-day cleanup (`cleanup_old_jobs(30)`) must continue working.

**Testing:**
- Each new feature should include at least basic unit tests (pytest).
- Filter pipeline tests: given a mock job dict, verify each filter produces correct pass/fail.
- Matching tests: given a known resume and job description, verify score is in expected range.

---

## 7. Current Performance Baseline (v3.1, March 11, 2026)

| Metric | Value |
|---|---|
| Jobs processed per scan | ~66 |
| Alerts sent per scan | ~24 |
| Reposts caught per scan | ~40+ |
| Garbage blocked per scan | ~20+ |
| Cross-board duplicates prevented | ~35+ |
| Scan cycle time | ~60 min interval |

Use these as regression benchmarks. New features should not significantly degrade scan throughput or increase false negatives.

---

## 8. How to Run the Current System

```bash
pip install python-jobspy schedule scikit-learn requests
cd job-alert
python main.py
```

**Critical:** Never delete `jobs_seen.db`. It is the system's memory. The longer it runs, the better its dedup and repost detection becomes.

---

That should give Claude Code everything it needs — the full picture of what exists, what's broken, what to build, and what not to break. You can paste this directly or feed it as a file. If you want, I can also break out any single feature (like the Ollama embedding one) into its own standalone task spec for a more focused coding session.