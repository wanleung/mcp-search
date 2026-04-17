import json
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch
from fastmcp import FastMCP

from cache import cache_get, cache_set
from page_fetcher import fetch_page
from scraper import ddg_search, scrape_google

load_dotenv()

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
SEARCH_TTL = 86400    # 24 hours
PAGE_TTL = 604800     # 7 days

mcp = FastMCP("google_search_mcp")
es = AsyncElasticsearch(ES_URL)


def format_search_results(results: list[dict], response_format: str, cache_hit: bool = False) -> str:
    """Format a list of search result dicts into a string response.

    Args:
        results: List of dicts with keys 'title', 'url', and optionally 'snippet'.
        response_format: 'markdown' or 'json'.
        cache_hit: Whether these results came from the cache.

    Returns:
        Formatted string representation of search results.
    """
    label = " (cached)" if cache_hit else ""
    if response_format == "json":
        return json.dumps({"results": results, "cached": cache_hit}, ensure_ascii=False)
    lines = [f"### Search Results{label}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"**{i}. [{r['title']}]({r['url']})**")
        if r.get("snippet"):
            lines.append(r["snippet"])
        lines.append("")
    return "\n".join(lines)


async def google_search_handler(
    es: AsyncElasticsearch, query: str, num_results: int, response_format: str
) -> str:
    """Core logic for searching Google, with caching and DDG fallback.

    Checks Elasticsearch cache first. On cache miss, scrapes Google.
    If Google scraping returns no results, falls back to DuckDuckGo.
    Stores fresh results in cache before returning.

    Args:
        es: AsyncElasticsearch client instance.
        query: The search query string.
        num_results: Number of results to return.
        response_format: 'markdown' or 'json'.

    Returns:
        Formatted string of search results.
    """
    cache_key = f"search:{query}:{num_results}"
    cached = await cache_get(es, cache_key)
    if cached:
        return format_search_results(cached["results"], response_format, cache_hit=True)

    try:
        results = await scrape_google(query, num_results)
    except Exception:
        results = []

    if not results:
        results = ddg_search(query, num_results)

    await cache_set(es, cache_key, {"results": results}, SEARCH_TTL)
    return format_search_results(results, response_format, cache_hit=False)


async def google_fetch_page_handler(
    es: AsyncElasticsearch, url: str, response_format: str
) -> str:
    """Core logic for fetching a web page, with caching and URL validation.

    Validates URL format, checks Elasticsearch cache, fetches page on miss,
    and stores content in cache before returning.

    Args:
        es: AsyncElasticsearch client instance.
        url: Full URL to fetch (must start with http:// or https://).
        response_format: 'markdown' or 'json'.

    Returns:
        Page content as a string, or an error message.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "Invalid URL format. Please provide a full URL starting with http:// or https://"

    cached = await cache_get(es, f"page:{url}")
    if cached:
        content = cached["content"]
        if response_format == "json":
            return json.dumps({"url": url, "content": content, "cached": True})
        return f"**(cached)**\n\n{content}"

    try:
        content = await fetch_page(url)
    except Exception as exc:
        return f"Failed to fetch page: {exc}. Check that the URL is accessible."

    await cache_set(es, f"page:{url}", {"content": content}, PAGE_TTL)
    if response_format == "json":
        return json.dumps({"url": url, "content": content, "cached": False})
    return content


@mcp.tool(
    description=(
        "Search the web using Google. Returns title, URL, and snippet for each result. "
        "Results are cached for 24 hours. Use response_format='json' for structured output."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def google_search(
    query: str,
    num_results: int = 10,
    response_format: str = "markdown",
) -> str:
    """Search the web using Google with caching and DuckDuckGo fallback.

    Args:
        query: The search query string.
        num_results: Number of results to return (1-20, default 10).
        response_format: 'markdown' (default) or 'json'.
    """
    num_results = min(max(1, num_results), 20)
    return await google_search_handler(es, query, num_results, response_format)


@mcp.tool(
    description=(
        "Fetch the full readable text content of a web page. "
        "Strips navigation, scripts, and styles. Content is cached for 7 days. "
        "Use response_format='json' for structured output."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def google_fetch_page(
    url: str,
    response_format: str = "markdown",
) -> str:
    """Fetch the readable text content of a web page.

    Args:
        url: Full URL to fetch (must start with http:// or https://).
        response_format: 'markdown' (default) or 'json'.
    """
    return await google_fetch_page_handler(es, url, response_format)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=SERVER_HOST, port=SERVER_PORT)
