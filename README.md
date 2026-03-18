# Job Alert Bot

A Python bot that scrapes **Indeed**, **LinkedIn**, and **Google Jobs** for intern/co-op positions, scores them against your resume using TF-IDF cosine similarity, and sends matching alerts to **Telegram** — all automatically, every 30 minutes.

## What You Get

- Telegram alerts like this:
  ```
  🚨 NEW JOB ALERT

  Software Engineer Intern
  🏢 Stripe
  📍 New York, NY
  🌐 LinkedIn
  🟢 Match: 72%
  ⭐ PRIORITY LOCATION
  ✅ Visa sponsorship indicated

  [Apply Now](https://...)
  ```
- **Smart filtering**: deduplication, garbage title blocking, repost detection, outdated season detection, US-only
- **Resume matching**: TF-IDF cosine similarity scores each job against your resume
- **Sponsorship detection**: flags jobs that require US citizenship or indicate visa sponsorship
- **Runs 24/7 on Railway's free tier** (sleeps 11 PM–7 AM to stay within limits)

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/job-alert-bot.git
cd job-alert-bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up Telegram

**Create a bot:**
1. Open Telegram → search `@BotFather` → send `/newbot`
2. Follow prompts → copy the token it gives you (looks like `123456789:ABCdef...`)

**Get your Chat ID:**
1. Open your new bot in Telegram and send it `/start`
2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in your browser
3. Find `"chat":{"id":XXXXXXXXXX}` — that number is your Chat ID

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DB_PATH=jobs_seen.db
```

### 4. Add your resume

Replace `resume.txt` with your resume as plain text. More content = better matching.

```
Your Name
your.email@example.com

SKILLS
Python, Java, React, ...

EXPERIENCE
...
```

### 5. Customize job preferences

Edit `config.py`:

```python
SEARCH_TERMS = [
    "Software Engineer Intern",
    "Backend Engineer Intern",
    "Generative AI Intern",
    # add your own...
]

LOCATIONS = [
    "Boston, MA",
    "New York, NY",
    "Remote",
    # add your own...
]

MATCH_THRESHOLD = 0.25  # lower = more alerts, higher = stricter
```

Also update the priority location tag in `notifier.py` to match your preferred cities:
```python
if "boston" in location or "new york" in location:
    priority = "⭐ PRIORITY LOCATION"
```

### 6. Run locally

```bash
python main.py
```

You should see the startup banner and Telegram alerts within a few minutes.

---

## Deploy to Railway (Free, 24/7)

See [DEPLOY_INSTRUCTIONS.txt](DEPLOY_INSTRUCTIONS.txt) for full step-by-step.

**Quick version:**
1. Push your repo to GitHub (make it **private** — your resume is in the code)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Set environment variables in Railway dashboard:
   ```
   TELEGRAM_BOT_TOKEN = your_token
   TELEGRAM_CHAT_ID   = your_chat_id
   DB_PATH            = /data/jobs_seen.db
   TZ                 = America/New_York
   ```
4. Add a persistent volume at `/data` (Volumes tab)
5. Done — Railway auto-deploys on every push

---

## How It Works

**Pipeline per scan:**
```
Search term × location → scrape jobs → filter pipeline → score vs resume → Telegram alert
```

**Filter pipeline (all mandatory):**
| Step | Filter | Blocks |
|------|--------|--------|
| 1 | US-only | Non-US jobs from LinkedIn/Google |
| 2 | Intern/co-op | Full-time roles |
| 3 | Garbage titles | Nursing, sales, accounting, etc. |
| 4 | Posted today | Reposts from previous days |
| 5 | Outdated season | "Summer 2025" listings in 2026 |

**Scoring:** TF-IDF cosine similarity between your `resume.txt` and the job description. Jobs alert if:
- Strong title match (bypasses scoring)
- No description available
- Score ≥ `MATCH_THRESHOLD` (default: 0.25)

**Alert indicators:**
- 🟢 Match ≥ 50% · 🟡 Match ≥ 30% · 🟠 Match < 30%
- ⭐ Priority location · 🌐 Other US / Remote
- ✅ Visa sponsorship indicated · ⚠️ May require US citizenship

---

## Configuration Reference

All settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `SEARCH_TERMS` | 11 terms | Job titles to search |
| `LOCATIONS` | 7 cities | Cities to search in |
| `MATCH_THRESHOLD` | `0.25` | Minimum TF-IDF score to alert |
| `CHECK_INTERVAL_MINUTES` | `30` | Minutes between scans |
| `ACTIVE_HOURS_START` | `7` | Start hour (local time) |
| `ACTIVE_HOURS_END` | `23` | End hour (local time) |

---

## Updating

**Change search terms or locations:** Edit `config.py` → commit → push (Railway auto-redeploys)

**Update resume:** Edit `resume.txt` → commit → push

**Warning:** Total queries per scan = `len(SEARCH_TERMS) × len(LOCATIONS)`. Keep this reasonable (< 150) to avoid scan timeouts.

---

## Troubleshooting

**Outside active hours:** Temporarily set `ACTIVE_HOURS_START = 0` and `ACTIVE_HOURS_END = 24` in `config.py` for testing.

**0 alerts sent:** Check `logs/job_alert.log` at DEBUG level. Common causes: all jobs filtered out, threshold too high, or no jobs posted today (weekends are slow).

**Telegram 401:** Bot token is wrong. Re-check with BotFather.

**Telegram 400 chat not found:** Send `/start` to your bot first, then re-check Chat ID.

**Non-US jobs appearing:** Already filtered — bot checks state abbreviation and country field on every job.

**Same jobs repeating:** Each job is hashed by `title|company` and stored in SQLite. True repeats mean the company name has changed slightly between scrapes — check `logs/job_alert.log` at DEBUG level.

---

## Known Quirks

- `python-telegram-bot` is in `requirements.txt` but unused — `notifier.py` calls the API directly via `requests`. Harmless but vestigial.
- `SITES` in `config.py` includes `zip_recruiter` but `scraper.py` overrides it — ZipRecruiter is disabled due to persistent 502 errors.
- Active hours use `datetime.now()` — on Railway, set `TZ=America/New_York` (or your timezone) so hours mean what you expect.

---

## Contributing

PRs welcome. Good areas to contribute:
- Support for more job boards
- Better sponsorship detection
- Slack / Discord / email notification support
- Resume scoring improvements (currently TF-IDF — could use embeddings)
- Web UI for configuration

Please keep the filter pipeline modular and easy to extend.

---

## License

MIT
