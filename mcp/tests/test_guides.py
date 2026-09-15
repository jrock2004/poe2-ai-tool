"""Unit tests for the pure gating/extraction logic in the guide fetcher (no network)."""
from poe2_mcp.guides import (
    extract_text,
    looks_blocked,
    looks_dynamic,
    prohibited_reason,
    registrable_host,
    robots_disallows,
    robots_prohibits_ai,
)

MAXROLL_ROBOTS = """\
# Use of any robot, crawler, or other tool to scrape, harvest, extract, or retrieve any content
# Prohibited uses include text and data mining and development of artificial intelligence or machine learning software
User-agent: *
Allow: /
"""


def test_registrable_host_collapses_subdomains():
    assert registrable_host("https://news.maxroll.gg/poe2/x") == "maxroll.gg"
    assert registrable_host("https://www.poe-vault.com/guides") == "poe-vault.com"


def test_prohibited_host_is_refused():
    assert prohibited_reason("https://maxroll.gg/poe2/build-guides") is not None
    assert prohibited_reason("https://sub.maxroll.gg/x") is not None
    assert prohibited_reason("https://www.poe-vault.com/guides") is None


def test_robots_ai_prohibition_detected_even_when_disallow_allows():
    # robots technically Allows /, but the preamble prohibits AI/scraping use.
    assert robots_prohibits_ai(MAXROLL_ROBOTS) is True
    assert robots_disallows(MAXROLL_ROBOTS, "poe2-ai-tools/0.1", "https://maxroll.gg/x") is False


def test_robots_disallow_is_respected():
    robots = "User-agent: *\nDisallow: /private\n"
    assert robots_disallows(robots, "poe2-ai-tools/0.1", "https://x.com/private/g") is True
    assert robots_disallows(robots, "poe2-ai-tools/0.1", "https://x.com/public/g") is False


def test_looks_blocked_on_status_and_cloudflare():
    assert looks_blocked(403, "", {}) is True
    assert looks_blocked(200, "<html>Just a moment...</html>", {}) is True
    assert looks_blocked(200, "<html>ok</html>", {"cf-mitigated": "challenge"}) is True
    # a plain cf-ray header on a real 200 page is NOT a block (poe-vault sits behind Cloudflare too)
    assert looks_blocked(200, "<html><body>Real guide content</body></html>", {"cf-ray": "abc"}) is False


def test_looks_dynamic_on_placeholder_and_empty_shell():
    assert looks_dynamic("<div>Fetching data...</div>", 40) is True
    assert looks_dynamic("x" * 30000, 100) is True  # big shell, little text
    assert looks_dynamic("<p>plenty of real content here</p>", 2000) is False


def test_extract_text_strips_chrome():
    html = """
    <html><head><style>.x{}</style></head>
    <body><nav>menu menu</nav>
      <main><h1>Ice Shot Deadeye</h1><p>Cap your resistances first.</p></main>
      <footer>footer links</footer>
      <script>console.log('x')</script>
    </body></html>
    """
    text = extract_text(html)
    assert "Ice Shot Deadeye" in text
    assert "Cap your resistances first." in text
    assert "menu menu" not in text
    assert "footer links" not in text
