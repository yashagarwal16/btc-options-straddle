
import pytest
from decimal import Decimal

from btc_options_straddle.market_data import (
    MarketDataError,
    normalize_orderbook_response,
)


SYMBOL = "BTC-7NOV26-75750-C-USDT"


def make_response(
    bids=None,
    asks=None,
    update_id=12345,
    timestamp=1793954628089,
    symbol=SYMBOL,
):
    return {
        "retCode": 0,
        "retMsg": "SUCCESS",
        "result": {
            "s": symbol,
            "b": bids if bids is not None else [["690", "1.00"]],
            "a": asks if asks is not None else [["695", "1.00"]],
            "u": update_id,
            "seq": 123456,
            "ts": timestamp,
        },
    }


def test_normalize_valid_orderbook():
    snapshot = normalize_orderbook_response(
        make_response(),
        SYMBOL,
    )

    assert snapshot.symbol == SYMBOL
    assert snapshot.update_id == 12345
    assert snapshot.timestamp_ms == 1793954628089
    assert snapshot.bids[0].price == Decimal("690")
    assert snapshot.asks[0].price == Decimal("695")


def test_normalize_empty_orderbook():
    snapshot = normalize_orderbook_response(
        make_response(bids=[], asks=[]),
        SYMBOL,
    )

    assert snapshot.bids == []
    assert snapshot.asks == []


def test_preserve_negative_update_id():
    snapshot = normalize_orderbook_response(
        make_response(update_id=-1),
        SYMBOL,
    )

    assert snapshot.update_id == -1


def test_reject_symbol_mismatch():
    with pytest.raises(MarketDataError, match="Symbol mismatch"):
        normalize_orderbook_response(
            make_response(symbol="BTC-WRONG-SYMBOL"),
            SYMBOL,
        )


def test_reject_bybit_api_error():
    payload = {
        "retCode": 10001,
        "retMsg": "Invalid request",
    }

    with pytest.raises(MarketDataError, match="Bybit API error"):
        normalize_orderbook_response(payload, SYMBOL)


def test_reject_missing_orderbook_result():
    payload = {
        "retCode": 0,
        "retMsg": "SUCCESS",
    }

    with pytest.raises(MarketDataError, match="Missing order-book result"):
        normalize_orderbook_response(payload, SYMBOL)


def test_reject_malformed_price_level():
    with pytest.raises(MarketDataError, match="Malformed bid level"):
        normalize_orderbook_response(
            make_response(bids=[["690"]]),
            SYMBOL,
        )



@pytest.mark.parametrize(
    "bad_value",
    ["NaN", "Infinity", "-Infinity"],
)
@pytest.mark.parametrize("side", ["bids", "asks"])
def test_reject_non_finite_orderbook_values(bad_value, side):
    levels = [[bad_value, "1.00"]]

    payload = make_response(**{side: levels})

    with pytest.raises(
        MarketDataError,
        match="Non-finite numeric value",
    ):
        normalize_orderbook_response(payload, SYMBOL)


@pytest.mark.parametrize(
    "bad_value",
    ["not-a-number", "invalid"],
)
def test_reject_malformed_numeric_values(bad_value):
    with pytest.raises(
        MarketDataError,
        match="Invalid numeric value",
    ):
        normalize_orderbook_response(
            make_response(bids=[[bad_value, "1.00"]]),
            SYMBOL,
        )
