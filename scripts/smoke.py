"""Smoke-test the poe2 MCP server the way the plugin runs it.

Launches `uv run --no-dev --project mcp poe2-mcp` over stdio, as `.claude-plugin/plugin.json` does, with a
throwaway data dir so the player's own roster, currency and league are never read or written, and -- like the
plugin -- its own environment, built fresh from `uv.lock` each run (without one, `uv run` would rebuild the
dev venv, `mcp/.venv`, without its test tools). Then it calls each tool once and checks the answer is
there: not an error, not empty. Exact values are pytest's job; this
catches what pure tests can't -- a snapshot missing from the package, a broken runtime dependency, a tool
gone from the server, a regenerated snapshot that loads but comes back empty.

Run it from the repo root, e.g. after a per-patch refresh:

    mcp/.venv/bin/python scripts/smoke.py        # Windows: mcp\\.venv\\Scripts\\python scripts\\smoke.py

The default checks are offline. `--live` adds one call to each price tool (poe2scout) and the trade
stat lookup; `--trade` also runs one trade search (the trade site's undocumented endpoint, so only on
request). They use the first current league `get_leagues` lists, or `--league NAME`.

Prints one line per check, then the patch each snapshot reports. Exits 1 if any check failed.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import tempfile
import zlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).resolve().parent.parent
PROJECT = REPO / "mcp"
DATA = PROJECT / "src" / "poe2_mcp" / "data"
TOOLS = {
    "get_leagues", "set_league", "get_knowledge", "save_knowledge", "get_state", "update_state",
    "get_currency_prices", "market_movers", "price_unique", "value_currency", "find_stat_filters",
    "build_trade_filter", "search_trade", "fetch_guide", "parse_pob_code", "summarize_tree",
    "get_stash_layout", "mod_tiers", "item_text", "trial_pool", "campaign_rewards", "build_vendor_regex",
    "write_build_plan", "remove_build_plans",
}
KNOWLEDGE = ("trials", "farming", "crafting")


class Failed(Exception):
    """A tool answered with an error, or without what the check looks for."""


class Smoke:
    def __init__(self, session: ClientSession) -> None:
        self.session = session
        self.failures = 0
        self.patches: dict[str, str] = {}
        self.league: str | None = None

    async def call(self, tool: str, **args: Any) -> Any:
        result = await self.session.call_tool(tool, args)
        if result.isError:
            raise Failed(result.content[0].text if result.content else "error")
        out = result.structuredContent or {}
        if set(out) == {"result"}:  # a tool that returns a list comes back wrapped
            return out["result"]
        if out.get("valid") is False:
            raise Failed(out.get("error", "not valid"))
        return out

    async def check(self, label: str, run: Callable[[], Awaitable[str]]) -> None:
        try:
            detail = await run()
        except Exception as e:  # a smoke run reports every failure and carries on
            self.failures += 1
            print(f"FAIL {label} -- {str(e).splitlines()[0] if str(e) else type(e).__name__}")
        else:
            print(f"OK   {label} -- {detail}")


def tree_sample() -> tuple[str, dict[int, str]]:
    """The newest tree snapshot's version, and one keystone and two notables from it (id -> name)."""
    path = max(DATA.glob("tree_*.json"), key=lambda p: tuple(int(n) for n in p.stem[len("tree_"):].split("_")))
    nodes = json.loads(path.read_text(encoding="utf-8"))["nodes"]
    plain = [(int(i), n) for i, n in nodes.items() if not n["ascendancy"]]
    keystones = [(i, n["name"]) for i, n in plain if n["kind"] == "keystone"][:1]
    notables = [(i, n["name"]) for i, n in plain if n["kind"] == "notable"][:2]
    return path.stem[len("tree_"):], dict(keystones + notables)


def pob_code(version: str, node_ids: list[int]) -> str:
    """A minimal Path of Building 2 export code allocating `node_ids` on tree `version`."""
    xml = (f'<PathOfBuilding2><Build level="70" className="Ranger" ascendClassName="Deadeye"/>'
           f'<Tree activeSpec="1"><Spec title="Smoke" treeVersion="{version}" '
           f'nodes="{",".join(map(str, node_ids))}"/></Tree></PathOfBuilding2>')
    return base64.urlsafe_b64encode(zlib.compress(xml.encode("utf-8"))).decode("ascii")


