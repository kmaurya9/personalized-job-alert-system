import os

# ===== YOUR SETTINGS =====

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8633219125:AAELaaXsms_1iTY2E3i1-6FRffDWOQadnE4")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8616520610")

# Roles + type combined (way better results)
SEARCH_TERMS = [
    "Data Analyst Intern",
    "Data Analyst Co-op",
    "Data Scientist Intern",
    "Data Scientist Co-op",
    "ML Engineer Intern",
    "Machine Learning Intern",
    "AI Engineer Intern",
    "AI Intern Co-op",
    "Data Engineer Intern",
    "Data Engineer Co-op",
    "Summer Data Analyst",
    "Summer Data Science",
]

# Locations
LOCATIONS = [
    "Boston, MA",
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
