"""SAHMK MCP Server — AI agent access to Saudi stock market data."""

import os
import re
from typing import Annotated, Any, Literal, Optional

from fastmcp import FastMCP

from sahmk import SahmkClient, SahmkError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MIN_SAHMK_VERSION = (0, 17, 0)
# Canonical public Developer API host (REST). Compatibility host app.sahmk.sa
# remains supported via SAHMK_BASE_URL.
_DEFAULT_BASE_URL = "https://api.sahmk.sa/api/v1"
# Canonical intervals first, then legacy aliases the API still accepts.
# "1m" is one MONTH (alias of "1mo"); one-minute bars are "1min".
_HISTORICAL_INTERVALS = (
    "1min", "5min", "15min", "30min", "60min", "1d", "1w", "1mo",
    "30m", "60m", "1m",
)
_PORTFOLIO_TRANSACTION_TYPES = ("deposit", "buy", "sell", "withdrawal", "dividend", "fee")
_ARABIC_INDIC_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)

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
        "get_depth for order-book depth (bid/ask ladder), get_trades for recent live trade prints (Pro+), "
        "get_events for AI stock event summaries (Pro+), "
        "and get_historical for past price data. "
        "Portfolio tools (get_portfolios, get_portfolio, get_portfolio_summary, get_portfolio_performance, "
        "get_portfolio_transactions, create_portfolio, create_portfolio_transaction, "
        "reverse_portfolio_transaction, set_portfolio_holdings) read and write the user's own SAHMK portfolios. "
        "For set_portfolio_holdings, always run a dry run first, show the plan, and apply only after the user confirms. "
        "For get_financials/get_dividends/get_historical/get_depth/get_trades, requires exact exchange symbol. "
        "If the user provides a company name, first use companies_list. "
        "If a previous tool result included resolved_instrument.symbol, reuse that symbol. "
        "Example flow: User says 'سعر الراجحي' -> get_quote(identifier='الراجحي'). "
        "Follow-up 'قوائم الشركة' -> reuse resolved_instrument.symbol='1120' and call get_financials(symbol='1120')."
    ),
)


def _resolve_base_url() -> str:
    """Return the REST base URL for public Developer API calls.

    Defaults to api.sahmk.sa. Override with SAHMK_BASE_URL (for example
    https://app.sahmk.sa/api/v1) when needed. Do not point portal/dashboard
    paths (/api/developers/*) at api.sahmk.sa.
    """
    override = os.environ.get("SAHMK_BASE_URL")
    if override and override.strip():
        return override.strip().rstrip("/")
    return _DEFAULT_BASE_URL


def _get_client() -> SahmkClient:
    _ensure_sahmk_min_version()
    api_key = os.environ.get("SAHMK_API_KEY")
    if not api_key:
        raise SahmkError(
            "SAHMK_API_KEY environment variable is not set. "
            "Get your key at https://sahmk.sa/developers"
        )
    return SahmkClient(api_key, base_url=_resolve_base_url())


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
        f"sahmk>={min_text} is required for MCP-SDK compatibility. "
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
    if (
        "NOT_FOUND" in code
        or "INVALID_SYMBOL" in code
        or "INVALID_IDENTIFIER" in code
        or "UNKNOWN_IDENTIFIER" in code
    ):
        return True
    message = str(error).lower()
    return (
        "unknown identifier" in message
        or "invalid symbol" in message
        or "stock symbol" in message and "not found" in message
    )


def _is_numeric_identifier(value: str) -> bool:
    return bool(value and value.isdigit())


def _normalize_identifier_digits(value: str) -> str:
    return value.translate(_ARABIC_INDIC_DIGIT_TRANSLATION)


def _normalize_symbol_input(value: str, field_name: str = "symbol") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {field_name}: '{value}'. Must be a non-empty string.")
    return _normalize_identifier_digits(value.strip())


def _extract_first_quote(raw: dict) -> Optional[dict]:
    quotes = raw.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        return None
    first = quotes[0]
    if isinstance(first, dict):
        return first
    return None


def _extract_quote_symbol(raw: dict) -> Optional[str]:
    first = _extract_first_quote(raw)
    if not isinstance(first, dict):
        return None
    symbol = first.get("symbol")
    if isinstance(symbol, str) and symbol.strip():
        return symbol.strip()
    return None


