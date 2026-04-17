import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from page_fetcher import fetch_page, extract_text_from_html, MAX_TEXT_LENGTH

SAMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <nav>Navigation links here</nav>
  <script>var x = 1; alert('hello');</script>
  <style>.class { color: red; }</style>
  <header>Site Header</header>
  <main>
    <h1>Main Content Heading</h1>
    <p>This is the main content of the page.</p>
  </main>
  <footer>Footer content here</footer>
</body>
</html>
"""


def test_extract_text_removes_script_content():
    text = extract_text_from_html(SAMPLE_HTML)
    assert "var x = 1" not in text
    assert "alert" not in text


def test_extract_text_removes_style_content():
    text = extract_text_from_html(SAMPLE_HTML)
    assert ".class" not in text
    assert "color: red" not in text


def test_extract_text_removes_nav_header_footer():
    text = extract_text_from_html(SAMPLE_HTML)
    assert "Navigation links here" not in text
    assert "Site Header" not in text
    assert "Footer content here" not in text


def test_extract_text_preserves_main_content():
    text = extract_text_from_html(SAMPLE_HTML)
    assert "Main Content Heading" in text
    assert "This is the main content of the page." in text


def test_extract_text_truncates_at_50000_chars():
    large_html = f"<html><body><p>{'x' * 100000}</p></body></html>"
    text = extract_text_from_html(large_html)
    assert len(text) == MAX_TEXT_LENGTH


def test_extract_text_empty_html_returns_empty():
    assert extract_text_from_html("") == ""


def test_extract_text_no_body_returns_empty():
    assert extract_text_from_html("<html></html>") == ""


def test_extract_text_only_stripped_tags_returns_empty():
    assert extract_text_from_html("<nav>Nav only</nav>") == ""


@pytest.mark.asyncio
async def test_fetch_page_returns_extracted_text():
    mock_html = "<html><body><nav>Nav</nav><p>Real content</p></body></html>"
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    mock_p = MagicMock()
    mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("page_fetcher.async_playwright") as mock_pw:
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_page("https://example.com")

    assert "Real content" in result
    assert "Nav" not in result
    mock_browser.close.assert_awaited_once()
