"""Session persistence & login management.

Handles saving/loading browser state and performing
Instagram login when no valid session exists.
"""

import sys
import os
import json
from pathlib import Path
from playwright.async_api import Page, BrowserContext

from config import settings
from core.human import human_delay, human_type


def get_session_path(username: str) -> Path:
    return settings.SESSION_DIR / f"{username}_state.json"


def session_exists(username: str) -> bool:
    path = get_session_path(username)
    return path.exists() and path.stat().st_size > 100


async def _screenshot(page: Page, name: str):
    try:
        path = settings.DATA_DIR / f"debug_{name}.png"
        await page.screenshot(path=str(path))
        print(f"[session] Screenshot: {path}")
    except Exception:
        pass


def _is_interactive() -> bool:
    return sys.stdin.isatty() and os.getenv("NONINTERACTIVE") != "1"


# ── Login ──────────────────────────────────────────────


async def login(page: Page, username: str, password: str) -> bool:
    """Perform Instagram login, handling challenges/2FA inline."""

    print(f"[session] Logging in as {username}...")

    # 1. Navigate to login page
    await page.goto(settings.IG_LOGIN, wait_until="domcontentloaded", timeout=30000)

    # 2. Wait for the page to fully render (React hydration)
    #    Instead of looking for specific input names/aria-labels (which Instagram
    #    changes frequently), wait for ANY visible input to appear on the login page.
    any_input = page.locator("input:visible")

    try:
        await any_input.first.wait_for(state="visible", timeout=20000)
    except Exception:
        if "/accounts/login" not in page.url:
            print(f"[session] Redirected to {page.url} — may already be logged in")
            return True
        await _screenshot(page, "login_form_missing")
        print(f"[session] Login form didn't render. URL: {page.url}")
        return False

    await human_delay(1, 2)

    # 3. Handle cookie consent if present
    try:
        cookie_btn = page.locator(
            "button:has-text('Allow all cookies'), "
            "button:has-text('Allow essential'), "
            "button:has-text('Accept')"
        )
        if await cookie_btn.count() > 0:
            await cookie_btn.first.click()
            await human_delay(1, 2)
    except Exception:
        pass

    # 4. Find username and password fields by type/position
    #    The login page always has: first input = username, second input = password
    all_inputs = page.locator("input:visible")
    input_count = await all_inputs.count()
    print(f"[session] Found {input_count} input(s) on login page")

    if input_count < 2:
        await _screenshot(page, "login_inputs_missing")
        print("[session] Expected at least 2 inputs (username + password)")
        return False

    username_input = all_inputs.nth(0)
    password_input = all_inputs.nth(1)

    # 5. Enter credentials
    await username_input.click()
    await human_delay(0.3, 0.8)
    await human_type(page, username)

    await human_delay(0.5, 1.5)

    await password_input.click()
    await human_delay(0.3, 0.8)
    await human_type(page, password)

    await human_delay(0.5, 1.5)

    # 5. Submit — try button click, fall back to Enter
    login_btn = page.locator(
        'button[type="submit"], '
        'button:has-text("Log in"), '
        'button:has-text("Log In"), '
        'div[role="button"]:has-text("Log in")'
    )

    try:
        await login_btn.first.wait_for(state="visible", timeout=5000)
        await login_btn.first.click()
    except Exception:
        print("[session] Login button not found, pressing Enter")
        await page.keyboard.press("Enter")

    # 6. Wait for page to change — could go to feed, challenge, or show error
    await human_delay(4, 6)

    # 7. Determine where we ended up
    result = await _resolve_post_login(page)
    return result


