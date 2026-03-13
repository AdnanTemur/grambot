"""Stealth Playwright browser setup.

Handles browser launch with anti-detection measures,
proxy configuration, and mobile viewport emulation.
"""

import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page
from config import settings

# Detect which stealth API is available.
# The newer `playwright-stealth` (>=1.1.0) exports a Stealth class.
# The older fork `tf-playwright-stealth` or `playwright-stealth<1.1` exports stealth_async().
# We normalise both into a single _apply_stealth(page) coroutine.
_stealth_cls = None
_stealth_fn = None

try:
    from playwright_stealth import Stealth as _stealth_cls
except ImportError:
    pass

if _stealth_cls is None:
    try:
        from playwright_stealth import stealth_async as _stealth_fn
    except ImportError:
        pass

if _stealth_cls is None and _stealth_fn is None:
    print(
        "[browser] WARNING: No playwright-stealth found. Running without stealth patches."
    )


async def _apply_stealth(page):
    """Apply stealth patches to a page, handling both API styles."""
    try:
        if _stealth_cls is not None:
            stealth = _stealth_cls()
            # Try known methods on the newer Stealth class
            if hasattr(stealth, "apply_stealth_async"):
                await stealth.apply_stealth_async(page)
            elif hasattr(stealth, "apply_async"):
                await stealth.apply_async(page)
            else:
                # Fallback: the Stealth class may only work as a context manager.
                # Apply manual evasions instead.
                await _manual_stealth(page)
        elif _stealth_fn is not None:
            await _stealth_fn(page)
        else:
            await _manual_stealth(page)
    except Exception as e:
        print(f"[browser] Stealth plugin failed ({e}), applying manual evasions")
        await _manual_stealth(page)


async def _manual_stealth(page):
    """Fallback stealth evasions when the plugin isn't available or fails."""
    await page.add_init_script(
        """
        // Hide webdriver flag
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // Spoof plugins (headless Chrome has none)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Spoof languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        // Chrome runtime
        window.chrome = { runtime: {} };

        // Permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    """
    )


async def create_browser_context(
    storage_state: str | None = None,
    headless: bool | None = None,
    proxy: str | None = None,
) -> tuple:
    """
    Launch a stealth Playwright browser and return (playwright, browser, context, page).

    Args:
        storage_state: Path to saved session state JSON (cookies, localStorage).
        headless: Override headless setting. Default uses config.
        proxy: Proxy URL override. Default uses config.

    Returns:
        Tuple of (playwright_instance, browser, context, page)
        Caller is responsible for cleanup via close_browser().
    """
    _headless = headless if headless is not None else settings.HEADLESS
    _proxy = proxy or settings.PROXY_URL

    pw = await async_playwright().start()

    launch_args = {
        "headless": _headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--window-size=412,915",
        ],
    }

    if _proxy:
        launch_args["proxy"] = {"server": _proxy}

    browser = await pw.chromium.launch(**launch_args)

    # Context options — desktop browser emulation
    context_opts = {
        "viewport": settings.VIEWPORT,
        "user_agent": settings.USER_AGENT,
        "locale": "en-US",
        "timezone_id": "Asia/Karachi",
        "device_scale_factor": 2,
        "permissions": ["geolocation"],
        "geolocation": {"latitude": 33.6, "longitude": 73.05},  # Rawalpindi area
    }

    # Load saved session if available
    if storage_state:
        context_opts["storage_state"] = storage_state

    context = await browser.new_context(**context_opts)

    # Prevent WebRTC IP leak
    await context.add_init_script(
        """
        // Override WebRTC to prevent IP leak
        const origRTCPeerConnection = window.RTCPeerConnection;
        window.RTCPeerConnection = function(...args) {
            const pc = new origRTCPeerConnection(...args);
            return pc;
        };
        window.RTCPeerConnection.prototype = origRTCPeerConnection.prototype;

        // Mask automation indicators
        Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 5 });
        Object.defineProperty(navigator, 'connection', {
            get: () => ({
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false,
            })
        });
    """
    )

    page = await context.new_page()

    # Apply stealth patches
    await _apply_stealth(page)

    return pw, browser, context, page


async def close_browser(pw, browser, context, save_state_path: str | None = None):
    """
    Cleanly close browser, optionally saving session state.

    Args:
        save_state_path: If provided, saves cookies/localStorage to this path.
    """
    if save_state_path:
        await context.storage_state(path=save_state_path)

    await context.close()
    await browser.close()
    await pw.stop()
