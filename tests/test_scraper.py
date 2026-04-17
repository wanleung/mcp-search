import pytest
from unittest.mock import patch, MagicMock
from scraper import parse_google_results, ddg_search, scrape_google

SAMPLE_GOOGLE_HTML = """
<html><body>
<div id="search">
  <div class="g">
    <h3>Python Programming</h3>
    <a href="https://python.org">Python.org</a>
    <div class="VwiC3b">Python is a programming language.</div>
  </div>
  <div class="g">
    <h3>Learn Python</h3>
    <a href="https://learnpython.org">LearnPython.org</a>
    <div class="VwiC3b">Learn Python interactively.</div>
  </div>
</div>
</body></html>
"""

EMPTY_GOOGLE_HTML = "<html><body><div id='search'></div></body></html>"


def test_parse_google_results_extracts_title_url_snippet():
    results = parse_google_results(SAMPLE_GOOGLE_HTML)
    assert len(results) == 2
    assert results[0]["title"] == "Python Programming"
    assert results[0]["url"] == "https://python.org"
    assert results[0]["snippet"] == "Python is a programming language."
    assert results[1]["title"] == "Learn Python"
    assert results[1]["url"] == "https://learnpython.org"


def test_parse_google_results_returns_empty_list_for_no_results():
    results = parse_google_results(EMPTY_GOOGLE_HTML)
    assert results == []


def test_parse_google_results_skips_entries_without_http_href():
    html = """
    <html><body><div id="search">
      <div class="g">
        <h3>Ad Result</h3>
        <a href="/aclk?sa=something">Ad link</a>
        <div class="VwiC3b">Ad snippet</div>
      </div>
    </div></body></html>
    """
    results = parse_google_results(html)
    assert results == []


def test_ddg_search_maps_fields_correctly():
    with patch("scraper.DDGS") as mock_ddgs_class:
        mock_ddgs = MagicMock()
        mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "DDG Result", "href": "http://ddg.com", "body": "A result from DDG"}
        ]
        results = ddg_search("python", num_results=1)
    assert len(results) == 1
    assert results[0] == {
        "title": "DDG Result",
        "url": "http://ddg.com",
        "snippet": "A result from DDG",
    }


def test_ddg_search_returns_empty_on_error():
    with patch("scraper.DDGS") as mock_ddgs_class:
        mock_ddgs_class.side_effect = Exception("DDG unreachable")
        results = ddg_search("python", num_results=5)
    assert results == []


@pytest.mark.asyncio
async def test_scrape_google_returns_parsed_results():
    """scrape_google should launch Playwright, fetch Google, and return parsed results."""
    from unittest.mock import AsyncMock

    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value=SAMPLE_GOOGLE_HTML)
    mock_page.goto = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("scraper.async_playwright") as mock_apw:
        mock_apw.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_apw.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await scrape_google("python", num_results=2)

    assert len(results) >= 1
    assert results[0]["url"].startswith("http")


def test_parse_google_results_empty_snippet_when_no_snippet_element():
    html = """<html><body><div class="g">
        <h3>No Snippet</h3>
        <a href="https://example.com">link</a>
    </div></body></html>"""
    results = parse_google_results(html)
    assert len(results) == 1
    assert results[0]["snippet"] == ""