def _resolve_symbol_from_identifier(client: SahmkClient, identifier: str) -> Optional[str]:
    identifier = _normalize_identifier_digits(identifier.strip())
    if _is_numeric_identifier(identifier):
        return identifier
    try:
        batch_raw = _to_raw_response(client.quotes([identifier]))
    except SahmkError as error:
        _raise_if_ambiguous_identifier(error, identifier)
        return None
    if not isinstance(batch_raw, dict):
        return None
    return _extract_quote_symbol(batch_raw)


def _resolve_symbol_from_unknown_identifier_error(
    client: SahmkClient, identifier: str, error: SahmkError
) -> Optional[str]:
    if not _is_unknown_identifier_error(error) or _is_numeric_identifier(identifier):
        return None
    return _resolve_symbol_from_identifier(client, identifier)


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
    normalized_identifier = (
        _normalize_identifier_digits(identifier.strip())
        if isinstance(identifier, str) and identifier.strip()
        else identifier
    )
    normalized_symbol = (
        _normalize_identifier_digits(symbol.strip())
        if isinstance(symbol, str) and symbol.strip()
        else symbol
    )
    if (
        identifier is not None
        and symbol is not None
        and normalized_identifier != normalized_symbol
    ):
        raise ValueError(
            "Conflicting inputs: provide either 'identifier' (preferred) "
            "or legacy 'symbol', not both with different values."
        )
    value = normalized_identifier if identifier is not None else normalized_symbol
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
    normalized_identifiers = (
        [_normalize_identifier_digits(value.strip()) for value in identifiers]
        if identifiers is not None
        else None
    )
    normalized_symbols = (
        [_normalize_identifier_digits(value.strip()) for value in symbols]
        if symbols is not None
        else None
    )
    if (
        identifiers is not None
        and symbols is not None
        and normalized_identifiers != normalized_symbols
    ):
        raise ValueError(
            "Conflicting inputs: provide either 'identifiers' (preferred) "
            "or legacy 'symbols', not both with different values."
        )
    values = (
        normalized_identifiers
        if normalized_identifiers is not None
        else normalized_symbols
    )
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
    # Financial statements endpoint is contractually block-focused and does not expose meta.
    normalized.pop("meta", None)
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


def _normalize_analytics_meta(raw_meta) -> dict:
    if not isinstance(raw_meta, dict):
        return {}
    normalized_meta: dict = {}
    for key in ("period", "metrics", "warnings"):
        if key in raw_meta:
            normalized_meta[key] = raw_meta[key]
    return normalized_meta


def _normalize_ratios_response(raw: dict) -> dict:
    normalized = dict(raw)
    normalized.setdefault("symbol", None)
    normalized.setdefault("ratios", {})
    normalized["meta"] = _normalize_analytics_meta(normalized.get("meta"))
    return normalized


def _normalize_compare_response(raw: dict) -> dict:
    normalized = dict(raw)
    results = normalized.get("results")
    if not isinstance(results, list):
        results = []
    normalized["results"] = results
    if not isinstance(normalized.get("count"), int):
        normalized["count"] = len(results)
    normalized["meta"] = _normalize_analytics_meta(normalized.get("meta"))
    return normalized


def _normalize_symbol_list_input(symbols: list[str] | str) -> list[str]:
    if isinstance(symbols, str):
        items = [part.strip() for part in symbols.split(",")]
        normalized = [_normalize_identifier_digits(item) for item in items if item]
    elif isinstance(symbols, list):
        normalized = []
        for item in symbols:
            if not isinstance(item, str):
                raise ValueError(
                    "Invalid symbols: list entries must be strings or a comma-separated string."
                )
            stripped = item.strip()
            if stripped:
                normalized.append(_normalize_identifier_digits(stripped))
    else:
        raise ValueError(
            "Invalid symbols: provide a list of symbols or a comma-separated string."
        )
    if not normalized:
        raise ValueError(
            "At least one symbol is required. Provide a list or comma-separated symbols."
        )
    return normalized


def _normalize_depth_levels(levels: int | None) -> int | None:
    if levels is None:
        return None
    if not isinstance(levels, int) or isinstance(levels, bool) or levels < 1 or levels > 20:
        raise ValueError(
            f"Invalid levels: '{levels}'. Must be an integer from 1 to 20."
        )
    return levels


def _normalize_events_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
        raise ValueError(
            f"Invalid limit: '{limit}'. Must be an integer from 1 to 100."
        )
    return limit


