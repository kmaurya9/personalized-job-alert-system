import os
from dotenv import load_dotenv
load_dotenv()

# ===== YOUR SETTINGS =====

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Roles + type combined (way better results)
SEARCH_TERMS = [
    # SWE / Backend
    "Software Engineer Intern",
    "Software Engineer Co-op",
    "Backend Engineer Intern",
    "Backend Developer Intern",
    "Full Stack Engineer Intern",
    # GenAI / Agentic AI
    "Generative AI Intern",
    "LLM Engineer Intern",
    "AI Engineer Intern",
    "AI Software Engineer Intern",
    "Agentic AI Intern",
    "AI Agent Engineer Intern",
]

# Locations
LOCATIONS = [
    "Boston, MA",
    "New York, NY",
    "San Francisco, CA",
    "Seattle, WA",
    "Austin, TX",
    "Chicago, IL",
    "Remote",
]

# Job boards
SITES = ["indeed", "linkedin", "zip_recruiter", "google"]

# We'll calculate this dynamically now (see main.py)
# but keeping as fallback
HOURS_OLD = 24

# Minimum match score to trigger alert
MATCH_THRESHOLD = 0.25

# How often to check (in minutes)
CHECK_INTERVAL_MINUTES = 30

# Database file
DB_PATH = os.environ.get("DB_PATH", "jobs_seen.db")

# Resume file
RESUME_PATH = "resume.txt"

# Active hours for scanning (ET) — saves server resources on free tier
# Bot only scans between these hours; sleeps outside to stay within free-tier limits
ACTIVE_HOURS_START = 7   # 7 AM
ACTIVE_HOURS_END = 23    # 11 PM
