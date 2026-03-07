import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

load_dotenv()

PROJECTIONLAB_URL = "https://app.projectionlab.com"
EMAIL = os.getenv("PROJECTIONLAB_EMAIL")
PASSWORD = os.getenv("PROJECTIONLAB_PASSWORD")
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"
CDP_PORT = os.getenv("CDP_PORT")

_playwright = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_page: Page | None = None


async def get_page() -> Page:
    global _playwright, _browser, _context, _page

    if _page is not None:
        return _page

    _playwright = await async_playwright().start()

    if CDP_PORT:
        _browser = await _playwright.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        _context = _browser.contexts[0] if _browser.contexts else await _browser.new_context()
        _page = _context.pages[0] if _context.pages else await _context.new_page()
    else:
        _browser = await _playwright.chromium.launch(headless=HEADLESS)
        _context = await _browser.new_context()
        _page = await _context.new_page()

    if "/login" in _page.url or _page.url == "about:blank":
        await _login(_page)
    return _page


async def _login(page: Page) -> None:
    await page.goto(f"{PROJECTIONLAB_URL}/login")
    if "/login" not in page.url:
        return
    await page.get_by_role("button", name="Sign in with Email").click()
    await page.get_by_placeholder("Enter your email").fill(EMAIL)
    await page.locator("input[type='password']").fill(PASSWORD)
    await page.get_by_role("button", name="Sign in").click()
    await page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