def _normalize_trades_recovery(
    date: str | None, after_seq: int | None, cursor: str | None
) -> dict:
    params: dict = {}
    if date is not None:
        _validate_date(date, "date")
        params["date"] = date
    if after_seq is not None:
        if not isinstance(after_seq, int) or isinstance(after_seq, bool) or after_seq < 0:
            raise ValueError(
                f"Invalid after_seq: '{after_seq}'. Must be a non-negative integer."
            )
        params["after_seq"] = after_seq
    if cursor is not None and str(cursor).strip():
        params["cursor"] = str(cursor).strip()
    if ("after_seq" in params or "cursor" in params) and "date" not in params:
        raise ValueError(
            "date (YYYY-MM-DD, Asia/Riyadh) is required with after_seq or cursor."
        )
    return params


def _normalize_trades_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 200:
        raise ValueError(
            f"Invalid limit: '{limit}'. Must be an integer from 1 to 200."
        )
    return limit


def _normalize_depth_response(raw: dict) -> dict:
    normalized = dict(raw) if isinstance(raw, dict) else {}
    normalized.setdefault("symbol", None)
    normalized.setdefault("updated_at", None)
    normalized.setdefault("session", None)
    normalized.setdefault("book_state", None)
    normalized.setdefault("levels", None)
    normalized.setdefault("best_bid", None)
    normalized.setdefault("best_ask", None)
    normalized.setdefault("spread", None)
    normalized.setdefault("spread_bps", None)
    normalized.setdefault("total_bid_quantity_top5", None)
    normalized.setdefault("total_ask_quantity_top5", None)
    normalized.setdefault("level_imbalance", None)
    normalized.setdefault("bids", [])
    normalized.setdefault("asks", [])
    normalized.setdefault("entitled_levels", None)
    return normalized


def _normalize_events_response(raw: dict) -> dict:
    normalized = dict(raw) if isinstance(raw, dict) else {}
    normalized.setdefault("events", [])
    normalized.setdefault("count", None)
    normalized.setdefault("available_types", [])
    return normalized


def _normalize_trades_response(raw: dict) -> dict:
    normalized = dict(raw) if isinstance(raw, dict) else {}
    normalized.setdefault("symbol", None)
    normalized.setdefault("updated_at", None)
    normalized.setdefault("count", None)
    events = normalized.get("events")
    normalized_events: list = []
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                normalized_events.append(event)
                continue
            normalized_event = dict(event)
            # Additive compatibility: preserve `side` exactly when upstream
            # includes it (`buy`, `sell`, or null).
            if "side" in event:
                normalized_event["side"] = event.get("side")
            normalized_events.append(normalized_event)
    else:
        normalized_events = []
    normalized["events"] = normalized_events
    summary = normalized.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.setdefault("event_count", None)
    summary.setdefault("trade_quantity", None)
    summary.setdefault("trade_value", None)
    summary.setdefault("latest_event_time", None)
    normalized["summary"] = summary
    return normalized


def _call_sdk_with_fallback(client: SahmkClient, primary: str, fallback: str, *args, **kwargs):
    method = getattr(client, primary, None)
    if method is None:
        method = getattr(client, fallback, None)
    if method is None:
        raise AttributeError(
            f"SahmkClient has neither '{primary}' nor '{fallback}'. "
            "Upgrade sahmk SDK to a compatible version."
        )
    return method(*args, **kwargs)


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
    normalized_identifier = _normalize_symbol_input(identifier, field_name="identifier")
    client = _get_client()
    try:
        return client.company(normalized_identifier).raw
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_identifier)
        except SahmkError:
            # Keep resolution SDK-backed: if company lookup fails for a
            # non-numeric identifier, attempt resolver-based symbol discovery.
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_identifier, error
            )
            if resolved_symbol and resolved_symbol != normalized_identifier:
                return _to_raw_response(client.company(resolved_symbol))
            raise error


