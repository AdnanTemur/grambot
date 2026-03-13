"""Human behavior simulation.

Realistic delays, typing patterns, scroll behavior,
and mouse movement to avoid bot detection.
"""

import random
import math
import asyncio
from playwright.async_api import Page

from config import settings


# ── Delays ─────────────────────────────────────────────

async def human_delay(min_sec: float = None, max_sec: float = None):
    """
    Sleep for a random duration using gaussian distribution.
    Center-weighted — most delays cluster around the midpoint,
    with occasional shorter/longer pauses like a real human.
    """
    _min = min_sec if min_sec is not None else settings.MIN_ACTION_DELAY
    _max = max_sec if max_sec is not None else settings.MAX_ACTION_DELAY

    mean = (_min + _max) / 2
    std_dev = (_max - _min) / 4  # 95% of values within min-max range
    delay = max(_min, min(_max, random.gauss(mean, std_dev)))

    await asyncio.sleep(delay)


async def micro_delay():
    """Very short delay — simulates reaction time between small actions."""
    await asyncio.sleep(random.uniform(0.1, 0.5))


async def between_actions_delay():
    """Delay between major actions (like → scroll → like)."""
    await human_delay(settings.MIN_ACTION_DELAY, settings.MAX_ACTION_DELAY)


async def thinking_pause():
    """Longer pause — simulates reading/thinking before acting."""
    await human_delay(5, 15)


# ── Typing ─────────────────────────────────────────────

async def human_type(page: Page, text: str):
    """
    Type text with human-like variable speed.
    Includes occasional pauses and speed variations.
    """
    for i, char in enumerate(text):
        # Base typing speed: 50-150ms per character
        delay = random.uniform(50, 150)

        # Occasional longer pause (thinking/hesitation)
        if random.random() < 0.05:
            delay += random.uniform(200, 500)

        # Slightly faster for repeated characters
        if i > 0 and text[i] == text[i - 1]:
            delay *= 0.7

        await page.keyboard.type(char, delay=delay)


# ── Scrolling ──────────────────────────────────────────

async def human_scroll(page: Page, direction: str = "down", amount: str = "medium"):
    """
    Scroll the page with realistic behavior.

    Args:
        direction: "down" or "up"
        amount: "small" (1 post), "medium" (2-3 posts), "large" (5+ posts)
    """
    scroll_map = {
        "small": (200, 400),
        "medium": (400, 800),
        "large": (800, 1500),
    }
    min_px, max_px = scroll_map.get(amount, (400, 800))
    total_scroll = random.randint(min_px, max_px)

    if direction == "up":
        total_scroll = -total_scroll

    # Scroll in multiple small increments (not one big jump)
    steps = random.randint(3, 7)
    for i in range(steps):
        # Ease-in-out: slower at start and end
        progress = i / steps
        ease = math.sin(progress * math.pi)  # 0 → 1 → 0
        step_amount = int((total_scroll / steps) * (0.5 + ease))

        await page.mouse.wheel(0, step_amount)
        await asyncio.sleep(random.uniform(0.05, 0.15))

    # Small settling pause after scroll
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def scroll_feed(page: Page, num_posts: int = 3):
    """Scroll through feed naturally, pausing at posts like a human would."""
    for _ in range(num_posts):
        await human_scroll(page, "down", random.choice(["small", "medium"]))

        # Sometimes pause to "read" a post
        if random.random() < 0.4:
            await thinking_pause()
        else:
            await human_delay(1, 3)


# ── Mouse Movement ─────────────────────────────────────

async def move_to_element(page: Page, selector: str):
    """
    Move mouse to an element with a natural curved path.
    Uses bezier-like movement instead of instant teleport.
    """
    element = page.locator(selector).first
    box = await element.bounding_box()
    if not box:
        return

    # Target point with slight randomness (don't always click dead center)
    target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
    target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)

    # Move in steps with slight curve
    steps = random.randint(5, 12)
    # Get current rough position (viewport center as fallback)
    current_x = settings.VIEWPORT["width"] / 2
    current_y = settings.VIEWPORT["height"] / 2

    for i in range(steps):
        t = (i + 1) / steps
        # Add slight curve via sine wave offset
        curve_offset = math.sin(t * math.pi) * random.uniform(-20, 20)

        x = current_x + (target_x - current_x) * t + curve_offset
        y = current_y + (target_y - current_y) * t

        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.01, 0.04))

    await micro_delay()


# ── Session Behavior ───────────────────────────────────

def random_session_duration() -> float:
    """Get a random session duration in seconds."""
    return random.uniform(
        settings.MIN_SESSION_MINUTES * 60,
        settings.MAX_SESSION_MINUTES * 60,
    )


def should_take_break(actions_done: int) -> bool:
    """Decide if bot should take a longer break (simulating distraction)."""
    # After every 5-10 actions, 30% chance of a longer break
    if actions_done > 0 and actions_done % random.randint(5, 10) == 0:
        return random.random() < 0.3
    return False


async def take_break():
    """Simulate a human taking a short break from scrolling."""
    duration = random.uniform(30, 120)
    print(f"[human] Taking a {duration:.0f}s break...")
    await asyncio.sleep(duration)
