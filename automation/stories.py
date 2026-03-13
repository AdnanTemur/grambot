"""Story viewing automation.

Views stories from the feed tray with human-like timing.
This helps maintain natural-looking account activity.
"""

import random
from playwright.async_api import Page

from config import settings
from core.human import human_delay, human_scroll
from core.rate_limiter import RateLimiter


async def view_stories(page: Page, rate_limiter: RateLimiter, max_stories: int = 5):
    """
    View stories from the feed story tray.

    Args:
        page: Playwright page.
        rate_limiter: Rate limiter instance.
        max_stories: Maximum stories to view.

    Returns:
        Number of stories viewed.
    """
    print("[stories] Starting story viewing...")

    await page.goto(settings.IG_FEED, wait_until="domcontentloaded")
    await human_delay(2, 4)

    viewed = 0

    try:
        # Story tray is at the top of the feed — click first unwatched story
        # Stories with gradient ring = unwatched
        story_items = page.locator(
            'div[role="button"] canvas, '  # Canvas-rendered story rings
            'button[aria-label*="Story"]'   # Accessible story buttons
        )

        if await story_items.count() == 0:
            # Try alternative: the story tray container
            story_items = page.locator(
                'div[role="menu"] button, '
                'div[role="listbox"] button'
            )

        if await story_items.count() == 0:
            print("[stories] No stories found in tray")
            return 0

        # Click the first story
        await story_items.first.click()
        await human_delay(2, 4)

        while viewed < max_stories and rate_limiter.can_perform("story_view"):
            # Wait for story content to load
            await human_delay(3, 7)  # Watch the story for a realistic duration
            rate_limiter.record("story_view")
            viewed += 1

            # Tap right side to go to next story (or next person's story)
            # Instagram advances on right-side tap
            viewport_w = settings.VIEWPORT["width"]
            viewport_h = settings.VIEWPORT["height"]

            tap_x = viewport_w * random.uniform(0.7, 0.9)
            tap_y = viewport_h * random.uniform(0.3, 0.6)

            await page.mouse.click(tap_x, tap_y)
            await human_delay(1, 2)

            # Check if we've exited stories (back to feed)
            if "/stories/" not in page.url and "instagram.com" in page.url:
                # Might have exited stories
                if await page.locator('svg[aria-label="Like"]').count() > 0:
                    break

        print(f"[stories] Viewed {viewed} stories")

    except Exception as e:
        print(f"[stories] Error viewing stories: {e}")

    return viewed