@mcp.tool
def get_financials(
    symbol: Annotated[
        str,
        "Requires exact exchange symbol. If the user provides a company name, first use companies_list. "
        "If a previous tool result included resolved_instrument.symbol, reuse that symbol. "
        "Example: '1120'.",
    ],
    type: Annotated[
        Optional[str],
        "Optional financial view selector (e.g. statement family/profile returned by backend).",
    ] = None,
    period: Annotated[
        Optional[Literal["annual", "quarterly", "auto"]],
        "Optional period selector: annual, quarterly, or auto. If both period and statement_period are provided, period takes precedence.",
    ] = None,
    statement_period: Annotated[
        Optional[Literal["annual", "quarterly", "auto"]],
        "Optional explicit statement period selector (annual, quarterly, or auto). Ignored when period is provided.",
    ] = None,
    history: Annotated[
        Optional[str],
        "Optional history window selector. Common values: latest, 1y, 3y, 5y, 10y, max (backend-dependent).",
    ] = None,
    metrics: Annotated[
        Optional[str],
        "Optional metrics profile selector. Common values: core, extended (backend-dependent).",
    ] = None,
    result: Annotated[
        Optional[str],
        "Optional result shaping selector. Common values: series, latest, raw (backend-dependent).",
    ] = None,
    include_partial: Annotated[
        Optional[bool],
        "Optionally include partial/incomplete statement periods when available.",
    ] = None,
) -> dict:
    """Get company financial statements and key financial data.
    Use this for income statement, balance sheet, and cash flow requests.
    Requires exact exchange symbol."""
    normalized_symbol = _normalize_symbol_input(symbol)
    client = _get_client()
    effective_statement_period = (
        period if period is not None else statement_period
    )
    financials_kwargs: dict = {}
    if type is not None:
        financials_kwargs["type"] = type
    if effective_statement_period is not None:
        financials_kwargs["statement_period"] = effective_statement_period
    if history is not None:
        financials_kwargs["history"] = history
    if metrics is not None:
        financials_kwargs["metrics"] = metrics
    if result is not None:
        financials_kwargs["result"] = result
    if include_partial is not None:
        financials_kwargs["include_partial"] = include_partial
    try:
        raw = _to_raw_response(client.financials(normalized_symbol, **financials_kwargs))
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_symbol)
        except SahmkError:
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_symbol, error
            )
            if resolved_symbol and resolved_symbol != normalized_symbol:
                raw = _to_raw_response(client.financials(resolved_symbol, **financials_kwargs))
            else:
                raise error
    return _normalize_financials_response(raw)


@mcp.tool
def get_ratios(
    symbol: Annotated[
        str,
        "Requires exact exchange symbol. If the user provides a company name, first use companies_list. "
        "If a previous tool result included resolved_instrument.symbol, reuse that symbol. "
        "Example: '1120'.",
    ],
    history: Annotated[
        Literal["latest", "3y", "5y", "10y", "max"],
        "History window for ratios.",
    ] = "latest",
    period: Annotated[
        Literal["annual", "quarterly"],
        "Statement period for ratios.",
    ] = "annual",
    metrics: Annotated[
        Literal["core", "extended"],
        "Metrics profile for ratios.",
    ] = "core",
) -> dict:
    """Get calculated financial ratios for one Saudi-listed company. Starter returns latest annual core ratios; Pro supports history, quarterly, and extended metrics."""
    normalized_symbol = _normalize_symbol_input(symbol)
    client = _get_client()
    try:
        raw = _to_raw_response(
            _call_sdk_with_fallback(
                client,
                "get_ratios",
                "ratios",
                normalized_symbol,
                history=history,
                period=period,
                metrics=metrics,
            )
        )
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_symbol)
        except SahmkError:
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_symbol, error
            )
            if resolved_symbol and resolved_symbol != normalized_symbol:
                raw = _to_raw_response(
                    _call_sdk_with_fallback(
                        client,
                        "get_ratios",
                        "ratios",
                        resolved_symbol,
                        history=history,
                        period=period,
                        metrics=metrics,
                    )
                )
            else:
                raise error
    return _normalize_ratios_response(raw)


@mcp.tool
def compare_symbols(
    symbols: Annotated[
        list[str] | str,
        "Symbols to compare as a list (preferred) or comma-separated string. "
        "Starter supports up to 3 symbols; Pro supports up to 10.",
    ],
    metrics: Annotated[
        str,
        "Metrics profile, e.g. 'core' or 'extended'. Default 'core'.",
    ] = "core",
) -> dict:
    """Compare multiple Saudi-listed companies using normalized financial ratios and key metrics. Starter supports up to 3 symbols; Pro supports up to 10."""
    normalized_symbols = _normalize_symbol_list_input(symbols)
    client = _get_client()
    try:
        raw = _to_raw_response(
            _call_sdk_with_fallback(
                client,
                "compare_symbols",
                "compare",
                normalized_symbols,
                metrics=metrics,
            )
        )
    except SahmkError as error:
        if not _is_unknown_identifier_error(error):
            raise error
        resolved_symbols = [
            _resolve_symbol_from_identifier(client, value) or value
            for value in normalized_symbols
        ]
        if resolved_symbols == normalized_symbols:
            raise error
        raw = _to_raw_response(
            _call_sdk_with_fallback(
                client,
                "compare_symbols",
                "compare",
                resolved_symbols,
                metrics=metrics,
            )
        )
    return _normalize_compare_response(raw)


