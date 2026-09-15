/**
 * poe2 MCP server — data plumbing for the PoE2 assistant skills.
 *
 * STATUS: skeleton only. Endpoints and the reuse-vs-build split are documented in ../README.md.
 * Phase 1 fills in poe2scout pricing + the /trade2 filter tools. Nothing here talks to the network yet.
 */

const POE2SCOUT_BASE = "https://api.poe2scout.com";
const REALM = "poe2";
const USER_AGENT = "poe2-ai-tools (personal; contact: jrock2004@gmail.com)";

// TODO(Phase 1): construct an McpServer from @modelcontextprotocol/sdk and register tools:
//   get_leagues, get_currency_rates, price_item, build_trade_filter, search_trade
// TODO(Phase 2): get_my_characters (OAuth), parse_pob_code, fetch_guide
// TODO: shared fetch helper with caching + rate limiting (poe2scout ~2 req/s; /trade2 back off on 429).

export const config = { POE2SCOUT_BASE, REALM, USER_AGENT };

async function main() {
  // Placeholder entrypoint. Wire the MCP SDK stdio transport here in Phase 1.
  console.error("poe2-mcp skeleton — not yet implemented. See mcp/README.md.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
