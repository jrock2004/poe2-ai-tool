# GGG OAuth client application (draft — PARKED)

> **STATUS as of 2026-09-15: DO NOT SEND. GGG registration is closed.** The developer docs
> (`pathofexile.com/developer/docs`) state under *Registering your Application*: **"We are currently
> unable to process new applications."** So OAuth character-read is unobtainable right now, full stop
> — not just slow or discretionary. Character reading uses **PoB paste / screenshot** instead (that is
> now the design primary, not a fallback). This draft is kept ready so we can send it the moment the
> registration door reopens; check that docs page periodically.

Send to **support@grindinggear.com** (the only contact GGG surfaces for this). Registration is
manual and discretionary — approval is not guaranteed and GGG explicitly discourages third-party
tools, so keep the ask small, honest, read-only, and single-user. Everything below is deliberately
scoped to the *minimum* that makes character-read work.

Fill in the two placeholders (`[POE_ACCOUNT_NAME]`, and a redirect port if you don't like 8180)
before sending — **once registration reopens.**

---

**Subject:** OAuth client request — personal, read-only PoE 2 character access (public/PKCE)

Hello,

I'd like to request an OAuth `client_id` for a **personal, non-commercial** tool that reads only my
own Path of Exile 2 character data. It's a single-user assistant I run locally to help me make gearing
and build decisions; it is not a hosted service and has no other users.

Details for registration:

- **Account:** [POE_ACCOUNT_NAME]
- **Client type:** public client — Authorization Code grant with **PKCE**, no client secret.
- **Redirect URI:** `http://127.0.0.1:8180/callback` (loopback only).
- **Scope requested:** `account:characters` only. (No `service:*` scopes, no stash scopes.)
- **Realm:** `poe2` — I use `GET /character/poe2` and `GET /character/poe2/<name>` to read my own
  characters' equipment and passives.
- **Usage:** read-only. The tool never trades, whispers, lists items, or takes any action on my
  account. It fetches my character data on demand for my own analysis and caches it.
- **Etiquette:** it sends a descriptive `User-Agent` identifying the app and my contact email, and it
  respects the documented rate limits and any `Retry-After` / rate-limit headers.

If a public/PKCE client for personal use isn't something you issue, no problem — I'll use manual
Path of Building exports instead. Either way, thanks for your time and for the API docs.

Best,
John Costanzo
jrock2004@gmail.com

---

## After you get a client_id

Set these where the MCP server can read them (env, not committed):

```
POE2_OAUTH_CLIENT_ID=<the client_id GGG issues>
POE2_OAUTH_REDIRECT=http://127.0.0.1:8180/callback
```

No client secret — a public/PKCE client doesn't use one. The OAuth code I'm staging will pick these
up and do the browser-based auth-code + PKCE exchange, storing the refresh token locally.

## If GGG says no (or goes silent)

That's the expected case, not a failure. Character reading falls back to **PoB paste / character
screenshot**, which needs no approval and is wired in as the default. OAuth upgrades it transparently
if/when a client_id ever lands — no change to how you use the skills.