@mcp.tool
def get_dividends(
    symbol: Annotated[
        str,
        "Requires exact exchange symbol. If the user provides a company name, first use companies_list. "
        "If a previous tool result included resolved_instrument.symbol, reuse that symbol. "
        "Example: '1120'.",
    ],
) -> dict:
    """Get company dividend history and yield data.
    Use this when the user asks for dividends or payout history.
    Requires exact exchange symbol."""
    normalized_symbol = _normalize_symbol_input(symbol)
    client = _get_client()
    try:
        raw = client.dividends(normalized_symbol).raw
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_symbol)
        except SahmkError:
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_symbol, error
            )
            if resolved_symbol and resolved_symbol != normalized_symbol:
                raw = _to_raw_response(client.dividends(resolved_symbol))
            else:
                raise error
    return _normalize_dividends_response(raw)


@mcp.tool
def get_depth(
    symbol: Annotated[
        str,
        "Requires exact exchange symbol. If the user provides a company name, first use companies_list. "
        "If a previous tool result included resolved_instrument.symbol, reuse that symbol. "
        "Example: '2222'.",
    ],
    levels: Annotated[
        Optional[int],
        "Optional number of book levels to request (1-20). Backend default is 5; "
        "entitlement may return fewer levels than requested.",
    ] = None,
) -> dict:
    """Get market depth (order book) for a Saudi stock.
    Use this for bid/ask ladder, spread, imbalance, and liquidity at the top of book.
    Requires exact exchange symbol. Plan/entitlement-gated by the API."""
    normalized_symbol = _normalize_symbol_input(symbol)
    normalized_levels = _normalize_depth_levels(levels)
    client = _get_client()
    try:
        raw = _to_raw_response(
            client.depth(normalized_symbol, levels=normalized_levels)
        )
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_symbol)
        except SahmkError:
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_symbol, error
            )
            if resolved_symbol and resolved_symbol != normalized_symbol:
                raw = _to_raw_response(
                    client.depth(resolved_symbol, levels=normalized_levels)
                )
            else:
                raise error
    return _normalize_depth_response(raw)


@mcp.tool
def get_trades(
    symbol: Annotated[
        str,
        "Requires exact exchange symbol. If the user provides a company name, first use companies_list. "
        "If a previous tool result included resolved_instrument.symbol, reuse that symbol. "
        "Example: '2222'.",
    ],
    limit: Annotated[
        Optional[int],
        "Optional page size (1-200). Backend default is typically 50.",
    ] = None,
    date: Annotated[
        Optional[str],
        "Optional session date YYYY-MM-DD (Asia/Riyadh). Reads that session from the recent "
        "tape (about three days) in receive order and adds a `page` object. Omit for the newest prints.",
    ] = None,
    after_seq: Annotated[
        Optional[int],
        "Optional: only prints with a greater trade_seq. Requires date. A filter, not a cursor.",
    ] = None,
    cursor: Annotated[
        Optional[str],
        "Optional page.next_cursor from the previous page. Requires date.",
    ] = None,
) -> dict:
    """Get live trade prints for a Saudi stock (Pro+ plan).
    Without date: the most recent prints, newest first.
    With date: one session in receive order; follow page.next_cursor while page.has_more is true.
    Each print has trade_seq, price, quantity, value, optional side (`buy`/`sell`/`null`),
    and on dated calls market_session. This is the recent tape, not official session volume.
    Requires exact exchange symbol."""
    normalized_symbol = _normalize_symbol_input(symbol)
    normalized_limit = _normalize_trades_limit(limit)
    recovery = _normalize_trades_recovery(date, after_seq, cursor)
    client = _get_client()
    try:
        raw = _to_raw_response(
            client.trades(normalized_symbol, limit=normalized_limit, **recovery)
        )
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_symbol)
        except SahmkError:
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_symbol, error
            )
            if resolved_symbol and resolved_symbol != normalized_symbol:
                raw = _to_raw_response(
                    client.trades(resolved_symbol, limit=normalized_limit, **recovery)
                )
            else:
                raise error
    return _normalize_trades_response(raw)