def named(block: dict[str, Any], expected: dict[int, str]) -> str:
    names = {n["name"] for n in block["keystones"] + block["notables"]}
    missing = sorted(set(expected.values()) - names)
    if missing:
        raise Failed(f"not named: {', '.join(missing)}")
    return f"named {len(expected)} nodes"


def nonempty(count: int, what: str) -> str:
    if not count:
        raise Failed(f"no {what}")
    return f"{count} {what}"


def fresh(out: dict[str, Any], detail: str) -> str:
    """`detail`, after checking the answer says how old its data is (every market tool should)."""
    if not isinstance(out.get("ageSeconds"), (int, float)):
        raise Failed("no ageSeconds")
    return f"{detail}, {out['ageSeconds']}s old"


async def offline_checks(s: Smoke) -> None:
    async def tools() -> str:
        names = {t.name for t in (await s.session.list_tools()).tools}
        if names != TOOLS:
            raise Failed(f"missing {sorted(TOOLS - names)}, unexpected {sorted(names - TOOLS)}")
        return f"{len(names)} tools"

    version, sample = tree_sample()
    s.patches["tree"] = version

    async def summarize() -> str:
        return named(await s.call("summarize_tree", main=list(sample), tree_version=version), sample)

    async def parse_pob() -> str:
        out = await s.call("parse_pob_code", code=pob_code(version, list(sample)))
        return named(out["tree"], sample)

    async def build_plan() -> str:
        # Into a throwaway game folder; also checks the item snapshot names every sampled tree node.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as documents:
            game = Path(documents) / "My Games" / "Path of Exile 2"
            game.mkdir(parents=True)
            out = await s.call("write_build_plan", code=pob_code(version, list(sample)), name="Smoke", folder=str(game))
            if out["status"] != "written":
                raise Failed(out.get("error") or out["status"])
            unmapped = [x["what"] for x in out["plans"][0]["leftOut"] if x["why"] == "unmapped-passive"]
            if unmapped or not list((game / "BuildPlanner").glob("*.build")):
                raise Failed(f"unmapped: {', '.join(unmapped)}" if unmapped else "no .build file written")
            removed = await s.call("remove_build_plans", files=[out["plans"][0]["file"]])
            if removed.get("removed") != [out["plans"][0]["file"]] or list((game / "BuildPlanner").glob("*.build")):
                raise Failed(f"plan not removed: {removed}")
            return f"{out['plans'][0]['passives']} passives planned, then removed"

    async def mod_tiers() -> str:
        out = await s.call("mod_tiers", base="Cavalry Boots")
        s.patches["items"] = out["patch"]
        return nonempty(sum(len(v["families"]) for v in out["variants"]), "mod families on Cavalry Boots")

    async def item_text() -> str:
        out = await s.call("item_text", search="Chaos Orb")
        if not any(m.get("name") == "Chaos Orb" for m in out["matches"]):
            raise Failed("Chaos Orb not among the matches")
        return f"{out['total']} matches"

    async def trial(name: str) -> str:
        return nonempty((await s.call("trial_pool", trial=name))["total"], "entries")

    async def vendor_regex() -> str:
        regex = (await s.call("build_vendor_regex", want=[{"key": "movement_speed"}]))["regex"]
        return nonempty(len(regex), "characters of regex")

    async def stash() -> str:
        out = await s.call("get_stash_layout", tab="currency")
        s.patches["stash layouts"] = out["patch"]
        return nonempty(len(out["rows"]), "rows")

    async def campaign() -> str:
        out = await s.call("campaign_rewards", search="resistance")
        s.patches["campaign"] = out["patch"]
        return nonempty(out["total"], "resistance rewards")

    async def knowledge(topic: str) -> str:
        out = await s.call("get_knowledge", topic=topic)
        s.patches[f"knowledge {topic}"] = out["patch"]
        return nonempty(len(out["text"]), "characters")

    async def trade_filter() -> str:
        out = await s.call("build_trade_filter", category="armour.boots",
                           stats=[{"id": "explicit.stat_3299347043", "min": 50}])
        if "query" not in out:
            raise Failed("no query")
        return "query built"

    await s.check("server: tools registered", tools)
    await s.check(f"summarize_tree ({version})", summarize)
    await s.check("parse_pob_code", parse_pob)
    await s.check("write_build_plan", build_plan)
    await s.check("mod_tiers", mod_tiers)
    await s.check("item_text", item_text)
    for name in ("chaos", "sekhemas"):
        await s.check(f"trial_pool {name}", lambda name=name: trial(name))
    await s.check("build_vendor_regex", vendor_regex)
    await s.check("get_stash_layout currency", stash)
    await s.check("campaign_rewards", campaign)
    for topic in KNOWLEDGE:
        await s.check(f"get_knowledge {topic}", lambda topic=topic: knowledge(topic))
    await s.check("build_trade_filter", trade_filter)


