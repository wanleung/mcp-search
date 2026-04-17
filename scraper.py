"""
Scraper module for mcp-google.

Provides two search backends:
- scrape_google: async Playwright-based Google scraper
- ddg_search: synchronous DuckDuckGo fallback via duckduckgo-search library
"""

import random
import urllib.parse

from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def parse_google_results(html: str) -> list[dict]:
    """Parse Google search result HTML and extract structured results.

    Args:
        html: Raw HTML string from a Google search results page.

    Returns:
        A list of dicts, each with keys: ``title``, ``url``, ``snippet``.
        Entries whose anchor href does not start with ``http`` are skipped
        (e.g. ad click-tracking URLs).
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for g in soup.select("div.g"):
        title_el = g.select_one("h3")
        link_el = g.select_one("a[href]")
        if not title_el or not link_el:
            continue
        href = link_el.get("href", "")
        if not href.startswith("http"):
            continue
        snippet = ""
        for sel in [".VwiC3b", ".IsZvec", "[data-sncf]"]:
            snippet_el = g.select_one(sel)
            if snippet_el:
                snippet = snippet_el.get_text(strip=True)
                break
        results.append({
            "title": title_el.get_text(strip=True),
            "url": href,
            "snippet": snippet,
        })
    return results


async def scrape_google(query: str, num_results: int = 10) -> list[dict]:
    """Fetch Google search results using a headless Playwright browser.

    Launches Chromium in headless mode, navigates to Google with the given
    query, and parses the resulting HTML with :func:`parse_google_results`.

    Args:
        query: The search query string.
        num_results: Approximate number of results to request from Google.

    Returns:
        A list of dicts with keys: ``title``, ``url``, ``snippet``.
    """
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={num_results}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            html = await page.content()
        finally:
            await browser.close()
    return parse_google_results(html)


def ddg_search(query: str, num_results: int = 10) -> list[dict]:
    """Search DuckDuckGo and return structured results.

    Uses the ``duckduckgo-search`` library as a fallback when Google
    scraping is unavailable or blocked.

    Args:
        query: The search query string.
        num_results: Maximum number of results to return.

    Returns:
        A list of dicts with keys: ``title``, ``url``, ``snippet``.
        Returns an empty list if any error occurs.
    """
    try:
        with DDGS() as ddgs:
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in ddgs.text(query, max_results=num_results)
            ]
    except Exception:
        return []