@mcp.tool
def get_events(
    symbol: Annotated[
        Optional[str],
        "Optional exact exchange symbol filter. Omit for market-wide recent events. "
        "Example: '1120'.",
    ] = None,
    limit: Annotated[
        Optional[int],
        "Optional max number of events to return (1-100). Backend default is typically 20.",
    ] = None,
) -> dict:
    """Get AI-generated stock event summaries (Pro+ plan).
    Use this for recent corporate/news-style events with type, importance, and sentiment.
    Optionally filter by exact exchange symbol."""
    normalized_symbol = (
        _normalize_symbol_input(symbol) if symbol is not None else None
    )
    normalized_limit = _normalize_events_limit(limit)
    client = _get_client()
    try:
        raw = _to_raw_response(
            client.events(symbol=normalized_symbol, limit=normalized_limit)
        )
    except SahmkError as error:
        if normalized_symbol is None:
            raise error
        try:
            _raise_if_ambiguous_identifier(error, normalized_symbol)
        except SahmkError:
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_symbol, error
            )
            if resolved_symbol and resolved_symbol != normalized_symbol:
                raw = _to_raw_response(
                    client.events(symbol=resolved_symbol, limit=normalized_limit)
                )
            else:
                raise error
    return _normalize_events_response(raw)


@mcp.tool
def get_historical(
    symbol: Annotated[
        str,
        "Requires exact exchange symbol. If the user provides a company name, first use companies_list. "
        "If a previous tool result included resolved_instrument.symbol, reuse that symbol. "
        "Example: '1120'.",
    ],
    from_date: Annotated[
        Optional[str], "Start date in YYYY-MM-DD format (default: 30 days ago)"
    ] = None,
    to_date: Annotated[
        Optional[str], "End date in YYYY-MM-DD format (default: today)"
    ] = None,
    interval: Annotated[
        Optional[str],
        "Bar size. Preferred: '1min', '5min', '15min', '30min', '60min', '1d', '1w', '1mo' "
        "(default: '1d'). Legacy aliases accepted: '30m'->'30min', '60m'->'60min', "
        "'1m'->'1mo' (monthly, NOT one-minute). Plan and date-window limits apply to intraday intervals.",
    ] = None,
) -> dict:
    """Get historical OHLCV price data for a Saudi stock over a date range.
    Use this when the user asks for past prices, price trends, or chart-style historical data."""
    _validate_date(from_date, "from_date")
    _validate_date(to_date, "to_date")
    if interval and interval not in _HISTORICAL_INTERVALS:
        raise ValueError(
            f"Invalid interval: '{interval}'. Must be one of: "
            "1min, 5min, 15min, 30min, 60min, 1d, 1w, 1mo "
            "(legacy aliases: 30m, 60m, 1m = monthly)."
        )
    normalized_symbol = _normalize_symbol_input(symbol)
    client = _get_client()
    try:
        return client.historical(
            normalized_symbol, from_date=from_date, to_date=to_date, interval=interval
        ).raw
    except SahmkError as error:
        try:
            _raise_if_ambiguous_identifier(error, normalized_symbol)
        except SahmkError:
            resolved_symbol = _resolve_symbol_from_unknown_identifier_error(
                client, normalized_symbol, error
            )
            if resolved_symbol and resolved_symbol != normalized_symbol:
                return _to_raw_response(
                    client.historical(
                        resolved_symbol,
                        from_date=from_date,
                        to_date=to_date,
                        interval=interval,
                    )
                )
            raise error


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



# -----------------------------------------------------------------------------
# Portfolios
#
# Names, titles, and safety hints match the hosted SAHMK MCP server so a client
# sees the same tools locally and remotely.
# -----------------------------------------------------------------------------


def _portfolio_annotations(title: str, *, write: bool = False, destructive: bool = False) -> dict:
    return {
        "title": title,
        "readOnlyHint": not write,
        "idempotentHint": not write,
        "destructiveHint": destructive,
        "openWorldHint": False,
    }


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Invalid {name}: '{value}'. Must be a positive integer.")
    return value


def _normalize_transaction_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _PORTFOLIO_TRANSACTION_TYPES:
        raise ValueError(
            f"Invalid transaction_type: '{value}'. Must be one of: "
            + ", ".join(_PORTFOLIO_TRANSACTION_TYPES)
            + "."
        )
    return normalized


_PortfolioId = Annotated[int, "Portfolio id (positive integer) from get_portfolios."]


@mcp.tool(annotations=_portfolio_annotations("List Portfolios"))
def get_portfolios(
    workspace_id: Annotated[Optional[int], "Optional workspace id filter."] = None,
) -> dict:
    """List the user's SAHMK portfolios, most recently updated first."""
    if workspace_id is not None:
        workspace_id = _positive_int(workspace_id, "workspace_id")
    return _get_client().portfolios(workspace_id=workspace_id)


