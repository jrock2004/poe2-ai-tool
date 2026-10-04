"""Robots- and license-aware guide fetcher for the poe2 assistant.

The value here is *not* brute scraping -- it's a gate that decides, per URL, whether an automated fetch
is permitted, and only then fetches and cleans the page. Current reality (re-verified Sep 2026, which
overturns the plan's older spike):

* **Mobalytics** -- Cloudflare-blocks server fetches (403) even with a browser UA -> browser-assisted
  read (the assistant opens it in a real browser; the player's own only if a bot check appears) or a
  pasted PoB code.
* **poe-vault** -- static and readable -> fetch works.
* **Maxroll** -- reachable, but its robots.txt (Ziff Davis) explicitly prohibits automated/AI use of
  the content. We respect that and refuse -> paste the PoB code / content instead.

So `fetch_guide` returns not just content but a **route**: `fetched` (we got it), or a `route` telling
the skill how to get the guide another way (`browser`, `paste`). It never bypasses a block or a policy.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

# Honest, descriptive UA -- not a spoofed browser. Where fetching is permitted (poe-vault) this works;
# where it's blocked (Mobalytics/Cloudflare) faking a browser doesn't help anyway, so we stay honest.
GUIDE_UA = os.environ.get(
    "POE2_GUIDE_USER_AGENT", "poe2-ai-tools/0.1 (personal build assistant; contact jrock2004@gmail.com)"
)

# Publishers who prohibit automated/AI use of their content in their terms/robots preamble. We refuse
# to fetch these regardless of what the robots Disallow lines technically allow -- it's their content.
PROHIBITED_HOSTS = {
    "maxroll.gg": "Maxroll (Ziff Davis) prohibits automated/AI use of its content in its robots.txt.",
}

# Substrings that signal a publisher-level no-AI / no-scraping policy in a robots.txt preamble.
_AI_PROHIBITION_MARKERS = (
    "artificial intelligence or machine learning",
    "text and data mining",
    "scrape, harvest, extract",
)

# Body phrases that mean a 2xx response is actually a bot/challenge wall, not the guide. (The mere
# presence of a `cf-ray` header is NOT a block -- most sites, poe-vault included, sit behind Cloudflare
# and serve real content; only a challenge status/body or a cf-mitigated header is an actual block.)
_BLOCK_MARKERS = ("just a moment", "attention required", "checking your browser")
_DYNAMIC_MARKERS = ("fetching data", "loading build", "please enable javascript")


def registrable_host(url: str) -> str:
    """Best-effort host match: exact host or its parent domain (so news.maxroll.gg -> maxroll.gg)."""
    host = (urlsplit(url).hostname or "").lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def prohibited_reason(url: str) -> str | None:
    """Return why a host is off-limits to automated fetch, or None."""
    return PROHIBITED_HOSTS.get(registrable_host(url))


def robots_prohibits_ai(robots_text: str) -> bool:
    """True if a robots.txt carries publisher-level no-AI / no-scraping language (in comments or terms)."""
    low = robots_text.lower()
    return any(m in low for m in _AI_PROHIBITION_MARKERS)


def robots_disallows(robots_text: str, ua: str, url: str) -> bool:
    """Standard robots Disallow check for `url` under `ua`."""
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    return not parser.can_fetch(ua, url)


def looks_blocked(status: int, html: str, headers: dict[str, str]) -> bool:
    """A response that's really a bot/challenge wall rather than the guide.

    A challenge status, a Cloudflare `cf-mitigated` header, or a challenge phrase in the body -- but
    not the plain `cf-ray` header, which is on every Cloudflare response including successful ones.
    """
    if status in (401, 403, 429, 503):
        return True
    if headers.get("cf-mitigated"):
        return True
    body = html[:4000].lower()
    return any(m in body for m in _BLOCK_MARKERS)


def looks_dynamic(html: str, text_len: int) -> bool:
    """A 2xx page whose real content loads client-side (little static text, or a loading placeholder)."""
    low = html.lower()
    if any(m in low for m in _DYNAMIC_MARKERS):
        return True
    return text_len < 500 and len(html) > 20000  # big shell, little readable text


def extract_text(html: str) -> str:
    """Strip chrome (script/style/nav/header/footer) and return the page's readable text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "svg"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    # collapse runs of blank lines
    lines = [ln.strip() for ln in text.splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


class GuideFetcher:
    def __init__(self, timeout_s: float = 20.0):
        self._client = httpx.Client(
            headers={"User-Agent": GUIDE_UA, "Accept": "text/html,application/xhtml+xml"},
            timeout=timeout_s,
            follow_redirects=True,
        )
        self._robots_cache: dict[str, str] = {}

    def close(self) -> None:
        self._client.close()

    def _robots_text(self, url: str) -> str:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots_cache:
            try:
                r = self._client.get(f"{origin}/robots.txt")
                self._robots_cache[origin] = r.text if r.status_code == 200 else ""
            except httpx.HTTPError:
                self._robots_cache[origin] = ""
        return self._robots_cache[origin]

    def fetch(self, url: str, max_chars: int = 20000) -> dict[str, object]:
        """Gate, then fetch. Returns a dict describing what happened and how to proceed."""
        reason = prohibited_reason(url)
        if reason:
            return _routed("paste", url, reason + " Paste the guide's PoB code or its text instead.")

        robots = self._robots_text(url)
        if robots and robots_prohibits_ai(robots):
            return _routed(
                "paste", url,
                "This site's robots.txt prohibits automated/AI use of its content. "
                "Paste the guide's PoB code or its text instead.",
            )
        if robots and robots_disallows(robots, GUIDE_UA, url):
            return _routed("paste", url, "Blocked by robots.txt. Paste the PoB code or the guide text.")

        try:
            resp = self._client.get(url)
        except httpx.HTTPError as e:
            return _routed("paste", url, f"Couldn't reach the page ({type(e).__name__}). Paste the guide instead.")

        headers = {k.lower(): v for k, v in resp.headers.items()}
        if looks_blocked(resp.status_code, resp.text, headers):
            return _routed(
                "browser", url,
                f"The site blocks automatic fetches (HTTP {resp.status_code}), so I'll open it in a browser "
                "and read it there. If it asks to verify you're human, open the guide in your own "
                "browser, or paste its PoB code.",
            )

        text = extract_text(resp.text)
        dynamic = looks_dynamic(resp.text, len(text))
        return {
            "url": url,
            "fetched": True,
            "route": None,
            "partial": dynamic,
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
            "note": (
                "Some of this guide loads client-side, so detail (e.g. gem/gear tables) may be missing; "
                "paste the PoB code for the exact build if needed."
                if dynamic else
                "Static fetch OK. Structure it into stages by level/act (see the guide model in the plan)."
            ),
        }


def _routed(route: str, url: str, note: str) -> dict[str, object]:
    return {"url": url, "fetched": False, "route": route, "content": None, "note": note}
