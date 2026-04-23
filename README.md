# sahmk-mcp

Official MCP server for [Sahmk](https://sahmk.sa/developers) — use Saudi market data inside AI agents such as Cursor and Claude Desktop.

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
| `get_dividends` | Dividend history and yield data *(Starter+ plan)* |
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

## Installation

```bash
pip install sahmk-mcp
```

Requires `sahmk>=0.8.0` for symbol discovery (`companies_list`) and identifier-aware quote resolution (`identifier`/`identifiers`).

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
- `companies_list.market`: `TASI` or `NOMU` (`NOMUC` alias is accepted and normalized).
- `companies_list.limit`: integer greater than 0.
- `companies_list.offset`: integer greater than or equal to 0.
- `get_historical.interval`: `1d`, `1w`, or `1m`.
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

## Company Directory / Symbol Discovery

Use `companies_list` first to reduce invalid-symbol 404s before quote/company calls.

1. Discover candidates by name or symbol fragment:
   - `companies_list(search="aramco")`
   - `companies_list(search="2222")`
2. Optionally scope discovery by market:
   - `companies_list(search="acwa", market="NOMUC")` (`NOMUC` is normalized to `NOMU`)
3. Pick a symbol from `results`, then call:
   - `get_quote(identifier="<symbol>")`
   - `get_company(identifier="<symbol>")`
4. For pagination loops, increment `offset` by `limit` until you reach `total`:
   - `companies_list(search="bank", limit=100, offset=0)`
   - `companies_list(search="bank", limit=100, offset=100)`
   - continue until `offset >= total`

## Example Prompts

- "Give me a TASI summary and market mood."
- "Give me TASI market movers by gainers."
- "Give me NOMU market movers by value."
- "Show me sector performance."
- "Compare سابك, سبكيم, and 2222 by price change and net liquidity."
- "Show me NOMU summary for today."
- "Get financials for 2222."
- "Get dividends for 2222."
- "Get 1d historical data for 1120 from 2026-01-01 to 2026-03-31."
- "Tell me about الراجحي and its sector."

Note: `get_financials` and `get_dividends` require Sahmk API access on Starter or higher. If unavailable for the current key, the MCP returns the underlying API error.

## License

MIT — see [LICENSE](https://github.com/sahmk-sa/sahmk-mcp/blob/main/LICENSE)
