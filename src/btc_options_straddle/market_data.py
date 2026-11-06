
import json
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from btc_options_straddle.orderbook_validator import (
    OrderBookSnapshot,
    PriceLevel,
)


TESTNET_BASE_URL = "https://api-testnet.bybit.com"
ORDERBOOK_ENDPOINT = "/v5/market/orderbook"


class MarketDataError(Exception):
    """Raised when Bybit Testnet market data cannot be retrieved or parsed."""


def _parse_levels(raw_levels, side_name):
    if not isinstance(raw_levels, list):
        raise MarketDataError(f"Invalid {side_name} levels format")

    levels = []

    for item in raw_levels:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            raise MarketDataError(f"Malformed {side_name} level")

        try:
            price = Decimal(str(item[0]))
            quantity = Decimal(str(item[1]))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise MarketDataError(
                f"Invalid numeric value in {side_name} level"
            ) from exc

        if not price.is_finite() or not quantity.is_finite():
            raise MarketDataError(
                f"Non-finite numeric value in {side_name} level"
            )

        levels.append(
            PriceLevel(
                price=price,
                quantity=quantity,
            )
        )

    return levels


def normalize_orderbook_response(
    payload: dict,
    expected_symbol: str,
) -> OrderBookSnapshot:
    if not isinstance(payload, dict):
        raise MarketDataError("Invalid API response format")

    if payload.get("retCode") != 0:
        raise MarketDataError(
            f"Bybit API error: {payload.get('retCode')} "
            f"- {payload.get('retMsg')}"
        )

    result = payload.get("result")

    if not isinstance(result, dict):
        raise MarketDataError("Missing order-book result")

    actual_symbol = result.get("s")

    if actual_symbol != expected_symbol:
        raise MarketDataError(
            f"Symbol mismatch: expected {expected_symbol}, "
            f"received {actual_symbol}"
        )

    try:
        update_id = int(result["u"])
        timestamp_ms = int(result["ts"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketDataError(
            "Missing or invalid order-book metadata"
        ) from exc

    bids = _parse_levels(result.get("b"), "bid")
    asks = _parse_levels(result.get("a"), "ask")

    # Preserve empty books and invalid update IDs.
    # The order-book validator will reject them.
    return OrderBookSnapshot(
        symbol=expected_symbol,
        bids=bids,
        asks=asks,
        update_id=update_id,
        timestamp_ms=timestamp_ms,
    )


def fetch_testnet_orderbook(
    symbol: str,
    limit: int = 5,
    timeout_seconds: int = 15,
) -> OrderBookSnapshot:
    if not symbol:
        raise ValueError("Instrument symbol is required")

    if not 1 <= limit <= 25:
        raise ValueError("Order-book limit must be between 1 and 25")

    params = urlencode({
        "category": "option",
        "symbol": symbol,
        "limit": limit,
    })

    url = f"{TESTNET_BASE_URL}{ORDERBOOK_ENDPOINT}?{params}"

    request = Request(
        url,
        headers={
            "User-Agent": "BTC-Options-Straddle/1.0",
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MarketDataError(
            f"Testnet order-book request failed for {symbol}: {exc}"
        ) from exc

    return normalize_orderbook_response(payload, symbol)
