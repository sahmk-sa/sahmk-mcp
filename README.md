# sahmk-mcp

Official MCP server for [Sahmk](https://sahmk.sa/developers) — use Saudi market data inside AI agents such as Cursor and Claude Desktop.

This MCP exposes agent-friendly tools on top of the Sahmk API and SDK layer, so assistants can answer market questions in natural language.

## Tools

| Tool | Use it for |
|------|------------|
| `get_quote` | One symbol snapshot (price, change, volume, liquidity) |
| `get_quotes` | Multi-symbol comparison in one call (up to 50 symbols) |
| `get_market_summary` | Market summary for `TASI`/`NOMU` with delay metadata |
| `get_market_movers` | Top movers by `gainers`, `losers`, `volume`, or `value` (optional index); stable output with `type`, `index`, `count`, `items` |
| `get_sectors` | Sector performance snapshot for `TASI`/`NOMU`; stable output with `index`, `count`, `items` |
| `get_company` | Company profile, sector, and fundamentals |
| `get_financials` | Financial statements (income, balance sheet, cash flow) *(Starter+ plan)* |
| `get_dividends` | Dividend history and yield data *(Starter+ plan)* |
| `get_historical` | Historical OHLCV series |

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
- `get_quotes.symbols`: maximum 50 symbols per request.
- `get_historical.interval`: `1d`, `1w`, or `1m`.
- Invalid symbols return an error response from the underlying API.

## Example Prompts

- "Give me a TASI summary and market mood."
- "Give me TASI market movers by gainers."
- "Give me NOMU market movers by value."
- "Show me sector performance."
- "Compare 2222, 1120, and 7010 by price change and net liquidity."
- "Show me NOMU summary for today."
- "Get financials for 2222."
- "Get dividends for 2222."
- "Get 1d historical data for 1120 from 2026-01-01 to 2026-03-31."
- "Tell me about STC (7010) and its sector."

Note: `get_financials` and `get_dividends` are plan-gated by Sahmk API access (Starter+). If unavailable for a key, the MCP will return the underlying API error.

## License

MIT — see [LICENSE](https://github.com/sahmk-sa/sahmk-mcp/blob/main/LICENSE)
