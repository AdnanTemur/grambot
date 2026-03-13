"""Follow/unfollow automation.

Handles following users and unfollowing non-followers
via the Instagram web interface with human-like behavior.
"""

import json
import random
from pathlib import Path
from playwright.async_api import Page

from config import settings
from core.human import human_delay, human_scroll, between_actions_delay, thinking_pause
from core.rate_limiter import RateLimiter


async def unfollow_user(page: Page, username: str) -> bool:
    """
    Unfollow a single user by navigating to their profile.

    Args:
        username: Instagram username to unfollow.

    Returns:
        True if unfollowed successfully.
    """
    try:
        profile_url = settings.IG_PROFILE(username)
        await page.goto(profile_url, wait_until="domcontentloaded")
        await human_delay(2, 4)

        # Look for "Following" button (indicates we follow them)
        following_btn = page.locator(
            'button:has-text("Following"), '
            'div[role="button"]:has-text("Following")'
        )

        if await following_btn.count() == 0:
            print(f"[unfollow] {username} — not following or button not found")
            return False

        # Click "Following" to open unfollow dialog
        await following_btn.first.click()
        await human_delay(1, 2)

        # Click "Unfollow" in the confirmation dialog
        unfollow_confirm = page.locator(
            'button:has-text("Unfollow")'
        )

        if await unfollow_confirm.count() > 0:
            await unfollow_confirm.first.click()
            await human_delay(1, 3)
            print(f"[unfollow] ✓ Unfollowed {username}")
            return True
        else:
            print(f"[unfollow] {username} — confirm dialog not found")
            return False

    except Exception as e:
        print(f"[unfollow] ✗ Error unfollowing {username}: {e}")
        return False


async def unfollow_batch(
    page: Page,
    usernames: list[str],
    rate_limiter: RateLimiter,
    max_per_session: int = 10,
) -> list[str]:
    """
    Unfollow a batch of users with human-like pacing.

    Args:
        page: Playwright page.
        usernames: List of usernames to unfollow.
        rate_limiter: Rate limiter instance.
        max_per_session: Max unfollows this session.

    Returns:
        List of successfully unfollowed usernames.
    """
    unfollowed = []
    attempted = 0

    # Shuffle to avoid predictable patterns
    batch = usernames[:max_per_session]
    random.shuffle(batch)

    print(f"[unfollow] Starting batch — {len(batch)} targets")

    for username in batch:
        if not rate_limiter.can_perform("unfollow"):
            print("[unfollow] Rate limit reached, stopping batch")
            break

        success = await unfollow_user(page, username)
        attempted += 1

        if success:
            unfollowed.append(username)
            rate_limiter.record("unfollow", target=username)

        # Human-like delay between unfollows (longer than likes)
        delay = random.uniform(30, 120)
        print(f"[unfollow] Waiting {delay:.0f}s before next...")
        await human_delay(delay * 0.8, delay * 1.2)

        # Occasionally browse feed between unfollows (looks natural)
        if random.random() < 0.2 and attempted < len(batch):
            print("[unfollow] Quick feed check (natural behavior)...")
            await page.goto(settings.IG_FEED, wait_until="domcontentloaded")
            await human_delay(3, 8)
            await human_scroll(page, "down", "small")
            await human_delay(2, 5)

    print(f"[unfollow] Batch done — {len(unfollowed)}/{attempted} unfollowed")
    return unfollowed


async def follow_user(page: Page, username: str) -> bool:
    """
    Follow a single user by navigating to their profile.

    Args:
        username: Instagram username to follow.

    Returns:
        True if followed successfully.
    """
    try:
        profile_url = settings.IG_PROFILE(username)
        await page.goto(profile_url, wait_until="domcontentloaded")
        await human_delay(2, 4)

        # Scroll down slightly to view profile (human behavior)
        await human_scroll(page, "down", "small")
        await human_delay(1, 2)

        follow_btn = page.locator(
            'button:has-text("Follow"):not(:has-text("Following")):not(:has-text("Unfollow"))'
        )

        if await follow_btn.count() == 0:
            print(f"[follow] {username} — already following or button not found")
            return False

        await follow_btn.first.click()
        await human_delay(1, 3)
        print(f"[follow] ✓ Followed {username}")
        return True

    except Exception as e:
        print(f"[follow] ✗ Error following {username}: {e}")
        return False


# ── Task Queue Management ──────────────────────────────

def load_task_queue() -> dict:
    """Load the pending task queue from disk."""
    if settings.TASK_QUEUE_PATH.exists():
        try:
            return json.loads(settings.TASK_QUEUE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"unfollow": [], "follow": [], "completed": {"unfollow": [], "follow": []}}


def save_task_queue(queue: dict):
    """Save the task queue to disk."""
    settings.TASK_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.TASK_QUEUE_PATH.write_text(json.dumps(queue, indent=2))


def mark_completed(queue: dict, action: str, username: str):
    """Move a username from pending to completed in the queue."""
    if username in queue.get(action, []):
        queue[action].remove(username)
    if "completed" not in queue:
        queue["completed"] = {"unfollow": [], "follow": []}
    if username not in queue["completed"].get(action, []):
        queue["completed"].setdefault(action, []).append(username)
    save_task_queue(queue)