async def _resolve_post_login(page: Page, depth: int = 0) -> bool:
    """
    After submitting credentials, figure out what Instagram is showing us
    and handle it. This is recursive to handle multiple steps
    (e.g. challenge → save info → notifications).
    """
    if depth > 5:
        print("[session] Too many post-login steps. Something is wrong.")
        await _screenshot(page, "too_many_steps")
        return False

    current_url = page.url
    print(f"[session] Post-login step {depth} — URL: {current_url}")

    # ── Success: we're on the feed ──
    if _is_feed_url(current_url):
        print(f"[session] ✓ Logged in successfully!")
        return True

    # ── Challenge / 2FA page (check FIRST — can be at /accounts/login/ URL) ──
    if await _is_challenge_page(page):
        resolved = await _handle_challenge(page)
        if not resolved:
            return False
        await human_delay(2, 4)
        return await _resolve_post_login(page, depth + 1)

    # ── Still on login page: check for errors ──
    if "/accounts/login" in current_url:
        error = page.locator(
            "#slfErrorAlert, "
            "[data-testid='login-error-message'], "
            "div[role='alert']"
        )
        if await error.count() > 0:
            msg = (await error.first.text_content() or "").strip()
            if msg:
                print(f"[session] Login error: {msg}")
                return False

        # No visible error but still on login — wait a bit more
        await human_delay(3, 5)

        # Re-check for challenge (might have loaded late)
        if await _is_challenge_page(page):
            resolved = await _handle_challenge(page)
            if not resolved:
                return False
            await human_delay(2, 4)
            return await _resolve_post_login(page, depth + 1)

        if "/accounts/login" in page.url:
            await _screenshot(page, "stuck_on_login")
            print("[session] Still on login page. Credentials may be wrong.")
            return False

    # ── "Save Login Info?" dialog ──
    try:
        save_btn = page.locator(
            "button:has-text('Save info'), "
            "button:has-text('Save Info'), "
            "button:has-text('Save your login info')"
        )
        if await save_btn.count() > 0:
            await save_btn.first.click()
            print("[session] Clicked 'Save Info'")
            await human_delay(2, 4)
            return await _resolve_post_login(page, depth + 1)
    except Exception:
        pass

    # ── "Turn on Notifications?" dialog ──
    try:
        not_now = page.locator(
            "button:has-text('Not Now'), " "button:has-text('Not now')"
        )
        if await not_now.count() > 0:
            await not_now.first.click()
            print("[session] Dismissed notifications dialog")
            await human_delay(2, 3)
            return await _resolve_post_login(page, depth + 1)
    except Exception:
        pass

    # ── Unknown state — take screenshot, try to continue ──
    await _screenshot(page, f"unknown_step_{depth}")
    print(f"[session] Unknown post-login state. URL: {current_url}")

    # Give it one more chance — maybe a redirect is pending
    await human_delay(3, 5)
    if _is_feed_url(page.url):
        print("[session] ✓ Reached feed after wait")
        return True

    print("[session] Could not resolve post-login state.")
    return False


def _is_feed_url(url: str) -> bool:
    """Check if URL looks like the authenticated feed/home."""
    # Feed URL is just instagram.com/ or instagram.com with no login/challenge path
    if "/accounts/" in url or "/challenge" in url:
        return False
    from urllib.parse import urlparse

    path = urlparse(url).path
    return (
        path in ("/", "") or path.startswith("/explore") or path.startswith("/direct")
    )


# ── Challenge Handling ─────────────────────────────────


async def _is_challenge_page(page: Page) -> bool:
    """Detect if the current page is a challenge/2FA verification page."""
    # Check URL
    if "/challenge" in page.url or "/two_factor" in page.url:
        return True

    # Check page content for challenge indicators (case-insensitive)
    indicators = page.locator(
        ':text("Check your WhatsApp"), '
        ':text("Enter the code"), '
        ':text("Check your email"), '
        ':text("Security Code"), '
        ':text("security code"), '
        ':text("verification code"), '
        ':text("Two-factor authentication"), '
        ':text("two-factor authentication"), '
        ':text("authentication app"), '
        ':text("login code"), '
        ':text("Confirm your account"), '
        ':text("We detected an unusual login"), '
        ':text("suspicious login"), '
        'input[placeholder="Security Code"], '
        'input[placeholder="Security code"]'
    )
    return await indicators.count() > 0


