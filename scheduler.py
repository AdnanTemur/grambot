"""Randomized scheduler for VPS deployment.

Two modes of operation:
1. Daemon mode: runs continuously, triggers sessions at random intervals.
2. Cron helper: called by cron, adds random sleep offset before running.

Usage:
  Daemon:  python scheduler.py --daemon --account your_username
  Cron:    python scheduler.py --once --account your_username
           (add to crontab at fixed intervals, the script adds its own jitter)
"""

import random
import time
import asyncio
import argparse
from datetime import datetime, timedelta

from automation.runner import run_session


# ── Scheduling Configuration ───────────────────────────

# How many sessions per day (min, max)
SESSIONS_PER_DAY = (3, 6)

# Active hours (don't run at 3am — looks suspicious)
ACTIVE_HOURS_START = 8   # 8 AM
ACTIVE_HOURS_END = 23    # 11 PM

# Max random offset when called from cron (minutes)
CRON_JITTER_MINUTES = 45


def _is_active_hour() -> bool:
    """Check if current hour is within active window."""
    hour = datetime.now().hour
    return ACTIVE_HOURS_START <= hour < ACTIVE_HOURS_END


def _next_session_delay() -> float:
    """
    Calculate seconds until next session.
    Spreads sessions evenly across active hours with randomness.
    """
    active_hours = ACTIVE_HOURS_END - ACTIVE_HOURS_START
    sessions_today = random.randint(*SESSIONS_PER_DAY)
    avg_gap_hours = active_hours / sessions_today
    # Add jitter: ±30% of average gap
    gap_hours = avg_gap_hours * random.uniform(0.7, 1.3)
    return gap_hours * 3600


async def run_once(username: str, password: str = None):
    """
    Run a single session with cron-style jitter.
    Adds a random delay (0 to CRON_JITTER_MINUTES) before starting.
    """
    if not _is_active_hour():
        print(f"[scheduler] Outside active hours ({ACTIVE_HOURS_START}-{ACTIVE_HOURS_END}). Skipping.")
        return

    # Random jitter so cron doesn't fire at exact intervals
    jitter = random.uniform(0, CRON_JITTER_MINUTES * 60)
    print(f"[scheduler] Jitter delay: {jitter / 60:.1f} minutes")
    await asyncio.sleep(jitter)

    await run_session(username=username, password=password)


async def run_daemon(username: str, password: str = None):
    """
    Run as a long-lived daemon process.
    Schedules sessions at random intervals throughout the day.
    """
    print("[scheduler] Starting daemon mode")
    print(f"[scheduler] Active hours: {ACTIVE_HOURS_START}:00 - {ACTIVE_HOURS_END}:00")
    print(f"[scheduler] Sessions per day: {SESSIONS_PER_DAY[0]}-{SESSIONS_PER_DAY[1]}")

    while True:
        if _is_active_hour():
            print(f"\n[scheduler] {datetime.now().strftime('%Y-%m-%d %H:%M')} — Starting session")
            try:
                await run_session(username=username, password=password)
            except Exception as e:
                print(f"[scheduler] Session failed: {e}")

            delay = _next_session_delay()
            next_time = datetime.now() + timedelta(seconds=delay)
            print(f"[scheduler] Next session at ~{next_time.strftime('%H:%M')}")
            await asyncio.sleep(delay)

        else:
            # Sleep until active hours start
            now = datetime.now()
            if now.hour >= ACTIVE_HOURS_END:
                # Wait until tomorrow morning
                tomorrow = now.replace(
                    hour=ACTIVE_HOURS_START, minute=0, second=0
                ) + timedelta(days=1)
                wait = (tomorrow - now).total_seconds()
            else:
                # Wait until today's start
                start = now.replace(
                    hour=ACTIVE_HOURS_START, minute=0, second=0
                )
                wait = (start - now).total_seconds()

            wait += random.uniform(0, 1800)  # Extra jitter
            print(f"[scheduler] Outside active hours. Sleeping {wait / 3600:.1f}h")
            await asyncio.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description="InstaBot Scheduler")
    parser.add_argument("--account", "-a", required=True, help="Instagram username")
    parser.add_argument("--password", "-p", default=None, help="Instagram password (or use .env)")
    parser.add_argument("--daemon", action="store_true", help="Run as persistent daemon")
    parser.add_argument("--once", action="store_true", help="Run single session with jitter")

    args = parser.parse_args()

    if args.daemon:
        asyncio.run(run_daemon(args.account, args.password))
    elif args.once:
        asyncio.run(run_once(args.account, args.password))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
