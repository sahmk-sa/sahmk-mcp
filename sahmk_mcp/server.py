"""SAHMK MCP Server — AI agent access to Saudi stock market data."""

import os
import re
from typing import Annotated, Optional

from fastmcp import FastMCP

from sahmk import SahmkClient, SahmkError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

mcp = FastMCP(
    "sahmk",
    instructions=(
        "SAHMK provides real-time and historical Saudi stock market (Tadawul) data "
        "for 350+ listed stocks. Stock symbols are numeric codes "
        "(e.g. '2222' for Aramco, '1120' for Al Rajhi Bank, '7010' for STC). "
        "Use get_quote for a single stock price, get_quotes to compare multiple stocks, "
        "get_market_summary for the overall market (optionally by index), get_market_movers for top gainers/losers/leaders, "
        "get_sectors for sector performance, get_company for company details, get_financials and get_dividends for fundamentals, "
        "and get_historical for past price data."
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


def _validate_date(value: str | None, name: str) -> None:
    if value is not None and not _DATE_RE.match(value):
        raise ValueError(
            f"Invalid {name} format: '{value}'. Expected YYYY-MM-DD (e.g. '2026-01-15')."
        )


@mcp.tool
def get_quote(
    symbol: Annotated[str, "Stock symbol (e.g. '2222' for Aramco, '1120' for Al Rajhi)"],
) -> dict:
    """Get a real-time quote for a Saudi stock.
    Use this when the user asks for the current price, change, bid/ask, or trading activity of one stock."""
    client = _get_client()
    return client.quote(symbol).raw


@mcp.tool
def get_quotes(
    symbols: Annotated[
        list[str],
        "List of stock symbols, up to 50 (e.g. ['2222', '1120'])",
    ],
) -> dict:
    """Get real-time quotes for multiple Saudi stocks in one call.
    Use this when the user wants to compare several stocks or asks for prices of more than one symbol."""
    if not symbols:
        raise ValueError("At least one symbol is required.")
    client = _get_client()
    return client.quotes(symbols).raw


@mcp.tool
def get_market_summary(
    index: Annotated[
        Optional[str],
        "Optional market index: 'TASI' or 'NOMU' (alias 'NOMUC' is accepted and normalized).",
    ] = None,
) -> dict:
    """Get the current Saudi market summary including TASI index level, change, market direction, and advancing/declining stock counts.
    Use this for questions about the overall market today."""
    client = _get_client()
    return client.market_summary(index=index).raw


@mcp.tool
def get_market_movers(
    type: Annotated[
        str,
        "Mover type: 'gainers', 'losers', 'volume', or 'value'.",
    ],
    limit: Annotated[
        Optional[int],
        "Optional number of results from 1 to 50.",
    ] = None,
    index: Annotated[
        Optional[str],
        "Optional market index: 'TASI' or 'NOMU' (alias 'NOMUC' is accepted and normalized).",
    ] = None,
) -> dict:
    """Get market movers in one curated endpoint.
    Use this for top gainers, top losers, highest volume leaders, or highest value leaders."""
    mover_handlers = {
        "gainers": "gainers",
        "losers": "losers",
        "volume": "volume_leaders",
        "value": "value_leaders",
    }
    if type not in mover_handlers:
        raise ValueError(
            f"Invalid type: '{type}'. Must be one of: gainers, losers, volume, value."
        )
    if limit is not None and (not isinstance(limit, int) or limit < 1 or limit > 50):
        raise ValueError(
            f"Invalid limit: '{limit}'. Must be between 1 and 50."
        )

    client = _get_client()
    method_name = mover_handlers[type]
    mover_method = getattr(client, method_name)
    return mover_method(limit=limit, index=index).raw


@mcp.tool
def get_sectors(
    index: Annotated[
        Optional[str],
        "Optional market index: 'TASI' or 'NOMU' (alias 'NOMUC' is accepted and normalized).",
    ] = None,
) -> dict:
    """Get sector performance for the Saudi market.
    Use this when the user asks for sector-level market moves or a sector snapshot."""
    client = _get_client()
    return client.sectors(index=index).raw


@mcp.tool
def get_company(
    symbol: Annotated[str, "Stock symbol (e.g. '2222' for Aramco)"],
) -> dict:
    """Get a company profile for a Saudi stock, including sector, industry, fundamentals, valuation, technical indicators, and analyst consensus.
    Use this when the user asks about a company's profile, key metrics, or detailed information."""
    client = _get_client()
    return client.company(symbol).raw


@mcp.tool
def get_financials(
    symbol: Annotated[str, "Stock symbol (e.g. '2222' for Aramco)"],
) -> dict:
    """Get company financial statements and key financial data.
    Use this for income statement, balance sheet, and cash flow requests."""
    client = _get_client()
    return client.financials(symbol).raw


@mcp.tool
def get_dividends(
    symbol: Annotated[str, "Stock symbol (e.g. '2222' for Aramco)"],
) -> dict:
    """Get company dividend history and yield data.
    Use this when the user asks for dividends or payout history."""
    client = _get_client()
    return client.dividends(symbol).raw


@mcp.tool
def get_historical(
    symbol: Annotated[str, "Stock symbol (e.g. '2222')"],
    from_date: Annotated[
        Optional[str], "Start date in YYYY-MM-DD format (default: 30 days ago)"
    ] = None,
    to_date: Annotated[
        Optional[str], "End date in YYYY-MM-DD format (default: today)"
    ] = None,
    interval: Annotated[
        Optional[str], "'1d' for daily, '1w' for weekly, or '1m' for monthly (default: '1d')"
    ] = None,
) -> dict:
    """Get historical OHLCV price data for a Saudi stock over a date range.
    Use this when the user asks for past prices, price trends, or chart-style historical data."""
    _validate_date(from_date, "from_date")
    _validate_date(to_date, "to_date")
    if interval and interval not in ("1d", "1w", "1m"):
        raise ValueError(
            f"Invalid interval: '{interval}'. Must be '1d' (daily), '1w' (weekly), or '1m' (monthly)."
        )
    client = _get_client()
    return client.historical(
        symbol, from_date=from_date, to_date=to_date, interval=interval
    ).raw


def main():
    mcp.run()


if __name__ == "__main__":
    main()