@mcp.tool(annotations=_portfolio_annotations("Get Portfolio"))
def get_portfolio(portfolio_id: _PortfolioId) -> dict:
    """Get one portfolio by id."""
    return _get_client().portfolio(_positive_int(portfolio_id, "portfolio_id"))


@mcp.tool(annotations=_portfolio_annotations("Create Portfolio", write=True))
def create_portfolio(
    name: Annotated[str, "Portfolio name. Must be unique for this user."],
    description: Annotated[Optional[str], "Optional description."] = None,
    workspace: Annotated[Optional[int], "Optional workspace id to link."] = None,
    metadata: Annotated[Optional[dict], "Optional object of your own fields."] = None,
) -> dict:
    """Create a portfolio."""
    if not str(name or "").strip():
        raise ValueError("name is required.")
    if workspace is not None:
        workspace = _positive_int(workspace, "workspace")
    return _get_client().create_portfolio(
        name, description=description, workspace=workspace, metadata=metadata
    )


@mcp.tool(annotations=_portfolio_annotations("List Portfolio Transactions"))
def get_portfolio_transactions(portfolio_id: _PortfolioId) -> dict:
    """List the full transaction ledger for one portfolio, newest first."""
    return _get_client().portfolio_transactions(_positive_int(portfolio_id, "portfolio_id"))


@mcp.tool(annotations=_portfolio_annotations("Create Portfolio Transaction", write=True))
def create_portfolio_transaction(
    portfolio_id: _PortfolioId,
    transaction_type: Annotated[
        Optional[Literal["deposit", "buy", "sell", "withdrawal", "dividend", "fee"]],
        "Single mode: transaction type.",
    ] = None,
    amount_sar: Annotated[Optional[float], "Single mode: amount in SAR (required)."] = None,
    symbol: Annotated[Optional[str], "Stock symbol for buy, sell, and dividend."] = None,
    quantity: Annotated[Optional[float], "Share quantity for buy and sell."] = None,
    unit_price_sar: Annotated[Optional[float], "Price per share in SAR for buy and sell."] = None,
    fee_sar: Annotated[Optional[float], "Optional fee in SAR."] = None,
    executed_at: Annotated[Optional[str], "Optional ISO-8601 timestamp."] = None,
    notes: Annotated[Optional[str], "Optional note."] = None,
    metadata: Annotated[Optional[dict], "Optional object of your own fields."] = None,
    idempotency_key: Annotated[
        Optional[str], "Optional key; resending the same key does not create a duplicate."
    ] = None,
    transactions: Annotated[
        Optional[list[dict]],
        "Batch mode: list of transactions (each needs transaction_type and amount_sar). "
        "Do not combine with single-mode fields.",
    ] = None,
    batch_idempotency_key: Annotated[
        Optional[str], "Batch mode: required key for the whole batch."
    ] = None,
) -> dict:
    """Create one portfolio transaction or an explicit atomic batch.
    Transactions are append-only by executed_at order; backdated entries before the
    latest executed_at are rejected."""
    pid = _positive_int(portfolio_id, "portfolio_id")
    client = _get_client()
    if transactions is not None:
        single_fields = {
            "transaction_type": transaction_type,
            "amount_sar": amount_sar,
            "symbol": symbol,
            "quantity": quantity,
            "unit_price_sar": unit_price_sar,
            "fee_sar": fee_sar,
            "executed_at": executed_at,
            "notes": notes,
            "metadata": metadata,
            "idempotency_key": idempotency_key,
        }
        if any(value is not None for value in single_fields.values()):
            raise ValueError(
                "Batch mode cannot include single-transaction fields. "
                "Send either transactions + batch_idempotency_key, or single transaction fields."
            )
        if not isinstance(transactions, list) or not transactions:
            raise ValueError("transactions must be a non-empty list.")
        if not str(batch_idempotency_key or "").strip():
            raise ValueError("batch_idempotency_key is required when transactions is provided.")
        normalized = []
        for item in transactions:
            if not isinstance(item, dict):
                raise ValueError("Each transaction must be an object.")
            entry = dict(item)
            entry["transaction_type"] = _normalize_transaction_type(item.get("transaction_type"))
            if entry.get("amount_sar") is None:
                raise ValueError("Each transaction needs amount_sar.")
            normalized.append(entry)
        return client.create_portfolio_transactions(
            pid, normalized, str(batch_idempotency_key).strip()
        )

    if transaction_type is None:
        raise ValueError("transaction_type is required.")
    if amount_sar is None:
        raise ValueError("amount_sar is required.")
    return client.create_portfolio_transaction(
        pid,
        _normalize_transaction_type(transaction_type),
        amount_sar,
        symbol=_normalize_symbol_input(symbol) if symbol is not None else None,
        quantity=quantity,
        unit_price_sar=unit_price_sar,
        fee_sar=fee_sar,
        executed_at=executed_at,
        notes=notes,
        metadata=metadata,
        idempotency_key=idempotency_key,
    )


