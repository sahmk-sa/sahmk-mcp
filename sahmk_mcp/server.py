"""SAHMK MCP Server — AI agent access to Saudi stock market data."""

import os
import re
from typing import Annotated, Optional

from fastmcp import FastMCP

from sahmk import SahmkClient, SahmkError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MIN_SAHMK_VERSION = (0, 8, 0)

mcp = FastMCP(
    "sahmk",
    instructions=(
        "SAHMK provides real-time and historical Saudi stock market (Tadawul) data "
        "for 350+ listed stocks. Stock inputs can be numeric symbols "
        "(e.g. '2222' for Aramco, '1120' for Al Rajhi Bank, '7010' for STC) "
        "or company names/aliases supported by the backend resolver. "
        "Use get_quote for a single stock price, get_quotes to compare multiple stocks, "
        "get_market_summary for the overall market (optionally by index), get_market_movers for top gainers/losers/leaders, "
        "get_sectors for sector performance, get_company for company details, get_financials and get_dividends for fundamentals, "
        "and get_historical for past price data."
    ),
)


def _get_client() -> SahmkClient:
    _ensure_sahmk_min_version()
    api_key = os.environ.get("SAHMK_API_KEY")
    if not api_key:
        raise SahmkError(
            "SAHMK_API_KEY environment variable is not set. "
            "Get your key at https://sahmk.sa/developers"
        )
    return SahmkClient(api_key)


def _parse_semver(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    normalized: list[int] = []
    for idx in range(3):
        if idx >= len(parts):
            normalized.append(0)
            continue
        token = parts[idx]
        digits = "".join(ch for ch in token if ch.isdigit())
        normalized.append(int(digits) if digits else 0)
    return tuple(normalized)  # type: ignore[return-value]


def _ensure_sahmk_min_version() -> None:
    # Defer import to runtime so tests can patch module version safely.
    import sahmk  # noqa: PLC0415

    current = getattr(sahmk, "__version__", "0.0.0")
    if _parse_semver(current) >= _MIN_SAHMK_VERSION:
        return
    min_text = ".".join(str(x) for x in _MIN_SAHMK_VERSION)
    raise SahmkError(
        f"sahmk>={min_text} is required for symbol discovery and identifier-aware quote resolution. "
        f"Found sahmk=={current}. Run: pip install --upgrade 'sahmk>={min_text}'."
    )


def _validate_date(value: str | None, name: str) -> None:
    if value is not None and not _DATE_RE.match(value):
        raise ValueError(
            f"Invalid {name} format: '{value}'. Expected YYYY-MM-DD (e.g. '2026-01-15')."
        )


def _normalize_market(value: str | None, name: str = "market") -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Invalid {name}: '{value}'. Must be one of: TASI, NOMU."
        )
    normalized = value.strip().upper()
    if normalized == "NOMUC":
        normalized = "NOMU"
    if normalized not in {"TASI", "NOMU"}:
        raise ValueError(
            f"Invalid {name}: '{value}'. Must be one of: TASI, NOMU."
        )
    return normalized


def _validate_limit_offset(limit: int, offset: int) -> None:
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"Invalid limit: '{limit}'. Must be a positive integer.")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError(
            f"Invalid offset: '{offset}'. Must be an integer greater than or equal to 0."
        )


def _to_raw_response(value):
    if hasattr(value, "raw"):
        return value.raw
    return value


def _extract_error_payload(error: SahmkError) -> dict:
    response = getattr(error, "response", None)
    if response is None:
        return {}
    try:
        payload = response.json()
    except Exception:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _extract_ambiguity_candidates(payload: dict) -> list[str]:
    error = payload.get("error")
    if not isinstance(error, dict):
        return []
    details = error.get("details")
    if not isinstance(details, dict):
        return []
    raw_candidates = details.get("candidates")
    if not isinstance(raw_candidates, list):
        return []

    candidates: list[str] = []
    for item in raw_candidates:
        if isinstance(item, str):
            text = item.strip()
            if text:
                candidates.append(text)
        elif isinstance(item, dict):
            # Prefer symbol in candidate objects, then fall back to a name.
            symbol = item.get("symbol")
            name = item.get("name")
            value = symbol if isinstance(symbol, str) else name
            if isinstance(value, str):
                text = value.strip()
                if text:
                    candidates.append(text)
    return candidates


