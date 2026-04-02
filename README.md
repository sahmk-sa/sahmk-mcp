# sahmk-mcp

Official MCP server for [Sahmk](https://sahmk.sa/developers) — gives AI agents access to real-time and historical Saudi stock market (Tadawul) data.

## Tools

| Tool | Description |
|------|-------------|
| `get_quote` | Real-time quote for a single stock (price, change, volume, liquidity) |
| `get_quotes` | Batch quotes for multiple stocks (up to 50) |
| `get_market_summary` | TASI index, volume, advancing/declining, market mood |
| `get_company` | Company profile, sector, fundamentals |
| `get_historical` | Historical OHLCV data (daily/weekly/monthly) |

## Get Your API Key

1. Sign up at [sahmk.sa/developers](https://sahmk.sa/developers)
2. Go to Dashboard → API Keys → Create Key
3. Copy your key (starts with `shmk_live_` or `shmk_test_`)

## Installation

```bash
pip install sahmk-mcp
```

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

### Running Directly

```bash
export SAHMK_API_KEY="your_api_key"
sahmk-mcp
```

## Example Prompts

- "What's the current price of Aramco (2222)?"
- "Compare 2222 and 1120"
- "Show me the Saudi market summary"
- "Get historical prices for Al Rajhi Bank (1120) for the last 3 months"
- "Tell me about STC (7010)"

## License

MIT — see [LICENSE](LICENSE)