async def _handle_challenge(page: Page) -> bool:
    """Handle Instagram challenge/2FA interactively."""

    await _screenshot(page, "challenge_detected")
    print("[session] ⚠ Challenge/2FA detected!")

    if not _is_interactive():
        print("[session] Non-interactive mode — cannot resolve challenge.")
        print(
            "[session] Run locally first: python main.py automate --account YOUR_USER"
        )
        print("[session] Then copy data/sessions/ to VPS.")
        return False

    # Show what type of challenge
    page_text = await page.locator("body").text_content() or ""
    if "WhatsApp" in page_text:
        print("[session] Type: WhatsApp code")
    elif "email" in page_text.lower():
        print("[session] Type: Email code")
    elif "SMS" in page_text.lower() or "text message" in page_text.lower():
        print("[session] Type: SMS code")
    else:
        print("[session] Type: Unknown verification")

    print("[session] Check your device and enter the code below.")
    print()

    code = input("  Enter verification code (or 'skip' to abort): ").strip()

    if not code or code.lower() == "skip":
        print("[session] Skipped challenge.")
        return False

    # Find the code input field
    code_input = page.locator(
        'input[name="verificationCode"], '
        'input[aria-label*="code" i], '
        'input[aria-label*="Code"], '
        'input[placeholder*="Code"], '
        'input[placeholder*="code"], '
        'input[name="security_code"], '
        'input[type="number"], '
        'input[type="tel"]'
    )

    if await code_input.count() == 0:
        # Broader fallback — find any visible text/number input
        code_input = page.locator(
            'input[type="text"]:visible, '
            'input[type="number"]:visible, '
            'input[type="tel"]:visible'
        )

    if await code_input.count() == 0:
        print("[session] Cannot find code input field")
        await _screenshot(page, "challenge_no_input")
        return False

    # Clear and type the code
    target_input = code_input.first
    await target_input.click()
    await target_input.fill("")
    await human_delay(0.3, 0.5)
    await human_type(page, code)
    await human_delay(0.5, 1)

    # Ensure "Trust this device" checkbox is checked
    try:
        checkbox = page.locator('input[type="checkbox"]')
        if await checkbox.count() > 0:
            if not await checkbox.first.is_checked():
                await checkbox.first.click()
                print("[session] Checked 'Trust this device'")
                await human_delay(0.3, 0.5)
    except Exception:
        pass

    # Click submit button
    submit_btn = page.locator(
        'button:has-text("Continue"), '
        'button:has-text("Confirm"), '
        'button:has-text("Submit"), '
        'button:has-text("Verify"), '
        'button:has-text("Next"), '
        'button[type="button"]:visible'
    )

    try:
        await submit_btn.first.wait_for(state="visible", timeout=5000)
        await submit_btn.first.click()
    except Exception:
        print("[session] Submit button not found, pressing Enter")
        await page.keyboard.press("Enter")

    print("[session] Code submitted, waiting for response...")
    await human_delay(5, 8)

    # Check if challenge is resolved by looking at what changed
    # Instead of re-running _is_challenge_page (which can false-positive on the feed),
    # check if the Security Code input is still present — if it's gone, we moved on.
    security_input = page.locator(
        'input[placeholder="Security Code"], '
        'input[placeholder="Security code"], '
        'input[name="verificationCode"], '
        'input[name="security_code"]'
    )
    still_on_challenge = await security_input.count() > 0

    if not still_on_challenge:
        print("[session] ✓ Challenge resolved!")
        return True

    # Still showing the code input — wrong code or new challenge
    await _screenshot(page, "challenge_still_active")
    print("[session] Still on challenge page — code may be wrong")

    # Offer retry
    retry = input("  Try another code? (y/n): ").strip().lower()
    if retry == "y":
        return await _handle_challenge(page)
    return False


# ── Session Check ──────────────────────────────────────


async def save_session(context: BrowserContext, username: str):
    path = get_session_path(username)
    await context.storage_state(path=str(path))
    print(f"[session] Saved session to {path}")


async def is_logged_in(page: Page) -> bool:
    """Check if we have a valid authenticated session."""
    try:
        await page.goto(settings.IG_FEED, wait_until="domcontentloaded", timeout=20000)

        # Wait for React to render something meaningful
        await human_delay(4, 6)

        current_url = page.url

        # Redirected to login = not authenticated
        if any(
            x in current_url
            for x in ["/accounts/login", "/accounts/emailsignup", "/challenge"]
        ):
            print(f"[session] Not logged in — redirected to {current_url}")
            return False

        # Login form visible = not authenticated
        login_form = page.locator(
            'input[name="username"], '
            'input[aria-label*="username" i], '
            'input[aria-label*="email" i], '
            'input[type="password"]'
        )
        if await login_form.count() > 0 and await login_form.first.is_visible():
            print("[session] Not logged in — login form visible")
            return False

        # Look for elements that only exist when authenticated
        auth_check = page.locator(
            'svg[aria-label="New post"], '
            'svg[aria-label="Search"], '
            'a[href*="/direct/inbox"], '
            'svg[aria-label="Home"]'
        )

        is_auth = await auth_check.count() > 0
        if is_auth:
            print("[session] Session is valid ✓")
        else:
            print("[session] No authenticated indicators found")

        return is_auth

    except Exception as e:
        print(f"[session] Auth check failed: {e}")
        return False
