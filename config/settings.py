"""Central configuration — loads from .env and provides defaults."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = Path(os.getenv("EXPORT_PATH", DATA_DIR / "exports"))
SESSION_DIR = Path(os.getenv("SESSION_PATH", DATA_DIR / "sessions"))
LOG_PATH = Path(os.getenv("LOG_PATH", DATA_DIR / "action_log.json"))
TASK_QUEUE_PATH = Path(os.getenv("TASK_QUEUE_PATH", DATA_DIR / "task_queue.json"))

# Ensure directories exist
for d in [DATA_DIR, EXPORT_DIR, SESSION_DIR, DATA_DIR / "exports"]:
    d.mkdir(parents=True, exist_ok=True)

# ── Account ────────────────────────────────────────────
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
PROXY_URL = os.getenv("PROXY_URL", None)

# ── Rate Limits (per hour) ─────────────────────────────
RATE_LIMITS = {
    "like": int(os.getenv("MAX_LIKES_PER_HOUR", 25)),
    "follow": int(os.getenv("MAX_FOLLOWS_PER_HOUR", 15)),
    "unfollow": int(os.getenv("MAX_UNFOLLOWS_PER_HOUR", 15)),
    "story_view": int(os.getenv("MAX_STORY_VIEWS_PER_HOUR", 30)),
}

# ── Session Behavior ───────────────────────────────────
MIN_SESSION_MINUTES = int(os.getenv("MIN_SESSION_MINUTES", 10))
MAX_SESSION_MINUTES = int(os.getenv("MAX_SESSION_MINUTES", 30))
MIN_ACTION_DELAY = float(os.getenv("MIN_ACTION_DELAY", 3))
MAX_ACTION_DELAY = float(os.getenv("MAX_ACTION_DELAY", 12))

# ── Browser ────────────────────────────────────────────
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
VIEWPORT = {"width": 1280, "height": 800}  # Desktop viewport
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ── Instagram URLs ─────────────────────────────────────
IG_BASE = "https://www.instagram.com"
IG_LOGIN = f"{IG_BASE}/accounts/login/"
IG_FEED = f"{IG_BASE}/"
IG_PROFILE = lambda username: f"{IG_BASE}/{username}/"
IG_FOLLOWERS = lambda username: f"{IG_BASE}/{username}/followers/"
IG_FOLLOWING = lambda username: f"{IG_BASE}/{username}/following/"
