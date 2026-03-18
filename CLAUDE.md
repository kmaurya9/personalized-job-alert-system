# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Python job alert bot that scrapes Indeed, LinkedIn, and Google for intern/co-op positions, scores them against a resume using TF-IDF cosine similarity, and sends alerts via Telegram. Runs on a 30-minute schedule during active hours (7 AM–11 PM).

## Commands

```bash
# Run locally
python main.py

# Run with Docker
docker compose up -d

# Install dependencies
pip install -r requirements.txt
```

No test suite exists. No linter is configured.

## Architecture

**Pipeline flow:** `main.run_scan()` → iterates all search term + location combos → `scraper.get_new_jobs()` fetches and filters → `main.compute_match_score()` scores against resume → `notifier.send_telegram_alert()` sends to Telegram.

**Filtering chain in `scraper.get_new_jobs()`** (order matters):
1. Dedup via MD5 hash of `title|company` checked against SQLite + in-memory scan set
2. Must contain intern/co-op keywords in title
3. Garbage title filter (irrelevant fields like nursing, sales, accounting)
4. Must be posted today (anti-repost)
5. Outdated season filter (e.g., "Summer 2025" when it's 2026)
6. Sponsorship/citizenship annotation (not a rejection — just tags the alert)

**Scoring in `main.py`:** TF-IDF vectorizer on `resume.txt` + job description → cosine similarity. Jobs alert if: strong title match, missing description, or score >= `MATCH_THRESHOLD` (0.25).

**Key modules:**
- `config.py` — All tunable settings: search terms, locations, thresholds, active hours, DB path. Telegram creds fall back to hardcoded defaults if env vars missing.
- `scraper.py` — python-jobspy wrapper, SQLite dedup layer, all filtering logic, sponsorship detection via regex/phrase matching.
- `notifier.py` — Formats and sends Telegram messages with priority location tags, match score indicators, and sponsorship/date warnings.
- `logger_setup.py` — Rotating file handler (5 MB × 3 backups at `logs/job_alert.log`) + console at INFO level.

## Environment

Requires a `.env` file (see `.env.example`):
- `TELEGRAM_BOT_TOKEN` — Telegram Bot API token
- `TELEGRAM_CHAT_ID` — Target chat ID
- `DB_PATH` — SQLite database path (defaults to `jobs_seen.db`)

## Deployment

Configured for Railway (`railway.toml`) with Dockerfile. See `DEPLOY_INSTRUCTIONS.txt` for step-by-step Railway setup. Docker Compose available for local persistent runs with a named volume for the database.

## Gotchas

- `config.py` has hardcoded fallback Telegram credentials — env vars override them but the defaults are real tokens.
- ZipRecruiter is listed in `config.SITES` but overridden to be excluded in `scraper.py` (line 13) due to 502 errors.
- `_scan_seen` in `scraper.py` is a module-level set that prevents cross-query duplicates within a single scan cycle — reset at the start of each `run_scan()`.
- SQLite connections are opened/closed per operation (no connection pooling) — fine for this single-threaded use case.
- `jobs_seen.db` is in `.gitignore` but a copy exists in the repo from before it was ignored.