def _raise_if_ambiguous_identifier(error: SahmkError, value: str) -> None:
    code = (getattr(error, "error_code", "") or "").upper()
    message = str(error).lower()
    is_ambiguous = "AMBIGU" in code or "ambiguous" in message
    if not is_ambiguous:
        raise error

    payload = _extract_error_payload(error)
    candidates = _extract_ambiguity_candidates(payload)
    candidate_text = ", ".join(candidates) if candidates else "(not provided)"
    raise ValueError(
        "AMBIGUOUS_IDENTIFIER: "
        f"'{value}' matched multiple stocks. "
        "Retry with a more specific name or a numeric symbol. "
        f"Candidates: {candidate_text}."
    ) from error


def _is_ambiguous_identifier_error(error: SahmkError) -> bool:
    code = (getattr(error, "error_code", "") or "").upper()
    message = str(error).lower()
    return "AMBIGU" in code or "ambiguous" in message


def _is_unknown_identifier_error(error: SahmkError) -> bool:
    code = (getattr(error, "error_code", "") or "").upper()
    if "NOT_FOUND" in code:
        return True
    message = str(error).lower()
    return (
        "unknown identifier" in message
        or "stock symbol" in message and "not found" in message
    )


def _is_numeric_identifier(value: str) -> bool:
    return bool(value and value.isdigit())


def _extract_first_quote(raw: dict) -> Optional[dict]:
    quotes = raw.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        return None
    first = quotes[0]
    if isinstance(first, dict):
        return first
    return None


def _extract_not_found_inputs(batch_raw: dict) -> list[str]:
    resolution = batch_raw.get("resolution")
    if not isinstance(resolution, dict):
        return []
    not_found = resolution.get("not_found")
    if not isinstance(not_found, list):
        return []
    inputs: list[str] = []
    for item in not_found:
        if isinstance(item, dict):
            value = item.get("input")
            if isinstance(value, str) and value.strip():
                inputs.append(value.strip())
        elif isinstance(item, str):
            text = item.strip()
            if text:
                inputs.append(text)
    return inputs


def _merge_recovered_batch_quotes(
    requested_identifiers: list[str],
    batch_raw: dict,
    recovered_quotes: list[dict],
    recovered_inputs: set[str],
    recovered_ambiguous: list[dict],
) -> dict:
    merged = dict(batch_raw)
    existing_quotes = merged.get("quotes")
    if not isinstance(existing_quotes, list):
        existing_quotes = []
    quotes = [item for item in existing_quotes if isinstance(item, dict)]

    existing_symbols = {
        quote.get("symbol")
        for quote in quotes
        if isinstance(quote.get("symbol"), str) and quote.get("symbol")
    }
    for quote in recovered_quotes:
        symbol = quote.get("symbol")
        if isinstance(symbol, str) and symbol in existing_symbols:
            continue
        quotes.append(quote)
        if isinstance(symbol, str):
            existing_symbols.add(symbol)

    resolution = merged.get("resolution")
    if not isinstance(resolution, dict):
        resolution = {}
    not_found_inputs = set(_extract_not_found_inputs(merged))
    not_found_inputs -= recovered_inputs
    ambiguous_inputs = {
        item.get("input")
        for item in recovered_ambiguous
        if isinstance(item, dict) and isinstance(item.get("input"), str)
    }
    not_found_inputs -= {x for x in ambiguous_inputs if x}

    existing_ambiguous = resolution.get("ambiguous")
    if not isinstance(existing_ambiguous, list):
        existing_ambiguous = []
    ambiguous = [item for item in existing_ambiguous if isinstance(item, dict)]
    ambiguous += recovered_ambiguous

    merged["quotes"] = quotes
    merged["count"] = len(quotes)
    merged["resolution"] = {
        "requested_count": len(requested_identifiers),
        "resolved_count": len(quotes),
        "ambiguous": ambiguous,
        "not_found": [{"input": value} for value in sorted(not_found_inputs)],
    }
    return merged


def _recover_unresolved_batch_quotes(client: SahmkClient, identifiers: list[str], raw: dict) -> dict:
    not_found_inputs = _extract_not_found_inputs(raw)
    if not not_found_inputs:
        return raw

    recovered_quotes: list[dict] = []
    recovered_inputs: set[str] = set()
    recovered_ambiguous: list[dict] = []
    for value in not_found_inputs:
        if _is_numeric_identifier(value):
            continue
        try:
            resolved = client.quote(value).raw
            if isinstance(resolved, dict):
                recovered_quotes.append(resolved)
                recovered_inputs.add(value)
        except SahmkError as error:
            if _is_ambiguous_identifier_error(error):
                payload = _extract_error_payload(error)
                candidates = _extract_ambiguity_candidates(payload)
                recovered_ambiguous.append({"input": value, "candidates": candidates})
            # Keep unresolved items in not_found for all non-resolved cases.
            continue

    if not recovered_quotes and not recovered_ambiguous:
        return raw
    return _merge_recovered_batch_quotes(
        identifiers, raw, recovered_quotes, recovered_inputs, recovered_ambiguous
    )


