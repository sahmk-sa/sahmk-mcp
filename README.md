# SAHMK MCP Server

[![Official Source](https://img.shields.io/badge/Source-Official%20Only-0A66C2?style=for-the-badge)](https://github.com/sahmk-sa/sahmk-mcp)

> **Official distribution:** GitHub (`sahmk-sa/sahmk-mcp`) and PyPI (`sahmk-mcp`) only. Do not install from third-party forks.

Official SAHMK MCP server for [SAHMK](https://sahmk.sa/developers) — use Saudi market data inside AI agents such as Cursor and Claude Desktop.

This MCP exposes a curated set of Sahmk tools for AI agents, so assistants can query the Saudi market in natural language.

## Tools

| Tool | Use it for |
|------|------------|
| `get_quote` | Snapshot for one stock identifier (symbol, name, or alias) |
| `get_quotes` | Compare multiple stock identifiers in one call |
| `companies_list` | Company directory/symbol discovery with pagination |
| `get_market_summary` | Summary for `TASI` or `NOMU` |
| `get_market_movers` | Top movers by `gainers`, `losers`, `volume`, or `value` |
| `get_sectors` | Sector performance snapshot |
| `get_company` | Company profile and fundamentals |
| `get_financials` | Financial statements *(Starter+ plan)* |
| `get_ratios` | Calculated financial ratios *(Starter/Pro features vary)* |
| `compare_symbols` | Multi-symbol normalized ratio/metrics comparison *(Starter/Pro limits vary)* |
| `get_dividends` | Dividend history and yield data *(Starter+ plan)* |
| `get_depth` | Order-book depth (bid/ask ladder, spread, imbalance) *(entitlement-gated)* |
| `get_trades` | Recent live trade prints / tape *(Pro+ plan)* |
| `get_events` | AI-generated stock event summaries *(Pro+ plan)* |
| `get_historical` | Historical OHLCV data |

## Identifier-First Contract

- Canonical inputs for quote tools are `identifier` and `identifiers`.
- Legacy aliases `symbol` and `symbols` are still accepted for compatibility.
- Prefer canonical keys in prompts, tool calls, and client templates.
- Resolution is backend/SDK-backed (names, aliases, and symbols); MCP does not maintain its own symbol map.

## When to Use MCP vs SDK

- Use **MCP** for interactive agent workflows in tools like Cursor and Claude Desktop.
- Use the **Python SDK** for scripts, automation, dashboards, alerts, backtests, and application code.

SDK repo: [sahmk-sa/sahmk-python](https://github.com/sahmk-sa/sahmk-python)

## Get Your API Key

1. Sign up at [sahmk.sa/developers](https://sahmk.sa/developers)
2. Go to Dashboard → API Keys → Create Key
3. Copy your key (starts with `shmk_live_` or `shmk_test_`)

## Market Depth Access

`get_depth` is entitlement-gated. Request realtime/depth access from the developer dashboard:

[Request realtime access](https://www.sahmk.sa/developers/dashboard/realtime-access)

## Required Environment Variable

`SAHMK_API_KEY` is required for all server runs (Claude Desktop, Cursor, and direct CLI usage).  
Set it in your MCP client `env` config or export it before running `sahmk-mcp`.

## Installation

```bash
pip install sahmk-mcp
```

Requires `sahmk>=0.14.0` for current MCP-SDK compatibility, including market depth, live trades, and events tools.

## Security

- Set API keys via environment variables (`SAHMK_API_KEY`).
- Never commit keys to source control or share them in logs.
- Rotate exposed keys immediately from your Sahmk dashboard.

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sahmk": {
      "command": "sahmk-mcp",
      "env": {
        "SAHMK_API_KEY": "your_api_key"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "sahmk": {
      "command": "sahmk-mcp",
      "env": {
        "SAHMK_API_KEY": "your_api_key"
      }
    }
  }
}
```

### Run Directly

```bash
export SAHMK_API_KEY="your_api_key"
sahmk-mcp
```

## Tool Input Constraints

- `get_market_summary.index`: `TASI` or `NOMU` (`NOMUC` alias is accepted and normalized).
- `get_market_movers.type`: `gainers`, `losers`, `volume`, or `value`.
- `get_market_movers.limit`: integer from 1 to 50.
- `get_quote.identifier` *(preferred)*: accepts numeric symbol, Arabic/English company name, or known alias.
- `get_quote.symbol` *(legacy alias)*: accepted for backward compatibility.
- `get_quotes.identifiers` *(preferred)*: maximum 50 identifiers per request.
- `get_quotes.symbols` *(legacy alias)*: accepted for backward compatibility.
- `get_financials.symbol`: prefers exact exchange symbol; MCP attempts SDK-backed identifier resolution for names/aliases when possible.
- `get_financials.period` and `get_financials.statement_period`: if both are provided, `period` takes precedence.
- `get_financials` supports optional passthrough params: `type`, `period`, `statement_period`, `history`, `metrics`, `result`, and `include_partial`.
- `get_financials` response is statement-block focused and does not include `meta`.
- `get_ratios.symbol`: prefers exact exchange symbol; MCP attempts SDK-backed identifier resolution for names/aliases when possible.
- `get_ratios.history`: defaults to `latest`.
- `get_ratios.period`: defaults to `annual`.
- `get_ratios.metrics`: defaults to `core`.
- `compare_symbols.symbols`: list of symbols (preferred) or comma-separated string; MCP attempts SDK-backed identifier resolution for names/aliases when possible.
- `compare_symbols.metrics`: defaults to `core`.
- `get_ratios` and `compare_symbols` include minimal `meta` only: `period`, `metrics`, `warnings`.
- Analytics tools do not expose backend/internal fields such as `applied_profile`, `plan`, or source diagnostics.
- `get_dividends.symbol`: prefers exact exchange symbol; MCP attempts SDK-backed identifier resolution for names/aliases when possible.
- `get_depth.symbol`: prefers exact exchange symbol; MCP attempts SDK-backed identifier resolution for names/aliases when possible.
- `get_depth.levels`: optional integer from 1 to 20 (backend default is typically 5; entitlement may cap below the request).
- `get_trades.symbol`: prefers exact exchange symbol; MCP attempts SDK-backed identifier resolution for names/aliases when possible.
- `get_trades.limit`: optional integer from 1 to 200 (backend default is typically 50; newest first).
- `get_events.symbol`: optional exact exchange symbol filter; omit for market-wide recent events.
- `get_events.limit`: optional integer from 1 to 100.
- `get_historical.symbol`: prefers exact exchange symbol; MCP attempts SDK-backed identifier resolution for names/aliases when possible.
- `companies_list.market`: `TASI` or `NOMU` (`NOMUC` alias is accepted and normalized).
- `companies_list.limit`: integer greater than 0.
- `companies_list.offset`: integer greater than or equal to 0.
- `get_historical.interval`: `1d`, `1w`, `1m`, `30m`, or `60m`.
- Ambiguous identifiers raise `AMBIGUOUS_IDENTIFIER` with retry guidance and candidates when available.
- Invalid identifiers and plan-gated requests return the underlying API error.

### Tool Call Examples

- Company directory search: `companies_list(search="aramco")`
- Company directory by market alias normalization: `companies_list(search="acwa", market="NOMUC")`
- Company directory pagination: `companies_list(search="bank", limit=50, offset=100)`
- Preferred single quote call: `get_quote(identifier="أرامكو")`
- Legacy single quote call: `get_quote(symbol="2222")`
- Preferred batch quote call: `get_quotes(identifiers=["سبكيم", "كيان"])`
- Legacy batch quote call: `get_quotes(symbols=["2222", "1120"])`
- Financials by exact symbol: `get_financials(symbol="1120")`
- Financial ratios defaults: `get_ratios(symbol="1120")`
- Financial ratios advanced: `get_ratios(symbol="1120", history="5y", period="quarterly", metrics="extended")`
- Compare symbols defaults: `compare_symbols(symbols=["1120", "1180", "1010"])`
- Compare symbols extended: `compare_symbols(symbols=["1120", "1180", "1010", "2222"], metrics="extended")`
- Dividends by exact symbol: `get_dividends(symbol="1120")`
- Market depth by exact symbol: `get_depth(symbol="2222")`
- Market depth with levels: `get_depth(symbol="2222", levels=10)`
- Recent trades by exact symbol: `get_trades(symbol="2222")`
- Recent trades with limit: `get_trades(symbol="2222", limit=20)`
- Recent market events: `get_events(limit=10)`
- Events for one symbol: `get_events(symbol="1120", limit=5)`
- Historical by exact symbol: `get_historical(symbol="1120", interval="1d")`
- Historical with explicit daily date range args: `get_historical(symbol="1120", from_date="2026-01-01", to_date="2026-03-31", interval="1d")`
- Intraday historical by exact symbol (plan-gated by API key): `get_historical(symbol="1120", interval="60m")`
- Intraday historical with explicit date range args: `get_historical(symbol="1120", from_date="2026-05-01", to_date="2026-05-31", interval="60m")`

## Company Directory / Symbol Discovery

Use `companies_list` first to reduce invalid-symbol 404s before symbol-only tools.

1. Discover candidates by name or symbol fragment:
   - `companies_list(search="aramco")`
   - `companies_list(search="2222")`
2. Optionally scope discovery by market:
   - `companies_list(search="acwa", market="NOMUC")` (`NOMUC` is normalized to `NOMU`)
3. Pick a symbol from `results`, then call:
   - `get_quote(identifier="<symbol>")`
   - `get_financials(symbol="<symbol>")`
   - `get_dividends(symbol="<symbol>")`
   - `get_historical(symbol="<symbol>")`
4. For pagination loops, increment `offset` by `limit` until you reach `total`:
   - `companies_list(search="bank", limit=100, offset=0)`
   - `companies_list(search="bank", limit=100, offset=100)`
   - continue until `offset >= total`

### MCP Guidance Examples

- User: "سعر الراجحي" -> call `get_quote(identifier="الراجحي")`.
- Follow-up: "قوائم الشركة" -> if previous result includes `resolved_instrument.symbol = "1120"`, reuse it and call `get_financials(symbol="1120")`.

## Example Prompts

- "Give me a TASI summary and market mood."
- "Give me TASI market movers by gainers."
- "Give me NOMU market movers by value."
- "Show me sector performance."
- "Compare سابك, سبكيم, and 2222 by price change and net liquidity."
- "Show me NOMU summary for today."
- "Get financials for 2222."
- "Get dividends for 2222."
- "Show me the order book / market depth for 2222."
- "Show me the latest trades for 2222."
- "What are the latest stock events?"
- "Get 1d historical data for 1120 from 2026-01-01 to 2026-03-31."
- "Tell me about الراجحي and its sector."

Note: `get_financials` and `get_dividends` require Sahmk API access on Starter or higher. If unavailable for the current key, the MCP returns the underlying API error.
Note: `get_depth` is entitlement-gated — [request access](https://www.sahmk.sa/developers/dashboard/realtime-access). `get_trades` and `get_events` require Pro+. If unavailable for the current key, the MCP surfaces the API error.
Note: intraday historical intervals (`30m`, `60m`) may be plan-gated. If unavailable for the current key, the MCP surfaces the API error (for example `403 PLAN_LIMIT`).

## Release Notes

- `0.6.0`: require `sahmk>=0.14.0`; add `get_trades` for recent live trade prints (Pro+).
- `0.5.1`: document market-depth entitlement request link in the README.
- `0.5.0`: require `sahmk>=0.13.0`; add `get_depth` (order-book ladder) and `get_events` (AI event summaries, Pro+).
- `0.4.7`: remove `include_quality` from public `get_financials` tool contract, normalize equivalent Arabic-Indic/ASCII digit inputs before identifier conflict checks, and improve Glama form UX with enum selectors for stable ratio/period options.
- `0.4.6`: add SDK-backed identifier fallback for `get_company` and symbol-first tools (`get_financials`, `get_ratios`, `compare_symbols`, `get_dividends`, `get_historical`) when name/alias inputs fail direct symbol lookup.
- `0.4.5`: align to `sahmk>=0.11.0`; extend `get_historical.interval` support to `30m`/`60m`; document intraday plan-gating behavior.
- `0.4.4`: docs: clarify official distribution channels (GitHub + PyPI only)
- `0.4.3`: Align MCP output contract: no financials `meta`; analytics `meta` is limited to `period`, `metrics`, and `warnings`.
- `0.4.2`: Add SDK method-name compatibility fallback for analytics (`get_ratios`/`ratios`, `compare_symbols`/`compare`).
- `0.4.1`: Require `sahmk>=0.9.1` in package dependency and runtime version guard.
- `0.4.0`: Add analytics ratios and compare tools; enhance financials optional parameters.

## License

MIT — see [LICENSE](https://github.com/sahmk-sa/sahmk-mcp/blob/main/LICENSE)
