"""Unit tests for the PoE2 patch-notes reader (no network: the fetch runs over a mock transport)."""
import asyncio
from pathlib import Path

import httpx
import pytest

from poe2_mcp.patchnotes import (
    PatchNotesClient,
    outline,
    parse_index,
    parse_thread,
    search_lines,
    section_lines,
    thread_kind,
    version_key,
)

FIXTURES = Path(__file__).parent / "patchnotes"
INDEX_1 = (FIXTURES / "index_page1.html").read_text(encoding="utf-8")
INDEX_2 = (FIXTURES / "index_page2.html").read_text(encoding="utf-8")
THREAD = (FIXTURES / "thread_staff.html").read_text(encoding="utf-8")
POINT_RELEASE = (FIXTURES / "thread_point_release.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("title, version, kind", [
    ("0.5.5 Patch Notes", "0.5.5", "content"),
    ("Content Update 0.5.0 — Path of Exile 2: Return of the Ancients", "0.5.0", "content"),
    ("0.5.5e Patch Notes", "0.5.5e", "lettered"),
    ("0.5.4e Patch Notes (restartless)", "0.5.4e", "lettered"),
    ("0.5.5 Hotfix 3", "0.5.5", "hotfix"),
    ("0.5.5 Hotfix", "0.5.5", "hotfix"),
    ("0.5.4f Hotfix", "0.5.4f", "hotfix"),
    ("0.5.3 Restart", "0.5.3", "other"),
    ("0.5.4e Maintenance", "0.5.4e", "other"),
    ("Server Maintenance", None, "other"),
    # Older titles: a dot before the letter, and a typo GGG never fixed.
    ("0.3.1.d Patch Notes", "0.3.1d", "lettered"),
    ("0.1.0 Hotifx 9", "0.1.0", "hotfix"),
    # 1.0 may be titled with two parts; it reads as x.y.0 so it equals the three-part spelling.
    ("1.0 Patch Notes", "1.0.0", "content"),
    ("1.0.0 Patch Notes", "1.0.0", "content"),
    ("1.0a Patch Notes", "1.0.0a", "lettered"),
    ("1.0 Hotfix 2", "1.0.0", "hotfix"),
    ("Content Update 1.1 — Path of Exile 2", "1.1.0", "content"),
    # Numbers that aren't versions.
    ("Server Maintenance 12.11.2026", None, "other"),
    ("Server Maintenance 2026.12.11", None, "other"),
    ("Patch Notes: Double Loot Weekend 2.5x", None, "other"),
])
def test_thread_kind_reads_the_version_and_kind_from_the_title(title, version, kind):
    assert thread_kind(title) == {"version": version, "kind": kind}


def test_version_key_orders_a_letter_after_its_base_version():
    assert version_key("0.4.0") < version_key("0.4.0l") < version_key("0.5.0") < version_key("0.5.10")


def test_version_key_reads_a_two_part_version_as_its_x_y_0():
    assert version_key("1.0") == version_key("1.0.0") == (1, 0, 0, "")
    assert version_key("0.5.5z") < version_key("1.0") < version_key("1.0a") < version_key("1.0.1")


def test_version_key_refuses_what_is_not_a_version():
    with pytest.raises(ValueError):
        version_key("2.5x")


@pytest.mark.parametrize("forum", ["Early Access Patch Notes", "Patch Notes", "Path of Exile 2 Patch Notes"])
def test_parse_thread_drops_the_forum_name_from_the_title_whatever_it_is(forum):
    page = POINT_RELEASE.replace("<title>Early Access Patch Notes - 0.5.4 Patch Notes",
                                 f"<title>{forum} - 1.0 Restart")
    title = parse_thread(page)["title"]
    assert title == "1.0 Restart"
    assert thread_kind(title) == {"version": "1.0.0", "kind": "other"}


def test_parse_thread_keeps_a_dash_inside_the_thread_title():
    page = POINT_RELEASE.replace("0.5.4 Patch Notes - Forum", "1.0 - Hotfix 2 - Forum")
    assert parse_thread(page)["title"] == "1.0 - Hotfix 2"


def test_parse_thread_keeps_a_title_with_no_forum_name_whole():
    page = POINT_RELEASE.replace("<title>Early Access Patch Notes - ", "<title>")
    assert parse_thread(page)["title"] == "0.5.4 Patch Notes"


