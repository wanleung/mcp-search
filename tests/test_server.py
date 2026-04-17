import pytest
from unittest.mock import AsyncMock, patch

# Import handler functions (not the mcp tool decorators)
from server import google_search_handler, google_fetch_page_handler, format_search_results


@pytest.fixture
def mock_es():
    return AsyncMock()


async def test_google_search_returns_cached_result(mock_es):
    cached_data = {
        "results": [{"title": "Cached", "url": "https://cached.com", "snippet": "cached snippet"}]
    }
    with patch("server.cache_get", new=AsyncMock(return_value=cached_data)):
        result = await google_search_handler(mock_es, "python", num_results=5, response_format="markdown")
    assert "Cached" in result
    assert "https://cached.com" in result
    assert "(cached)" in result


async def test_google_search_scrapes_on_cache_miss(mock_es):
    scrape_results = [{"title": "Scraped", "url": "https://scraped.com", "snippet": "scraped snippet"}]
    with patch("server.cache_get", new=AsyncMock(return_value=None)), \
         patch("server.scrape_google", new=AsyncMock(return_value=scrape_results)), \
         patch("server.cache_set", new=AsyncMock()):
        result = await google_search_handler(mock_es, "python", num_results=1, response_format="markdown")
    assert "Scraped" in result
    assert "https://scraped.com" in result


async def test_google_search_falls_back_to_ddg_on_empty_scrape(mock_es):
    ddg_results = [{"title": "DDG Result", "url": "http://ddg.com", "snippet": "ddg snippet"}]
    with patch("server.cache_get", new=AsyncMock(return_value=None)), \
         patch("server.scrape_google", new=AsyncMock(return_value=[])), \
         patch("server.ddg_search", return_value=ddg_results), \
         patch("server.cache_set", new=AsyncMock()):
        result = await google_search_handler(mock_es, "python", num_results=1, response_format="markdown")
    assert "DDG Result" in result


async def test_google_search_returns_no_results_message_when_both_sources_empty(mock_es):
    with patch("server.cache_get", new=AsyncMock(return_value=None)), \
         patch("server.scrape_google", new=AsyncMock(return_value=[])), \
         patch("server.ddg_search", return_value=[]), \
         patch("server.cache_set", new=AsyncMock()) as mock_cache_set:
        result = await google_search_handler(mock_es, "python", num_results=5, response_format="markdown")
    assert "No results found" in result
    mock_cache_set.assert_not_called()


async def test_google_fetch_page_returns_error_message_on_exception(mock_es):
    with patch("server.cache_get", new=AsyncMock(return_value=None)), \
         patch("server.fetch_page", new=AsyncMock(side_effect=Exception("net::ERR_CONNECTION_REFUSED"))), \
         patch("server.cache_set", new=AsyncMock()):
        result = await google_fetch_page_handler(mock_es, "https://example.com", response_format="markdown")
    assert "Failed to fetch" in result
    assert "net::ERR_CONNECTION_REFUSED" not in result  # must not leak internal details


async def test_google_fetch_page_returns_json_format_on_cache_miss(mock_es):
    import json
    with patch("server.cache_get", new=AsyncMock(return_value=None)), \
         patch("server.fetch_page", new=AsyncMock(return_value="page content")), \
         patch("server.cache_set", new=AsyncMock()):
        result = await google_fetch_page_handler(mock_es, "https://example.com", response_format="json")
    parsed = json.loads(result)
    assert parsed["url"] == "https://example.com"
    assert parsed["content"] == "page content"
    assert parsed["cached"] is False


async def test_google_search_returns_json_format(mock_es):
    cached_data = {
        "results": [{"title": "T", "url": "https://t.com", "snippet": "s"}]
    }
    with patch("server.cache_get", new=AsyncMock(return_value=cached_data)):
        result = await google_search_handler(mock_es, "python", num_results=1, response_format="json")
    import json
    parsed = json.loads(result)
    assert parsed["results"][0]["title"] == "T"


async def test_google_fetch_page_returns_cached(mock_es):
    with patch("server.cache_get", new=AsyncMock(return_value={"content": "Cached page text"})):
        result = await google_fetch_page_handler(mock_es, "https://example.com", response_format="markdown")
    assert "Cached page text" in result


async def test_google_fetch_page_rejects_invalid_url(mock_es):
    with patch("server.cache_get", new=AsyncMock(return_value=None)):
        result = await google_fetch_page_handler(mock_es, "not-a-url", response_format="markdown")
    assert "Invalid URL" in result


async def test_google_fetch_page_fetches_on_cache_miss(mock_es):
    with patch("server.cache_get", new=AsyncMock(return_value=None)), \
         patch("server.fetch_page", new=AsyncMock(return_value="Full page content here")), \
         patch("server.cache_set", new=AsyncMock()):
        result = await google_fetch_page_handler(mock_es, "https://example.com", response_format="markdown")
    assert "Full page content here" in result
