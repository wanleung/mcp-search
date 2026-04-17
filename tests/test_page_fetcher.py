import pytest
from page_fetcher import extract_text_from_html

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
    assert len(text) <= 50000
