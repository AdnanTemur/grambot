# GramBot

A Playwright-based Instagram automation bot built with Python. Automates everyday Instagram activities — feed browsing, liking, story viewing, and unfollowing non-followers — with human-like behavior patterns.

No private APIs. No reverse engineering. Just a browser doing what you'd do manually, but on autopilot.

## Why Playwright?

Most Instagram bots rely on reverse-engineered private APIs that break every time Instagram updates their app. GramBot controls a real Chromium browser through [Playwright](https://playwright.dev/python/). As long as instagram.com works in a browser, GramBot works.

## Features

- **Feed browsing & liking** — scrolls your feed and likes posts naturally
- **Story viewing** — watches stories with realistic timing
- **Unfollow non-followers** — parses your Instagram data export to find who doesn't follow you back, then unfollows in small batches
- **Session persistence** — saves browser state so you don't re-login every run
- **2FA / challenge handling** — detects WhatsApp, SMS, email, and authenticator app challenges; prompts for the code in your terminal (works over SSH)
- **Rate limiting** — configurable per-action hourly limits
- **Randomized scheduling** — daemon mode for VPS deployment
- **Whitelist** — protect accounts you never want to unfollow
- **Offline analytics** — non-followers extraction runs without a browser, just parses your data export

## Project Structure

```
grambot/
├── config/
│   └── settings.py           # Central configuration (loaded from .env)
├── core/
│   ├── browser.py            # Playwright browser setup
│   ├── session.py            # Login, 2FA handling, session persistence
│   ├── human.py              # Behavior simulation
│   └── rate_limiter.py       # Per-action hourly rate limits
├── automation/
│   ├── feed.py               # Feed browsing & liking
│   ├── follow.py             # Follow/unfollow actions + task queue
│   ├── stories.py            # Story viewing
│   └── runner.py             # Session orchestrator
├── analytics/
│   ├── extractor.py          # Instagram data export parser
│   ├── non_followers.py      # Non-followers computation + queue generation
│   └── reports.py            # Activity reports + CSV export
├── data/
│   ├── exports/              # Your Instagram data exports go here
│   ├── sessions/             # Saved browser states (gitignored)
│   ├── task_queue.json       # Pending unfollow/follow actions
│   └── whitelist.txt         # Accounts to never unfollow
├── main.py                   # CLI entry point
├── scheduler.py              # Randomized scheduler for VPS
└── .env                      # Your credentials (gitignored)
```

## Setup

### Prerequisites

- Python 3.10+
- Chromium (installed via Playwright)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/grambot.git
cd grambot

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -r requirements.txt
playwright install chromium
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` with your Instagram credentials and preferences. All behavior — rate limits, session duration, delays, proxy — is configurable through `.env`. See `.env.example` for the full list of options.

## Usage

### 1. First Login

Run an interactive session to complete 2FA and save the browser session:

```bash
python main.py login --account your_username
```

If Instagram asks for a verification code, you'll be prompted in the terminal. This works over SSH — no GUI needed on a VPS.

### 2. Extract Non-Followers

Request your data from Instagram: **Settings → Accounts Center → Your information and permissions → Download your information** → select **Followers and following** → format **JSON**.

Instagram will email you a download link (usually within a few days). Download and unzip it, then:

```bash
python main.py analytics non-followers --export-path data/exports/your_export_folder
```

Output:

```
==================================================
  INSTAGRAM NON-FOLLOWERS REPORT
==================================================
  Followers:        1247
  Following:        1583
  ─────────────────────────
  Mutual:           1089
  Non-followers:     494  ← don't follow you back
  Fans:              158  ← you don't follow back
  Whitelisted:        12  ← excluded from unfollow
==================================================
```

This generates `data/task_queue.json` with the unfollow list. The analytics module is completely offline — no browser, no login needed.

### 3. Run Automation

Single session:

```bash
python main.py automate --account your_username
```

Force fresh login (ignores saved session):

```bash
python main.py automate --account your_username --fresh
```

### 4. Deploy on VPS

Install xvfb for running the browser without a display:

```bash
sudo apt install xvfb
```

Daemon mode:

```bash
xvfb-run python main.py schedule --account your_username --daemon
```

Cron mode:

```bash
# crontab -e
0 */3 * * * cd /path/to/grambot && xvfb-run python main.py schedule --account your_username
```

### 5. Other Commands

```bash
# Check rate limits and queue status
python main.py status

# Create a whitelist template
python main.py init-whitelist

# Parse an export without generating a queue
python main.py analytics parse --export-path data/exports/your_folder

# Export non-followers to CSV
python main.py analytics non-followers --export-path data/exports/your_folder --csv
```

## Whitelist

Create `data/whitelist.txt` to protect accounts from being unfollowed:

```
# Accounts I never want to unfollow
natgeo
nasa
my_best_friend
```

Run `python main.py init-whitelist` to generate a template.

## Roadmap

- [ ] Explore page browsing
- [ ] Reel viewing
- [ ] Profile visiting & targeted liking
- [ ] PyWebUI dashboard for local machine
- [ ] Multi-account support

## Disclaimer

This project is for **educational and research purposes only**. Use of automated tools to interact with Instagram may violate [Instagram's Terms of Service](https://help.instagram.com/581066165581870). The author is not responsible for any account restrictions, suspensions, or other consequences resulting from the use of this software.

This tool does not access any private or undocumented APIs. It operates through the standard web browser interface using Playwright, the same technology used for browser testing and QA automation.

**Use at your own risk.**

## License

MIT