def test_parse_index_reads_each_thread_and_whether_there_is_a_next_page():
    index = parse_index(INDEX_1)
    assert index["next"] is True
    assert index["threads"][0] == {
        "title": "0.5.5e Patch Notes", "version": "0.5.5e", "kind": "lettered", "threadId": "4009785",
        "url": "https://www.pathofexile.com/forum/view-thread/4009785", "posted": "2026-10-05"}
    assert [t["title"] for t in index["threads"]] == [
        "0.5.5e Patch Notes", "0.5.5 Hotfix 3", "0.5.5 Patch Notes", "Server Maintenance"]
    assert parse_index(INDEX_2)["next"] is False


def test_parse_thread_gives_each_line_verbatim_with_its_section():
    thread = parse_thread(THREAD)
    assert thread["title"] == "Content Update 0.5.0 — Path of Exile 2: Return of the Ancients"
    assert thread["posted"] == "2026-05-21"
    assert {"section": "Skill Changes",
            "text": "Lightning Arrow: Multiple Lighting Beams are no longer be able to chain onto the same target."
            } in thread["lines"]
    assert {"section": "Item Changes",
            "text": "The +2 to level of Projectile Skills modifier on Quivers now has a value of +1."} in thread["lines"]


def test_parse_thread_splits_a_nested_list_item_from_its_parent():
    texts = [line["text"] for line in parse_thread(THREAD)["lines"]]
    assert "All Command Skills now have a 50% movement speed penalty during skill use (previously 70%)." in texts
    assert "Does not apply to Ice Shot." in texts


def test_parse_thread_keeps_text_between_breaks_as_lines_and_drops_the_table_of_contents():
    lines = parse_thread(THREAD)["lines"]
    texts = [line["text"] for line in lines]
    assert ("The Return of the Ancients expansion contains a new league, an overhaul to Path of Exile 2's Endgame. "
            "For more information about this expansion, check out pathofexile2.com/ancients.") in texts
    assert all(line["section"] != "Table of Contents" for line in lines)
    assert ".newsPost li" not in " ".join(texts)  # the post's own <style>


def test_parse_thread_reads_every_staff_post_once():
    # The page wrapper is a div.content too; reading it as well would repeat every line.
    texts = [line["text"] for line in parse_thread(THREAD)["lines"]]
    assert texts.count("Ice Shot: Ice Shards no longer have 25% more Freeze Buildup.") == 1
    assert any(t.startswith("Hey Exiles!") for t in texts)


def test_search_lines_keeps_lines_with_any_term_in_any_case():
    lines = parse_thread(THREAD)["lines"]
    found = search_lines(lines, ["ice shot", "QUIVERS"])
    assert [line["text"] for line in found] == [
        "Ice Shot: Ice Shards no longer have 25% more Freeze Buildup.",
        "Does not apply to Ice Shot.",
        "The +2 to level of Projectile Skills modifier on Quivers now has a value of +1.",
    ]


def test_outline_lists_each_section_in_order_with_its_line_count():
    # The overview sits under the post's title heading; the moderator's post has no heading at all.
    assert outline(parse_thread(THREAD)["lines"]) == [
        {"section": "Content Update 0.5.0 — Path of Exile 2: Return of the Ancients", "lines": 1},
        {"section": "Skill Changes", "lines": 4},
        {"section": "Ascendancy Changes", "lines": 1},
        {"section": "Ascendancy Changes / Pathfinder", "lines": 2},
        {"section": "Item Changes", "lines": 1},
        {"section": "", "lines": 1},
    ]


def test_parse_thread_reads_a_bold_line_under_the_post_title_as_its_own_section():
    # Point releases mark their sections with a bold line, not a heading, under the post's title.
    assert outline(parse_thread(POINT_RELEASE)["lines"]) == [
        {"section": "0.5.4 Patch Notes", "lines": 1},
        {"section": "Runes of Aldur Changes", "lines": 1},
        {"section": "Bug Fixes", "lines": 1},
    ]


def test_section_lines_finds_a_bold_sub_heading_by_its_own_name_or_its_heading():
    lines = parse_thread(THREAD)["lines"]
    toxicity = "The Overwhelming Toxicity Notable Passive Skill now grants 50% less Poison Duration (previously 35%)."
    assert [line["text"] for line in section_lines(lines, ["pathfinder"])] == [toxicity, "Return to top"]
    assert toxicity in [line["text"] for line in section_lines(lines, ["Ascendancy"])]