async def live_checks(s: Smoke, league: str | None, trade: bool) -> None:
    async def leagues() -> str:
        current = [row["league"] for row in await s.call("get_leagues") if row["current"]]
        if not current:
            raise Failed("no current league")
        s.league = league or current[0]
        return f"{len(current)} current; using {s.league}" + ("" if league else " (first current; --league picks)")

    async def currency_prices() -> str:
        out = await s.call("get_currency_prices", category="currency", league=s.league)
        return fresh(out, nonempty(len(out["items"]), "currency prices"))

    async def movers() -> str:
        out = await s.call("market_movers", league=s.league)
        return fresh(out, nonempty(len(out["categories"]), "categories ranked"))

    async def price() -> str:
        out = await s.call("price_unique", name="Divine Orb", league=s.league)
        if not out["match"] or not out["priceExalted"]:
            raise Failed("Divine Orb not priced")
        return fresh(out, f"Divine Orb {out['priceExalted']:.1f} ex")

    async def value() -> str:
        out = await s.call("value_currency", holdings=[{"name": "Divine Orb", "count": 2}], league=s.league)
        if out["unmatched"] or not out["totalExalted"]:
            raise Failed("2 Divine Orbs not valued")
        return fresh(out, f"2 Divine Orbs {out['totalExalted']} ex")

    stat_ids: list[str] = []

    async def stat_filters() -> str:
        matches = (await s.call("find_stat_filters", affix="+# to maximum Life"))["matches"]
        stat_ids.extend(m["id"] for m in matches[:1])
        return nonempty(len(matches), "stat filters for +# to maximum Life")

    async def search() -> str:
        if not stat_ids:
            raise Failed("no stat id to search with (find_stat_filters failed)")
        query = (await s.call("build_trade_filter", category="armour.boots",
                              stats=[{"id": stat_ids[0], "min": 50}]))["query"]
        out = await s.call("search_trade", query=query, league=s.league, limit=1)
        if not out["url"]:
            raise Failed("no search link")
        return fresh(out, f"{out['matched']} matched")

    await s.check("get_leagues", leagues)
    await s.check("get_currency_prices currency", currency_prices)
    await s.check("market_movers", movers)
    await s.check("price_unique", price)
    await s.check("value_currency", value)
    await s.check("find_stat_filters", stat_filters)
    if trade:
        await s.check("search_trade", search)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the poe2 MCP server the way the plugin runs it.")
    parser.add_argument("--live", action="store_true", help="also call the price tools and the trade stat lookup")
    parser.add_argument("--trade", action="store_true", help="also run one trade search (implies --live)")
    parser.add_argument("--league", help="league for the live checks (default: the first current one)")
    args = parser.parse_args()
    # ignore_cleanup_errors: on Windows the just-closed server can briefly hold files in its venv.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch, \
            tempfile.TemporaryFile("w+", encoding="utf-8") as log:
        data_dir = Path(scratch) / "data"
        data_dir.mkdir()
        server = StdioServerParameters(
            command="uv", args=["run", "--quiet", "--no-dev", "--project", str(PROJECT), "poe2-mcp"],
            env={**os.environ, "POE2_DATA_DIR": str(data_dir), "UV_PROJECT_ENVIRONMENT": str(Path(scratch) / "venv")},
        )
        try:
            async with stdio_client(server, errlog=log) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                smoke = Smoke(session)
                await offline_checks(smoke)
                if args.live or args.trade:
                    await live_checks(smoke, args.league, args.trade)
        except Exception as e:  # the server didn't start, or died: its log says why
            print(f"FAIL server -- didn't start or stopped answering ({type(e).__name__})")
            return _show_log(log)
        print("Snapshots: " + ", ".join(f"{name} {patch}" for name, patch in smoke.patches.items()))
        if smoke.failures:
            print(f"\n{smoke.failures} check(s) failed.")
            return _show_log(log)
        return 0


def _show_log(log: Any) -> int:
    log.seek(0)
    print("Server log (last lines):\n" + "".join(log.readlines()[-20:]))
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
