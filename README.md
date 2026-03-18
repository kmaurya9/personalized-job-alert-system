# Personalized Job Alert Bot

A Python bot that scrapes **Indeed**, **LinkedIn**, and **Google Jobs** for job listings, scores them against your resume using TF-IDF cosine similarity, and sends matching alerts to **Telegram** — automatically, every 30 minutes.

Fully configurable: any job role, any location, any country.

---

## What You Get

Telegram alerts like this:
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

**Features:**
- Searches any job role across any location or country
- Scores each job against your resume — only relevant ones reach you
- Deduplication via SQLite — never see the same job twice
- Sponsorship/visa detection — flags citizenship requirements
- Runs 24/7 free on Railway (sleeps outside active hours to stay within limits)

---

## Setup (15 minutes)

### Step 1 — Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/personalized-job-alert-system.git
cd personalized-job-alert-system
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

---

### Step 2 — Create your Telegram bot

1. Open Telegram → search `@BotFather` → send `/newbot`
2. Follow the prompts → copy the token (looks like `123456789:ABCdef...`)
3. Open your new bot and send it `/start`
4. Visit this URL in your browser (replace `<TOKEN>` with yours):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
5. Find `"chat":{"id":XXXXXXXXXX}` — that number is your Chat ID

Edit `.env`:
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DB_PATH=jobs_seen.db
```

---

### Step 3 — Add your resume

Replace `resume.txt` with your resume as **plain text** (not PDF or DOCX).
Include skills, experience, projects, and coursework — more keywords = better matching.

---

### Step 4 — Customize for your job search

Open `config.py` and update these settings:

#### Job roles (`SEARCH_TERMS`)
Add any role you're targeting — the bot searches each one:
```python
SEARCH_TERMS = [
    "Software Engineer Intern",     # tech roles
    "Marketing Manager",            # any role works
    "Data Analyst",                 # full-time or intern
    "Product Manager Intern",
    # add as many as you want
]
```
> **Note:** More terms = longer scan time. Each term × each location = one query. Keep under ~150 total combinations.

#### Locations (`LOCATIONS`)
Any city, country, or "Remote" works:
```python
LOCATIONS = [
    "London, UK",           # international cities work
    "Toronto, Canada",
    "Bangalore, India",
    "Remote",               # worldwide remote
    "New York, NY",
]
```

#### Match threshold (`MATCH_THRESHOLD`)
How closely a job must match your resume:
```python
MATCH_THRESHOLD = 0.25   # 0.15 = more alerts, 0.35 = stricter
```

#### Priority locations
In `notifier.py`, update the cities you want tagged as ⭐ PRIORITY:
```python
if "london" in location or "toronto" in location:
    priority = "⭐ PRIORITY LOCATION"
```

---

### Step 5 — Important filters to know about

The bot has two filters that are **on by default**. If they don't fit your use case, here's how to adjust them:

#### Intern/co-op filter (`scraper.py` → `is_intern_or_coop()`)
By default, only jobs with these words in the title pass: `intern`, `co-op`, `summer`, `apprentice`, `trainee`.

**If you want full-time roles too**, comment out Filter 2 in `scraper.py`:
```python
# FILTER 2: Must be intern/co-op
# if not is_intern_or_coop(title):
#     ...
#     continue
```

#### US-only filter (`scraper.py` → `is_us_based()`)
By default, only US-based jobs pass (checks state abbreviation and country field).

**If you're searching outside the US**, comment out Filter 1 in `scraper.py`:
```python
# FILTER 1: Must be US-based
# if not is_us_based(row):
#     ...
#     continue
```

---

### Step 6 — Run locally

```bash
python main.py
```

You should see the startup banner and Telegram alerts arriving within a few minutes.
Press `Ctrl+C` to stop.

---

## Deploy to Railway (Free, 24/7)

See [DEPLOY_INSTRUCTIONS.txt](DEPLOY_INSTRUCTIONS.txt) for full step-by-step.

**Quick version:**
1. Push your repo to GitHub — set it **private** (your resume is in the code)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Set environment variables in Railway dashboard:
   ```
   TELEGRAM_BOT_TOKEN = your_token
   TELEGRAM_CHAT_ID   = your_chat_id
   DB_PATH            = /data/jobs_seen.db
   TZ                 = America/New_York    ← set to your timezone
   ```
4. Add a persistent volume at `/data` (Volumes tab) — prevents duplicate alerts after redeploys
5. Done — Railway auto-deploys on every push

> **Timezone:** The bot runs between `ACTIVE_HOURS_START` (7) and `ACTIVE_HOURS_END` (23). Set `TZ` to your local timezone (e.g. `Europe/London`, `Asia/Kolkata`, `America/Los_Angeles`) so active hours match your local time.

---

## How It Works

**Pipeline per scan:**
```
Search term × location
    → scrape Indeed + LinkedIn + Google
        → filter pipeline
            → score vs your resume (TF-IDF)
                → Telegram alert
