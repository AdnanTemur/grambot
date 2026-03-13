# InstaBot — Playwright-based Instagram Automation

A modular, stealth-first Instagram automation bot built with Playwright (Python).  
Designed for VPS deployment with human-like behavior simulation.

## Architecture

```
insta-bot/
├── config/
│   ├── settings.py          # Central configuration
│   └── accounts.example.json # Account config template
├── core/
│   ├── __init__.py
│   ├── browser.py            # Stealth Playwright browser setup
│   ├── session.py            # Session persistence & management
│   ├── human.py              # Human behavior simulation (delays, scrolls, mouse)
│   └── rate_limiter.py       # Action rate limiting & cooldowns
├── automation/
│   ├── __init__.py
│   ├── feed.py               # Feed browsing & liking
│   ├── follow.py             # Follow/unfollow actions
│   ├── stories.py            # Story viewing
│   └── runner.py             # Orchestrator — picks tasks, runs sessions
├── analytics/
│   ├── __init__.py
│   ├── extractor.py          # Parse Instagram data export (JSON)
│   ├── non_followers.py      # Compute non-followers from export
│   └── reports.py            # Generate reports (who unfollowed, stats)
├── data/
│   ├── exports/              # Place Instagram data export folders here
│   ├── sessions/             # Saved browser states
│   ├── task_queue.json       # Pending actions (unfollow list, etc.)
│   └── action_log.json       # History of performed actions
├── scheduler.py              # Randomized cron-style scheduler for VPS
├── main.py                   # CLI entry point
├── requirements.txt
└── .env.example
```

## Modules

### `automation/` — Browser Automation (Playwright)
Stealth Playwright sessions that perform actions on instagram.com.  
Human-like delays, scroll patterns, and session management.

### `analytics/` — Data Analysis (Offline, No Browser)
Parses your Instagram data export to extract non-followers, generate reports.  
Completely separate from automation — no browser, no login needed.  
Future: integrate with PyWebUI for local machine GUI.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Copy and edit config
cp .env.example .env
cp config/accounts.example.json config/accounts.json

# 3. Run analytics (non-followers extraction)
python main.py analytics --export-path data/exports/your_export_folder

# 4. Run automation (interactive first-time login)
python main.py automate --account your_username

# 5. Run scheduler (VPS deployment)
python main.py schedule --account your_username

#Create whitelist template
python main.py init-whitelist
```

## VPS Deployment

Requires `xvfb` for headful browser on headless VPS:
```bash
sudo apt install xvfb
xvfb-run python main.py schedule --account your_username
```

Or run via cron with randomized offset (see scheduler.py).