def _resolve_single_identifier(
    identifier: Optional[str],
    symbol: Optional[str],
) -> str:
    if identifier is not None and symbol is not None and identifier != symbol:
        raise ValueError(
            "Conflicting inputs: provide either 'identifier' (preferred) "
            "or legacy 'symbol', not both with different values."
        )
    value = identifier if identifier is not None else symbol
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValueError(
            "Missing required stock input: provide 'identifier' "
            "(preferred) or legacy 'symbol'."
        )
    return value.strip()


def _resolve_batch_identifiers(
    identifiers: Optional[list[str]],
    symbols: Optional[list[str]],
) -> list[str]:
    if identifiers is not None and symbols is not None and identifiers != symbols:
        raise ValueError(
            "Conflicting inputs: provide either 'identifiers' (preferred) "
            "or legacy 'symbols', not both with different values."
        )
    values = identifiers if identifiers is not None else symbols
    if not values:
        raise ValueError("At least one identifier is required.")
    return values


def _normalize_market_movers_response(mover_type: str, raw: dict) -> dict:
    list_key_map = {
        "gainers": "gainers",
        "losers": "losers",
        "volume": "stocks",
        "value": "stocks",
    }
    items = raw.get(list_key_map[mover_type]) or []
    if not isinstance(items, list):
        items = []
    count = raw.get("count")
    if not isinstance(count, int):
        count = len(items)
    return {
        "type": mover_type,
        "index": raw.get("index"),
        "count": count,
        "items": items,
    }


def _normalize_sectors_response(raw: dict) -> dict:
    items = raw.get("sectors") or []
    if not isinstance(items, list):
        items = []
    count = raw.get("count")
    if not isinstance(count, int):
        count = len(items)
    return {
        "index": raw.get("index"),
        "count": count,
        "items": items,
    }


def _normalize_financials_response(raw: dict) -> dict:
    normalized = dict(raw)
    normalized.setdefault("symbol", None)
    normalized.setdefault("income_statements", [])
    normalized.setdefault("balance_sheets", [])
    normalized.setdefault("cash_flows", [])
    return normalized


def _normalize_dividends_response(raw: dict) -> dict:
    normalized = dict(raw)
    normalized.setdefault("symbol", None)
    normalized.setdefault("current_price", None)
    normalized.setdefault("trailing_12m_yield", None)
    normalized.setdefault("trailing_12m_dividends", None)
    normalized.setdefault("payments_last_year", None)
    normalized.setdefault("upcoming", [])
    normalized.setdefault("history", [])
    return normalized


@mcp.tool
def get_quote(
    identifier: Annotated[
        Optional[str],
        "Stock identifier (preferred): symbol, Arabic/English name, or known alias, e.g. '2222', 'أرامكو', 'الراجحي'.",
    ] = None,
    symbol: Annotated[
        Optional[str],
        "Legacy alias for identifier. Prefer 'identifier'.",
    ] = None,
) -> dict:
    """Get a real-time quote for a Saudi stock.
    Use this when the user asks for the current price, change, bid/ask, or trading activity of one stock."""
    normalized_identifier = _resolve_single_identifier(identifier, symbol)
    client = _get_client()
    try:
        return client.quote(normalized_identifier).raw
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_identifier)
        except SahmkError:
            # Some backends may fail single-quote name resolution while batch
            # identifier resolution succeeds. Keep resolution backend/SDK-based.
            if _is_unknown_identifier_error(error) and not _is_numeric_identifier(
                normalized_identifier
            ):
                try:
                    batch_raw = client.quotes([normalized_identifier]).raw
                    first = _extract_first_quote(batch_raw)
                    if first is not None:
                        return first
                except SahmkError as batch_error:
                    _raise_if_ambiguous_identifier(batch_error, normalized_identifier)
                    raise batch_error
            raise error


