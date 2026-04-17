"""
Page Fetcher Module.

Provides two core functions:
  - extract_text_from_html: pure function that strips boilerplate tags and returns
    plain text truncated to MAX_TEXT_LENGTH characters.
  - fetch_page: async function that uses Playwright to load a URL and returns
    cleaned plain text via extract_text_from_html.
"""

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

MAX_TEXT_LENGTH = 50000


def extract_text_from_html(html: str) -> str:
    """Extract readable plain text from an HTML string.

    Removes script, style, nav, header, and footer elements, then returns
    the remaining text content separated by newlines and truncated to
    MAX_TEXT_LENGTH characters.

    Args:
        html: Raw HTML string to process.

    Returns:
        Plain text with boilerplate removed, at most MAX_TEXT_LENGTH chars long.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:MAX_TEXT_LENGTH]


async def fetch_page(url: str) -> str:
    """Fetch a web page using Playwright and return its cleaned text content.

    Launches a headless Chromium browser, navigates to the given URL, waits
    for the DOM to be loaded, retrieves the full HTML, and passes it through
    extract_text_from_html.

    Args:
        url: The URL of the page to fetch.

    Returns:
        Plain text extracted from the page, at most MAX_TEXT_LENGTH chars long.

    Raises:
        playwright.async_api.TimeoutError: If the page does not load within 15 s.
        playwright.async_api.Error: For any other Playwright-level error.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            html = await page.content()
        finally:
            await browser.close()
    return extract_text_from_html(html)