@mcp.tool(
    annotations=_portfolio_annotations("Set Portfolio Holdings", write=True, destructive=True)
)
def set_portfolio_holdings(
    portfolio_id: _PortfolioId,
    scope: Annotated[
        Literal["full", "partial"],
        "'full': the portfolio should hold exactly these holdings. 'partial': only the listed symbols change.",
    ],
    cash_policy: Annotated[
        Literal["auto_fund", "require_cash"],
        "auto_fund: when the plan needs cash, existing cash is consumed first and only the remaining "
        "shortfall is auto-deposited; when the plan releases cash, auto-withdrawal is limited to the "
        "amount released by plan actions and never withdraws pre-existing cash. require_cash: no "
        "automatic deposits or withdrawals; the plan is blocked if cash would go negative, and "
        "released money stays in cash.",
    ],
    holdings: Annotated[
        list[dict],
        "Target holdings: list of {symbol, quantity, avg_cost_sar}.",
    ],
    dry_run: Annotated[
        bool, "True (default) previews the plan. False applies it and needs plan_token."
    ] = True,
    plan_token: Annotated[Optional[str], "plan.plan_token from the dry run. Required to apply."] = None,
    expected_latest_transaction_id: Annotated[
        Optional[int], "Optional guard: apply fails if the ledger moved since the dry run."
    ] = None,
) -> dict:
    """Set target holdings for a portfolio with a dry-run/apply plan token flow.
    Run with dry_run=true first, show the user the plan, and apply only after they confirm.
    Applying writes ledger transactions."""
    pid = _positive_int(portfolio_id, "portfolio_id")
    if not isinstance(holdings, list):
        raise ValueError("holdings is required.")
    for item in holdings:
        if not isinstance(item, dict):
            raise ValueError("Each holding must be an object with symbol, quantity, avg_cost_sar.")
        missing = [k for k in ("symbol", "quantity", "avg_cost_sar") if item.get(k) is None]
        if missing:
            raise ValueError(f"Each holding needs symbol, quantity, avg_cost_sar (missing: {', '.join(missing)}).")
    if not dry_run and not str(plan_token or "").strip():
        raise ValueError("plan_token from a dry run is required when dry_run is false.")
    if expected_latest_transaction_id is not None:
        expected_latest_transaction_id = _positive_int(
            expected_latest_transaction_id, "expected_latest_transaction_id"
        )
    return _get_client().set_portfolio_holdings(
        pid,
        holdings,
        scope,
        cash_policy,
        dry_run=dry_run,
        plan_token=plan_token,
        expected_latest_transaction_id=expected_latest_transaction_id,
    )


@mcp.tool(
    annotations=_portfolio_annotations(
        "Reverse Portfolio Transaction", write=True, destructive=True
    )
)
def reverse_portfolio_transaction(
    portfolio_id: _PortfolioId,
    transaction_id: Annotated[int, "Transaction id to reverse."],
    notes: Annotated[Optional[str], "Optional note."] = None,
    metadata: Annotated[Optional[dict], "Optional object of your own fields."] = None,
) -> dict:
    """Reverse a transaction by id. Only the portfolio's latest transaction can be reversed."""
    return _get_client().reverse_portfolio_transaction(
        _positive_int(portfolio_id, "portfolio_id"),
        _positive_int(transaction_id, "transaction_id"),
        notes=notes,
        metadata=metadata,
    )


@mcp.tool(annotations=_portfolio_annotations("Get Portfolio Summary"))
def get_portfolio_summary(portfolio_id: _PortfolioId) -> dict:
    """Get cash, holdings, and P&L for one portfolio."""
    return _get_client().portfolio_summary(_positive_int(portfolio_id, "portfolio_id"))


@mcp.tool(annotations=_portfolio_annotations("Get Portfolio Performance"))
def get_portfolio_performance(
    portfolio_id: _PortfolioId,
    days: Annotated[Optional[int], "Optional window in days (backend default: 30)."] = None,
) -> dict:
    """Get the daily equity series for one portfolio."""
    if days is not None:
        days = _positive_int(days, "days")
    return _get_client().portfolio_performance(
        _positive_int(portfolio_id, "portfolio_id"), days=days
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