def test_section_lines_keeps_the_sections_whose_heading_contains_a_name():
    lines = parse_thread(THREAD)["lines"]
    kept = section_lines(lines, ["skill CHANGES"])
    assert {line["section"] for line in kept} == {"Skill Changes"} and len(kept) == 4


def _client(calls: list[str]) -> PatchNotesClient:
    pages = {
        "/forum/view-forum/2212": INDEX_1,
        "/forum/view-forum/2212/page/2": INDEX_2,
        "/forum/view-thread/3932540/filter-account-type/staff": THREAD,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        body = pages.get(request.url.path)
        return httpx.Response(200, text=body) if body else httpx.Response(404)

    return PatchNotesClient(min_gap_s=0, transport=httpx.MockTransport(handler))


def test_threads_pages_back_to_since_past_older_threads_posted_later():
    # 0.4.0l was posted after 0.5.0 launched: it's left out, and it doesn't stop the search short of 0.5.0.
    calls: list[str] = []
    threads = asyncio.run(_client(calls).threads(since="0.5.0")).body
    assert [t["title"] for t in threads] == [
        "0.5.5e Patch Notes", "0.5.5 Hotfix 3", "0.5.5 Patch Notes", "Server Maintenance",
        "0.5.4e Patch Notes (restartless)", "Content Update 0.5.0 — Path of Exile 2: Return of the Ancients"]
    assert calls == ["/forum/view-forum/2212", "/forum/view-forum/2212/page/2"]


def test_threads_without_since_reads_the_first_page_only():
    calls: list[str] = []
    threads = asyncio.run(_client(calls).threads()).body
    assert len(threads) == 4 and calls == ["/forum/view-forum/2212"]


@pytest.mark.parametrize("ref", ["0.5.0", "Content Update 0.5.0 — Path of Exile 2: Return of the Ancients", "3932540"])
def test_thread_finds_a_thread_by_version_title_or_id(ref):
    thread = asyncio.run(_client([]).thread(ref)).body
    assert thread["threadId"] == "3932540" and thread["version"] == "0.5.0"
    assert thread["url"] == "https://www.pathofexile.com/forum/view-thread/3932540"


def test_thread_by_version_takes_the_patch_notes_not_a_hotfix():
    # "0.5.5" names the 0.5.5 Patch Notes thread, not "0.5.5 Hotfix 3" above it on the page.
    calls: list[str] = []
    with pytest.raises(RuntimeError, match="404"):  # the fixture serves no 0.5.5 thread page
        asyncio.run(_client(calls).thread("0.5.5"))
    assert calls[-1] == "/forum/view-thread/4000864/filter-account-type/staff"


def test_thread_is_cached_after_the_first_read():
    calls: list[str] = []

    async def run():
        client = _client(calls)
        first = await client.thread("3932540")
        second = await client.thread("3932540")
        return first, second

    first, second = asyncio.run(run())
    assert second is first
    assert calls.count("/forum/view-thread/3932540/filter-account-type/staff") == 1


def test_thread_not_in_the_index_raises_lookup_error():
    with pytest.raises(LookupError, match="0.3.0"):
        asyncio.run(_client([]).thread("0.3.0"))


def test_threads_stop_after_a_run_of_older_versions():
    # Three older threads in a row end the search: page 2 is never read.
    page = INDEX_1.replace("0.5.5 Patch Notes", "0.4.0 Patch Notes").replace("0.5.5 Hotfix 3", "0.4.0 Hotfix 3")
    page = page.replace("Server Maintenance", "0.4.0 Restart")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, text=page)

    client = PatchNotesClient(min_gap_s=0, transport=httpx.MockTransport(handler))
    threads = asyncio.run(client.threads(since="0.5.5")).body
    assert [t["title"] for t in threads] == ["0.5.5e Patch Notes"] and calls == ["/forum/view-forum/2212"]


def test_patch_notes_tool_filters_by_section_and_search_and_always_gives_the_outline(monkeypatch):
    from poe2_mcp import server
    monkeypatch.setattr(server, "_patch_notes", _client([]))
    out = asyncio.run(server.patch_notes(version="3932540", sections=["Skill Changes"], search=["ice shot"]))
    assert [line["text"] for line in out["lines"]] == [
        "Ice Shot: Ice Shards no longer have 25% more Freeze Buildup.", "Does not apply to Ice Shot."]
    assert out["matched"] == 2 and out["total"] == 10
    assert [s["section"] for s in out["outline"]][:2] == [
        "Content Update 0.5.0 — Path of Exile 2: Return of the Ancients", "Skill Changes"]
    assert "ageSeconds" in out


