"""Feed browsing & liking automation.

Handles scrolling through the Instagram feed and liking posts
with human-like behavior patterns.
"""

import random
from playwright.async_api import Page

from config import settings
from core.human import (
    human_delay, human_scroll, scroll_feed,
    between_actions_delay, thinking_pause, move_to_element,
)
from core.rate_limiter import RateLimiter


async def browse_feed(page: Page, rate_limiter: RateLimiter, max_likes: int = 5):
    """
    Browse the Instagram feed, occasionally liking posts.

    Simulates natural feed browsing: scroll, pause, read, sometimes like.

    Args:
        page: Playwright page.
        rate_limiter: Rate limiter instance.
        max_likes: Maximum likes to perform this session.
    """
    print("[feed] Starting feed browse session...")

    await page.goto(settings.IG_FEED, wait_until="domcontentloaded")
    await human_delay(2, 5)

    likes_done = 0
    posts_seen = 0
    max_posts = random.randint(10, 25)  # Don't scroll forever

    while posts_seen < max_posts and likes_done < max_likes:
        # Scroll to next post area
        await human_scroll(page, "down", random.choice(["small", "medium"]))
        await human_delay(1, 3)
        posts_seen += 1

        # Decide whether to like this post (30-50% chance)
        should_like = random.random() < random.uniform(0.3, 0.5)

        if should_like and rate_limiter.can_perform("like"):
            liked = await _try_like_visible_post(page)
            if liked:
                rate_limiter.record("like")
                likes_done += 1
                await between_actions_delay()

        # Sometimes pause to "read" a post longer
        if random.random() < 0.25:
            await thinking_pause()

        # Sometimes scroll back up slightly (very human)
        if random.random() < 0.1:
            await human_scroll(page, "up", "small")
            await human_delay(1, 2)

    print(f"[feed] Session done — {posts_seen} posts viewed, {likes_done} liked")
    return likes_done


async def _try_like_visible_post(page: Page) -> bool:
    """
    Attempt to like a post currently visible in the viewport.
    Returns True if a post was successfully liked.
    """
    try:
        # Find unlike-able heart icons (not already liked)
        # Instagram uses svg with aria-label="Like" for unliked posts
        like_buttons = page.locator(
            'svg[aria-label="Like"]'
        )

        count = await like_buttons.count()
        if count == 0:
            return False

        # Pick the first visible one
        for i in range(min(count, 3)):
            btn = like_buttons.nth(i)
            if await btn.is_visible():
                # Click the parent button/span
                parent = btn.locator("..")
                await parent.click()
                await human_delay(0.5, 1.5)
                print("[feed] ♥ Liked a post")
                return True

        return False

    except Exception as e:
        print(f"[feed] Like failed: {e}")
        return False


async def like_post_by_url(page: Page, post_url: str) -> bool:
    """
    Navigate to a specific post and like it.

    Args:
        post_url: Full Instagram post URL.

    Returns:
        True if liked successfully.
    """
    try:
        await page.goto(post_url, wait_until="domcontentloaded")
        await human_delay(2, 4)

        # Scroll down slightly to see the post
        await human_scroll(page, "down", "small")
        await human_delay(1, 2)

        return await _try_like_visible_post(page)

    except Exception as e:
        print(f"[feed] Failed to like {post_url}: {e}")
        return False