@mcp.tool
def get_quotes(
    identifiers: Annotated[
        Optional[list[str]],
        "List of stock identifiers (preferred): symbol, Arabic/English name, or alias, up to 50 (e.g. ['2222', 'سابك']).",
    ] = None,
    symbols: Annotated[
        Optional[list[str]],
        "Legacy alias for identifiers. Prefer 'identifiers'.",
    ] = None,
) -> dict:
    """Get real-time quotes for multiple Saudi stocks in one call.
    Use this when the user wants to compare several stocks or asks for prices of more than one symbol."""
    normalized_identifiers = _resolve_batch_identifiers(identifiers, symbols)
    client = _get_client()
    try:
        raw = client.quotes(normalized_identifiers).raw
        if isinstance(raw, dict):
            return _recover_unresolved_batch_quotes(client, normalized_identifiers, raw)
        return raw
    except SahmkError as error:
        joined = ", ".join(normalized_identifiers)
        _raise_if_ambiguous_identifier(error, joined)


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
    Use this for top gainers, top losers, highest volume leaders, or highest value leaders.
    Returns a stable schema: type, index, count, items."""
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
    raw = mover_method(limit=limit, index=index).raw
    return _normalize_market_movers_response(type, raw)


@mcp.tool
def get_sectors(
    index: Annotated[
        Optional[str],
        "Optional market index: 'TASI' or 'NOMU' (alias 'NOMUC' is accepted and normalized).",
    ] = None,
) -> dict:
    """Get sector performance for the Saudi market.
    Use this when the user asks for sector-level market moves or a sector snapshot.
    Returns a stable schema: index, count, items."""
    client = _get_client()
    raw = client.sectors(index=index).raw
    return _normalize_sectors_response(raw)


@mcp.tool
def get_company(
    identifier: Annotated[
        str,
        "Stock identifier (symbol, Arabic/English name, or alias), e.g. '2222', 'أرامكو'.",
    ],
) -> dict:
    """Get a company profile for a Saudi stock, including sector, industry, fundamentals, valuation, technical indicators, and analyst consensus.
    Use this when the user asks about a company's profile, key metrics, or detailed information."""
    client = _get_client()
    try:
        return client.company(identifier).raw
    except SahmkError as error:
        _raise_if_ambiguous_identifier(error, identifier)


@mcp.tool
def get_financials(
    identifier: Annotated[
        str,
        "Stock identifier (symbol, Arabic/English name, or alias), e.g. '2222', 'أرامكو'.",
    ],
) -> dict:
    """Get company financial statements and key financial data.
    Use this for income statement, balance sheet, and cash flow requests."""
    client = _get_client()
    try:
        raw = client.financials(identifier).raw
    except SahmkError as error:
        _raise_if_ambiguous_identifier(error, identifier)
    return _normalize_financials_response(raw)


@mcp.tool
def get_dividends(
    identifier: Annotated[
        str,
        "Stock identifier (symbol, Arabic/English name, or alias), e.g. '2222', 'أرامكو'.",
    ],
) -> dict:
    """Get company dividend history and yield data.
    Use this when the user asks for dividends or payout history."""
    client = _get_client()
    try:
        raw = client.dividends(identifier).raw
    except SahmkError as error:
        _raise_if_ambiguous_identifier(error, identifier)
    return _normalize_dividends_response(raw)


@mcp.tool
def get_historical(
    identifier: Annotated[
        str,
        "Stock identifier (symbol, Arabic/English name, or alias), e.g. '2222', 'الراجحي'.",
    ],
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
    try:
        return client.historical(
            identifier, from_date=from_date, to_date=to_date, interval=interval
        ).raw
    except SahmkError as error:
        _raise_if_ambiguous_identifier(error, identifier)


@mcp.tool
def companies_list(
    search: Annotated[
        Optional[str],
        "Optional text search across symbol/company names for discovery.",
    ] = None,
    market: Annotated[
        Optional[str],
        "Optional market filter: 'TASI' or 'NOMU' (alias 'NOMUC' is accepted and normalized).",
    ] = None,
    limit: Annotated[
        int,
        "Page size (must be > 0).",
    ] = 100,
    offset: Annotated[
        int,
        "Pagination offset (must be >= 0).",
    ] = 0,
) -> dict:
    """Discover listed companies and symbols.
    Use this first to find/validate symbols before quote/company calls."""
    _validate_limit_offset(limit=limit, offset=offset)
    normalized_market = _normalize_market(market, name="market")
    client = _get_client()
    return _to_raw_response(
        client.companies(
            search=search,
            market=normalized_market,
            limit=limit,
            offset=offset,
        )
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