def test_patch_notes_tool_searches_every_thread_since_a_version(monkeypatch):
    # Every staff page serves the 0.5.0 fixture's lines; the 0.5.5 Hotfix 3 thread fails to fetch.
    from poe2_mcp import server
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        path = request.url.path
        if path == "/forum/view-forum/2212":
            return httpx.Response(200, text=INDEX_1)
        if path == "/forum/view-forum/2212/page/2":
            return httpx.Response(200, text=INDEX_2)
        if path == "/forum/view-thread/4001313/filter-account-type/staff":
            return httpx.Response(503)
        return httpx.Response(200, text=THREAD)

    monkeypatch.setattr(server, "_patch_notes", PatchNotesClient(min_gap_s=0, transport=httpx.MockTransport(handler)))
    out = asyncio.run(server.patch_notes(since="0.5.0", search=["quivers"]))
    by_title = {t["title"]: t for t in out["threads"]}
    assert list(by_title) == [
        "0.5.5e Patch Notes", "0.5.5 Hotfix 3", "0.5.5 Patch Notes", "Server Maintenance",
        "0.5.4e Patch Notes (restartless)", "Content Update 0.5.0 — Path of Exile 2: Return of the Ancients"]
    quiver = "The +2 to level of Projectile Skills modifier on Quivers now has a value of +1."
    assert by_title["0.5.5 Patch Notes"]["lines"] == [{"section": "Item Changes", "text": quiver}]
    assert by_title["0.5.5 Patch Notes"]["matched"] == 1 and by_title["0.5.5 Patch Notes"]["total"] == 10
    assert "lines" not in by_title["0.5.5 Hotfix 3"] and "503" in by_title["0.5.5 Hotfix 3"]["error"]
    assert out["matched"] == 5  # one line in each thread that was read
    assert "ageSeconds" in out


def test_patch_notes_tool_lists_threads_without_reading_them_when_nothing_is_searched(monkeypatch):
    from poe2_mcp import server
    calls: list[str] = []
    monkeypatch.setattr(server, "_patch_notes", _client(calls))
    out = asyncio.run(server.patch_notes(since="0.5.0"))
    assert all("lines" not in t for t in out["threads"])
    assert not any("view-thread" in c for c in calls)


def test_threads_stop_at_an_empty_page():
    # Past its last thread the forum serves empty pages that still offer "Next".
    empty = INDEX_2.replace(INDEX_2[INDEX_2.index("<tr>"):INDEX_2.index("</tbody>")], "")
    empty = empty.replace('class="current">2</a>', 'class="current">2</a><a href="/forum/view-forum/2212/page/3">Next</a>')
    pages = {"/forum/view-forum/2212": INDEX_1, "/forum/view-forum/2212/page/2": empty}
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, text=pages.get(request.url.path, empty))

    client = PatchNotesClient(min_gap_s=0, transport=httpx.MockTransport(handler))
    assert len(asyncio.run(client.threads(since="0.1.0")).body) == 4
    assert calls == ["/forum/view-forum/2212", "/forum/view-forum/2212/page/2"]


def test_patch_notes_tool_keeps_only_the_kinds_asked_for(monkeypatch):
    from poe2_mcp import server
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        page = {"/forum/view-forum/2212": INDEX_1, "/forum/view-forum/2212/page/2": INDEX_2}.get(request.url.path)
        return httpx.Response(200, text=page or THREAD)

    monkeypatch.setattr(server, "_patch_notes", PatchNotesClient(min_gap_s=0, transport=httpx.MockTransport(handler)))
    listed = asyncio.run(server.patch_notes(since="0.5.0", kinds=["content"]))
    assert [t["title"] for t in listed["threads"]] == [
        "0.5.5 Patch Notes", "Content Update 0.5.0 — Path of Exile 2: Return of the Ancients"]
    searched = asyncio.run(server.patch_notes(since="0.5.0", kinds=["content", "lettered"], search=["quivers"]))
    assert [t["kind"] for t in searched["threads"]] == ["lettered", "content", "lettered", "content"]
    read = [c for c in calls if "view-thread" in c]
    assert sorted(set(read)) == sorted({f"/forum/view-thread/{i}/filter-account-type/staff"
                                        for i in ("4009785", "4000864", "3991222", "3932540")})
