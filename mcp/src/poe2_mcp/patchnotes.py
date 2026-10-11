"""PoE2's official patch notes, read from the pathofexile.com forum (Early Access Patch Notes, forum 2212).

Why not a general web fetch: a fetch that summarises the page cuts a long thread (0.5.0's notes are
~900 lines) and can reword what it keeps, so a "quote" from it isn't GGG's text. This reads the thread
itself and hands back every line verbatim, with the section it sits under.

Only GGG's posts are read -- the forum's staff-only view of a thread (`/filter-account-type/staff`), so
player replies never mix in. robots.txt allows the forum's index and thread pages. Etiquette: a
descriptive User-Agent, one request a second, and caching -- a thread's notes don't change once posted,
the index gains a thread every few days.
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

from ._cache import CacheEntry, Fetched

HOST = "https://www.pathofexile.com"
FORUM = "/forum/view-forum/2212"
USER_AGENT = "poe2-ai-tools (patch notes; https://github.com/jrock2004/poe2-ai-tool)"
INDEX_TTL_S = 3600.0
THREAD_TTL_S = 7 * 86400.0
MAX_PAGES = 25  # 30 threads a page: well past a year of patches
# The forum lists threads in posting order, not version order: an old league's last patch can be posted
# after the next launch (0.4.0l came four days after 0.5.0). So an older version doesn't end a search;
# this many older ones in a row do.
_OLDER_RUN = 3

# A game version, its letter maybe after a dot in older titles ("0.3.1.d Patch Notes" is 0.3.1d).
_VERSION_RE = re.compile(r"\b(\d+)\.(\d+)\.(\d+)(?:\.?([a-z]))?\b")
_HOTFIX = ("hotfix", "hotifx")  # "0.1.0 Hotifx 9" is a real title
_TITLE_SUFFIX = " - Forum - Path of Exile"
_TITLE_PREFIX = "Early Access Patch Notes - "
_HEADINGS = {"h1", "h2", "h3", "h4", "h5"}
_BLOCKS = {"div", "p", "ul", "ol", "table", "tr", "td", "blockquote"}
_SKIPPED = {"style", "script", "img", "input", "button"}
_CONTENTS = "Table of Contents"


def version_key(version: str) -> tuple[int, int, int, str]:
    """Sort key for a game version: "0.5.5e" -> (0, 5, 5, "e"). A letter sorts after its base version."""
    m = _VERSION_RE.search(version)
    if not m:
        raise ValueError(f"not a game version: {version!r}")
    return int(m[1]), int(m[2]), int(m[3]), m[4] or ""


def _version(m: re.Match[str]) -> str:
    return f"{m[1]}.{m[2]}.{m[3]}{m[4] or ''}"


def thread_kind(title: str) -> dict[str, Any]:
    """{"version", "kind"} from a thread title. Pure.

    kind: "content" -- a content update's notes (x.y.z Patch Notes, or "Content Update x.y.z — ..."),
    "lettered" -- a lettered patch's notes (0.5.5b), "hotfix", or "other" (restarts, maintenance). version
    is the first x.y.z[letter] in the title ("0.3.1.d" read as "0.3.1d"), or None ("Server Maintenance").
    """
    m = _VERSION_RE.search(title)
    version = _version(m) if m else None
    low = title.lower()
    if any(word in low for word in _HOTFIX):
        kind = "hotfix"
    elif version and ("patch notes" in low or "content update" in low):
        kind = "lettered" if m[4] else "content"
    else:
        kind = "other"
    return {"version": version, "kind": kind}


def _posted(text: str) -> str | None:
    """"May 21, 2026, 7:30:00 PM" (the forum's format, maybe after ", ") -> "2026-05-21"; None if it isn't."""
    try:
        return datetime.strptime(text.strip(" ,"), "%b %d, %Y, %I:%M:%S %p").date().isoformat()
    except ValueError:
        return None


def _thread_url(thread_id: str) -> str:
    return f"{HOST}/forum/view-thread/{thread_id}"


def parse_index(html: str) -> dict[str, Any]:
    """One page of the patch-notes forum: {"threads": [...], "next": bool}, threads in the page's order
    (newest first). Pure. Each thread: {"title", "version", "kind", "threadId", "url", "posted"}."""
    soup = BeautifulSoup(html, "html.parser")
    threads = []
    for row in soup.select("table.viewForumTable tr"):
        link = row.select_one(".thread_title .title a")
        if link is None:
            continue
        title = " ".join(link.get_text().split())
        thread_id = link.get("href", "").rstrip("/").rsplit("/", 1)[-1]
        date = row.select_one(".postBy .post_date")
        threads.append({"title": title, **thread_kind(title), "threadId": thread_id,
                        "url": _thread_url(thread_id), "posted": _posted(date.get_text()) if date else None})
    has_next = any(a.get_text(strip=True) == "Next" for a in soup.select(".pagination a"))
    return {"threads": threads, "next": has_next}


def _clean(text: str) -> str:
    return " ".join(text.split())


def _lines(node: Tag, section: str, out: list[dict[str, str]]) -> str:
    """Walk a post's HTML into lines: a list item, a heading's section, or text between line breaks and
    blocks. Returns the section in force after `node`. The table of contents is the list under its
    heading; after it the section before it resumes."""
    buffer: list[str] = []
    before_contents = section

    def flush() -> None:
        text = _clean("".join(buffer))
        buffer.clear()
        if text and section != _CONTENTS:
            out.append({"section": section, "text": text})

    for child in node.children:
        if isinstance(child, NavigableString):
            if type(child) is NavigableString:  # not a comment or doctype
                buffer.append(str(child))
            continue
        if not isinstance(child, Tag) or child.name in _SKIPPED:
            continue
        if child.name == "br":
            flush()
        elif child.name in _HEADINGS:
            flush()
            heading = _clean(child.get_text())
            if heading == _CONTENTS:
                before_contents = section
            section = heading
        elif child.name == "li":
            flush()
            nested = [c.extract() for c in child.find_all(["ul", "ol"], recursive=False)]
            own = _clean(child.get_text())
            if own and section != _CONTENTS:
                out.append({"section": section, "text": own})
            for sub in nested:
                section = _lines(sub, section, out)
        elif child.name in ("ul", "ol") and section == _CONTENTS:
            flush()
            section = before_contents
        elif child.name in _BLOCKS:
            flush()
            section = _lines(child, section, out)
        else:  # inline: <a>, <strong>, <span> -- part of the line around it
            buffer.append(child.get_text())
    flush()
    return section


def parse_thread(html: str) -> dict[str, Any]:
    """A thread page (the staff-only view): {"title", "posted", "lines": [{"section", "text"}]}. Pure.

    Every post on the page, in order, line by line; a post's text before its first heading has section "".
    The table of contents and the post's own <style> are left out. Text is GGG's, with runs of
    whitespace collapsed to one space.
    """
    soup = BeautifulSoup(html, "html.parser")
    raw_title = soup.title.get_text() if soup.title else ""
    title = _clean(raw_title).removesuffix(_TITLE_SUFFIX).removeprefix(_TITLE_PREFIX)
    posts = [c for c in soup.select("table.forumPostListTable div.content")
             if c.find("div", class_="content") is None]
    lines: list[dict[str, str]] = []
    for post in posts:
        _lines(post, "", lines)
    date = soup.select_one("table.forumPostListTable .post_date")
    return {"title": title, "posted": _posted(date.get_text()) if date else None, "lines": lines}


def search_lines(lines: list[dict[str, str]], terms: list[str]) -> list[dict[str, str]]:
    """The lines containing any of `terms`, in any case, in their order. Pure."""
    wanted = [t.lower() for t in terms if t.strip()]
    return [line for line in lines if any(t in line["text"].lower() for t in wanted)]


def section_lines(lines: list[dict[str, str]], names: list[str]) -> list[dict[str, str]]:
    """The lines whose section heading contains any of `names`, in any case, in their order. Pure."""
    wanted = [n.lower() for n in names if n.strip()]
    return [line for line in lines if any(n in line["section"].lower() for n in wanted)]


def outline(lines: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Each section in the order it first appears, with how many lines it has: [{"section", "lines"}].
    Pure. A content update's overview sits under the post's own title heading."""
    counts: dict[str, int] = {}
    for line in lines:
        counts[line["section"]] = counts.get(line["section"], 0) + 1
    return [{"section": name, "lines": n} for name, n in counts.items()]


class PatchNotesClient:
    def __init__(self, min_gap_s: float = 1.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._last_request = 0.0
        self._min_gap_s = min_gap_s
        self._client = httpx.AsyncClient(base_url=HOST, headers={"User-Agent": USER_AGENT}, timeout=30.0,
                                         transport=transport, follow_redirects=True)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _page(self, path: str, ttl_s: float) -> Fetched[str]:
        hit = self._cache.get(path)
        if hit and hit.expires > time.monotonic():
            return hit.fetched
        gap = self._last_request + self._min_gap_s - time.monotonic()
        if gap > 0:
            await asyncio.sleep(gap)
        self._last_request = time.monotonic()
        resp = await self._client.get(path)
        if resp.status_code != 200:
            raise RuntimeError(f"pathofexile.com {path} -> HTTP {resp.status_code} {resp.reason_phrase}")
        fetched = Fetched(body=resp.text, fetched_at=time.time())
        self._cache[path] = CacheEntry(expires=time.monotonic() + ttl_s, fetched=fetched)
        return fetched

    async def _index(self, page: int) -> tuple[dict[str, Any], Fetched[str]]:
        fetched = await self._page(FORUM if page == 1 else f"{FORUM}/page/{page}", INDEX_TTL_S)
        return parse_index(fetched.body), fetched

    async def threads(self, since: str | None = None) -> Fetched[list[dict[str, Any]]]:
        """The patch-note threads, newest posted first: the first page, or -- with `since` -- every thread
        for version `since` (its lettered patches and hotfixes too) and later, paging back until
        `_OLDER_RUN` older threads in a row. Stamped with the oldest page's fetch."""
        floor = version_key(since)[:3] if since else None
        found: list[dict[str, Any]] = []
        oldest: Fetched[str] | None = None
        older = 0
        for page in range(1, MAX_PAGES + 1):
            index, fetched = await self._index(page)
            if not index["threads"]:  # past the last thread the forum serves empty pages that offer "Next"
                break
            oldest = fetched if oldest is None or fetched.fetched_at < oldest.fetched_at else oldest
            for thread in index["threads"]:
                if floor and thread["version"] and version_key(thread["version"])[:3] < floor:
                    older += 1
                    if older == _OLDER_RUN:
                        return Fetched(body=found, fetched_at=oldest.fetched_at)
                    continue
                older = 0 if thread["version"] else older
                found.append(thread)
            if floor is None or not index["next"]:
                break
        return Fetched(body=found, fetched_at=oldest.fetched_at if oldest else time.time())

    async def _find(self, ref: str) -> str:
        """A thread id for `ref`: a version ("0.5.5b" -> its Patch Notes thread), an exact title ("0.5.5
        Hotfix 3"), or a thread id. Pages back until it's found or `_OLDER_RUN` older versions in a row say
        the index is past it; LookupError if not."""
        if ref.isdigit():
            return ref
        wanted = _clean(ref).lower()
        exact = _VERSION_RE.fullmatch(wanted)
        is_version = exact is not None
        wanted = _version(exact) if exact else wanted
        floor = version_key(wanted) if is_version else None
        older = 0
        for page in range(1, MAX_PAGES + 1):
            index, _ = await self._index(page)
            if not index["threads"]:
                break
            for thread in index["threads"]:
                if is_version:
                    if thread["version"] == wanted and thread["kind"] in ("content", "lettered"):
                        return thread["threadId"]
                elif thread["title"].lower() == wanted:
                    return thread["threadId"]
                if floor and thread["version"]:
                    older = older + 1 if version_key(thread["version"]) < floor else 0
                    if older == _OLDER_RUN:
                        raise LookupError(f"no patch notes thread for {ref!r}")
            if not index["next"]:
                break
        raise LookupError(f"no patch notes thread for {ref!r}")

    async def thread(self, ref: str) -> Fetched[dict[str, Any]]:
        """One thread's notes, GGG's posts only: {"title", "version", "kind", "threadId", "url", "posted",
        "lines"}. `ref` is a version, an exact thread title, or a thread id (see `_find`)."""
        thread_id = await self._find(ref)
        fetched = await self._page(f"/forum/view-thread/{thread_id}/filter-account-type/staff", THREAD_TTL_S)
        key = f"parsed:{thread_id}"
        hit = self._cache.get(key)
        if hit and hit.fetched.fetched_at == fetched.fetched_at:
            return hit.fetched
        parsed = parse_thread(fetched.body)
        body = {"title": parsed["title"], **thread_kind(parsed["title"]), "threadId": thread_id,
                "url": _thread_url(thread_id), "posted": parsed["posted"], "lines": parsed["lines"]}
        result = Fetched(body=body, fetched_at=fetched.fetched_at)
        self._cache[key] = CacheEntry(expires=float("inf"), fetched=result)
        return result
