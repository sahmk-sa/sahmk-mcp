"""SAHMK MCP Server — AI agent access to Saudi stock market data."""

import os
from typing import Annotated, Optional

from fastmcp import FastMCP

from sahmk import SahmkClient, SahmkError

mcp = FastMCP(
    "sahmk",
    instructions=(
        "SAHMK provides real-time and historical Saudi stock market (Tadawul) data. "
        "Stock symbols are numeric codes (e.g. '2222' for Aramco, '1120' for Al Rajhi Bank). "
        "Use get_quote for a single stock, get_quotes to compare multiple stocks, "
        "get_market_summary for the overall market, get_company for company details, "
        "and get_historical for price history."
    ),
)


def _get_client() -> SahmkClient:
    api_key = os.environ.get("SAHMK_API_KEY")
    if not api_key:
        raise SahmkError(
            "SAHMK_API_KEY environment variable is not set. "
            "Get your key at https://sahmk.sa/developers"
        )
    return SahmkClient(api_key)


@mcp.tool
def get_quote(
    symbol: Annotated[str, "Stock symbol, e.g. '2222' for Aramco"],
) -> dict:
    """Get a real-time quote for a Saudi stock.
    Returns price, change, change_percent, volume, bid, ask, and liquidity data."""
    client = _get_client()
    return client.quote(symbol).raw


@mcp.tool
def get_quotes(
    symbols: Annotated[
        list[str],
        "List of stock symbols (up to 50), e.g. ['2222', '1120']",
    ],
) -> dict:
    """Get real-time quotes for multiple Saudi stocks in one request.
    Returns price, change, and volume for each. Use this when comparing stocks."""
    client = _get_client()
    return client.quotes(symbols).raw


@mcp.tool
def get_market_summary() -> dict:
    """Get the Saudi market overview.
    Returns TASI index value, change, total volume, advancing/declining counts, and market mood."""
    client = _get_client()
    return client.market_summary().raw


@mcp.tool
def get_company(
    symbol: Annotated[str, "Stock symbol, e.g. '2222' for Aramco"],
) -> dict:
    """Get company profile for a Saudi-listed stock.
    Returns name, sector, industry, description, and fundamentals like P/E, market cap, and EPS."""
    client = _get_client()
    return client.company(symbol).raw


@mcp.tool
def get_historical(
    symbol: Annotated[str, "Stock symbol, e.g. '2222'"],
    from_date: Annotated[
        Optional[str], "Start date YYYY-MM-DD (default: 30 days ago)"
    ] = None,
    to_date: Annotated[
        Optional[str], "End date YYYY-MM-DD (default: today)"
    ] = None,
    interval: Annotated[
        Optional[str], "'1d' (daily), '1w' (weekly), or '1m' (monthly). Default: '1d'"
    ] = None,
) -> dict:
    """Get historical OHLCV price data for a Saudi stock.
    Returns daily/weekly/monthly open, high, low, close, and volume."""
    client = _get_client()
    return client.historical(
        symbol, from_date=from_date, to_date=to_date, interval=interval
    ).raw


def main():
    mcp.run()


if __name__ == "__main__":
    main()