```

**Filter pipeline:**
| # | Filter | What it blocks | How to disable |
|---|--------|----------------|----------------|
| 1 | US-only | Non-US jobs | Comment out in `scraper.py` |
| 2 | Intern/co-op titles | Full-time roles | Comment out in `scraper.py` |
| 3 | Garbage titles | Unrelated fields | Edit `is_total_garbage()` |
| 4 | Posted today | Reposts from old days | Always recommended to keep |
| 5 | Outdated season | "Summer 2024" in 2026 | Always recommended to keep |

**Alert score indicators:**
- 🟢 Match ≥ 50% · 🟡 Match ≥ 30% · 🟠 Match < 30%
- ⭐ Priority location · 🌐 Other location
- ✅ Visa sponsorship indicated · ⚠️ May require citizenship/clearance

---

## Configuration Reference

All main settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `SEARCH_TERMS` | list of roles | Job titles to search |
| `LOCATIONS` | list of cities | Locations to search |
| `MATCH_THRESHOLD` | `0.25` | Min resume match score to alert |
| `CHECK_INTERVAL_MINUTES` | `30` | Minutes between scans |
| `ACTIVE_HOURS_START` | `7` | Start scanning at this hour |
| `ACTIVE_HOURS_END` | `23` | Stop scanning at this hour |

---

## Updating After Deployment

| Change | What to do |
|--------|------------|
| Search terms / locations | Edit `config.py` → commit → push |
| Resume | Edit `resume.txt` → commit → push |
| Threshold | Edit `config.py` → commit → push |
| Enable full-time roles | Comment out Filter 2 in `scraper.py` → commit → push |
| Enable non-US jobs | Comment out Filter 1 in `scraper.py` → commit → push |

Railway auto-redeploys on every push.

---

## Troubleshooting

**Getting 0 alerts:**
- Check `logs/job_alert.log` for DEBUG-level filter decisions
- Try lowering `MATCH_THRESHOLD` to `0.15`
- Check if Filter 1 or 2 is blocking your target roles (see above)
- Weekends have fewer postings — test on a weekday

**Getting non-US jobs:**
- Filter 1 is active — check `scraper.py` line ~30 that `is_us_based()` is not commented out

**Getting only intern roles:**
- Filter 2 is active by default — comment it out in `scraper.py` for full-time roles

**Telegram 401 Unauthorized:** Bot token is wrong — re-check with BotFather

**Telegram 400 chat not found:** Send `/start` to your bot first, then re-verify Chat ID

**Outside active hours:** Temporarily set `ACTIVE_HOURS_START = 0`, `ACTIVE_HOURS_END = 24` in `config.py` for testing

---

## Contributing

PRs welcome. Good areas:
- Additional job boards
- Slack / Discord / email notification support
- Better sponsorship/visa detection
- Embedding-based resume scoring (currently TF-IDF)
- Web UI for configuration

---

## License

MIT
