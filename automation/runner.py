"""Runner — orchestrates a single automation session.

Picks tasks based on available rate limits and task queue,
runs them within a randomized session duration, and saves state.
"""

import random
import time
import asyncio

from config import settings
from core.browser import create_browser_context, close_browser
from core.session import (
    login,
    save_session,
    is_logged_in,
    get_session_path,
    session_exists,
)
from core.human import (
    random_session_duration,
    should_take_break,
    take_break,
    human_delay,
)
from core.rate_limiter import RateLimiter
from automation.feed import browse_feed
from automation.follow import (
    unfollow_batch,
    load_task_queue,
    save_task_queue,
    mark_completed,
)
from automation.stories import view_stories


async def run_session(
    username: str = None, password: str = None, force_login: bool = False
):
    """
    Run a single automation session.

    Args:
        username: Override IG_USERNAME from config.
        password: Override IG_PASSWORD from config.
        force_login: If True, skip session check and force fresh login.
    """
    _username = username or settings.IG_USERNAME
    _password = password or settings.IG_PASSWORD

    if not _username or not _password:
        print("[runner] ERROR: No username/password configured. Check .env")
        return

    rate_limiter = RateLimiter()
    session_duration = random_session_duration()
    session_start = time.time()

    print(f"[runner] Starting session for @{_username}")
    print(f"[runner] Planned duration: {session_duration / 60:.1f} minutes")
    print(f"[runner] Rate status: {rate_limiter.status()}")

    # ── Launch browser ──────────────────────────────────
    if force_login:
        state_path = None
        print("[runner] Fresh login requested — ignoring saved session")
    else:
        state_path = (
            str(get_session_path(_username)) if session_exists(_username) else None
        )

    pw, browser, context, page = await create_browser_context(
        storage_state=state_path,
    )

    try:
        # ── Check/perform login ─────────────────────────
        if force_login:
            logged_in = False
        else:
            logged_in = await is_logged_in(page)

        if not logged_in:
            print("[runner] Session expired, logging in...")
            logged_in = await login(page, _username, _password)
            if not logged_in:
                print("[runner] Login failed. Aborting session.")
                return
            await save_session(context, _username)

        print("[runner] Session active ✓")

        # ── Build activity plan ─────────────────────────
        # Randomize the order of activities for natural behavior
        activities = _build_activity_plan(rate_limiter)
        random.shuffle(activities)

        print(f"[runner] Activity plan: {[a['type'] for a in activities]}")

        # ── Execute activities ──────────────────────────
        actions_done = 0

        for activity in activities:
            # Check session time limit
            elapsed = time.time() - session_start
            if elapsed > session_duration:
                print(f"[runner] Session time limit reached ({elapsed / 60:.1f} min)")
                break

            # Occasional break
            if should_take_break(actions_done):
                await take_break()

            try:
                if activity["type"] == "feed":
                    count = await browse_feed(
                        page,
                        rate_limiter,
                        max_likes=activity.get("max_likes", 5),
                    )
                    actions_done += count

                elif activity["type"] == "stories":
                    count = await view_stories(
                        page,
                        rate_limiter,
                        max_stories=activity.get("max_stories", 5),
                    )
                    actions_done += count

                elif activity["type"] == "unfollow":
                    queue = load_task_queue()
                    pending = queue.get("unfollow", [])

                    if pending:
                        unfollowed = await unfollow_batch(
                            page,
                            pending,
                            rate_limiter,
                            max_per_session=activity.get("max_count", 8),
                        )
                        for u in unfollowed:
                            mark_completed(queue, "unfollow", u)
                        actions_done += len(unfollowed)
                    else:
                        print("[runner] No pending unfollows in task queue")

            except Exception as e:
                print(f"[runner] Activity '{activity['type']}' failed: {e}")
                await human_delay(5, 10)

            # Delay between activities
            await human_delay(5, 15)

        # ── Wrap up ─────────────────────────────────────
        elapsed = time.time() - session_start
        print(
            f"[runner] Session complete — {actions_done} actions in {elapsed / 60:.1f} min"
        )

    finally:
        # Always save session and close browser
        await close_browser(
            pw,
            browser,
            context,
            save_state_path=str(get_session_path(_username)),
        )
        print("[runner] Browser closed, session saved ✓")


def _build_activity_plan(rate_limiter: RateLimiter) -> list[dict]:
    """
    Build a list of activities based on available rate limits.
    Weights activities to feel natural.
    """
    plan = []

    # Always browse feed (primary natural activity)
    likes_remaining = rate_limiter.remaining("like")
    if likes_remaining > 0:
        plan.append(
            {
                "type": "feed",
                "max_likes": min(random.randint(3, 8), likes_remaining),
            }
        )

    # Stories viewing (common passive activity)
    stories_remaining = rate_limiter.remaining("story_view")
    if stories_remaining > 3:
        plan.append(
            {
                "type": "stories",
                "max_stories": min(random.randint(3, 8), stories_remaining),
            }
        )

    # Unfollows (less frequent, do in small batches)
    unfollows_remaining = rate_limiter.remaining("unfollow")
    if unfollows_remaining > 0:
        queue = load_task_queue()
        if queue.get("unfollow"):
            plan.append(
                {
                    "type": "unfollow",
                    "max_count": min(random.randint(3, 8), unfollows_remaining),
                }
            )

    # Sometimes add a second feed browse (people check feed multiple times)
    if random.random() < 0.4 and likes_remaining > 5:
        plan.append(
            {
                "type": "feed",
                "max_likes": random.randint(2, 4),
            }
        )

    return plan
