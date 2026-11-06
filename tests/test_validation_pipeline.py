
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from btc_options_straddle.instrument_selector import StraddleSelection
from btc_options_straddle.market_data import MarketDataError
from btc_options_straddle.orderbook_validator import (
    InstrumentConstraints,
    OrderBookSnapshot,
    PriceLevel,
)
from btc_options_straddle.validation_pipeline import (
    validate_selected_straddle,
)


CONSTRAINTS = InstrumentConstraints(
    min_quantity=Decimal("0.01"),
    quantity_increment=Decimal("0.01"),
    price_increment=Decimal("5"),
)

SELECTION = StraddleSelection(
    underlying_price=Decimal("76000"),
    expiry=datetime(2026, 11, 7, tzinfo=timezone.utc),
    strike=76000.0,
    call_symbol="BTC-TEST-C-USDT",
    put_symbol="BTC-TEST-P-USDT",
    call_constraints=CONSTRAINTS,
    put_constraints=CONSTRAINTS,
)

NOW_MS = 11000
QUANTITY = Decimal("0.10")


def make_book(symbol, bids=None, asks=None, update_id=100, timestamp_ms=10000):
    return OrderBookSnapshot(
        symbol=symbol,
        bids=bids if bids is not None else [
            PriceLevel(Decimal("690"), Decimal("1.00"))
        ],
        asks=asks if asks is not None else [
            PriceLevel(Decimal("695"), Decimal("1.00"))
        ],
        update_id=update_id,
        timestamp_ms=timestamp_ms,
    )


def install_mock_books(monkeypatch, call_book=None, put_book=None):
    books = {
        SELECTION.call_symbol: call_book or make_book(SELECTION.call_symbol),
        SELECTION.put_symbol: put_book or make_book(SELECTION.put_symbol),
    }

    def mock_fetch(symbol, limit=5):
        assert limit == 25
        return books[symbol]

    monkeypatch.setattr(
        "btc_options_straddle.validation_pipeline.fetch_testnet_orderbook",
        mock_fetch,
    )


def test_pipeline_accepts_valid_straddle(monkeypatch):
    install_mock_books(monkeypatch)

    result = validate_selected_straddle(
        SELECTION,
        QUANTITY,
        now_ms=NOW_MS,
    )

    assert result.call_result.valid
    assert result.put_result.valid
    assert result.straddle_result.valid
    assert result.straddle_result.entry_credit_per_unit == Decimal("1380")
    assert result.straddle_result.buyback_cost_per_unit == Decimal("1390")


def test_pipeline_rejects_empty_call_book(monkeypatch):
    call_book = make_book(
        SELECTION.call_symbol,
        bids=[],
        asks=[],
    )
    install_mock_books(monkeypatch, call_book=call_book)

    result = validate_selected_straddle(
        SELECTION,
        QUANTITY,
        now_ms=NOW_MS,
    )

    assert not result.call_result.valid
    assert not result.straddle_result.valid


def test_pipeline_rejects_empty_put_book(monkeypatch):
    put_book = make_book(
        SELECTION.put_symbol,
        bids=[],
        asks=[],
    )
    install_mock_books(monkeypatch, put_book=put_book)

    result = validate_selected_straddle(
        SELECTION,
        QUANTITY,
        now_ms=NOW_MS,
    )

    assert result.call_result.valid
    assert not result.put_result.valid
    assert not result.straddle_result.valid


def test_pipeline_rejects_invalid_update_id(monkeypatch):
    call_book = make_book(
        SELECTION.call_symbol,
        update_id=-1,
    )
    install_mock_books(monkeypatch, call_book=call_book)

    result = validate_selected_straddle(
        SELECTION,
        QUANTITY,
        now_ms=NOW_MS,
    )

    assert not result.call_result.valid
    assert not result.straddle_result.valid


def test_pipeline_rejects_insufficient_depth(monkeypatch):
    call_book = make_book(
        SELECTION.call_symbol,
        bids=[
            PriceLevel(Decimal("690"), Decimal("0.04"))
        ],
        asks=[
            PriceLevel(Decimal("695"), Decimal("0.04"))
        ],
    )
    install_mock_books(monkeypatch, call_book=call_book)

    result = validate_selected_straddle(
        SELECTION,
        QUANTITY,
        now_ms=NOW_MS,
    )

    assert not result.call_result.valid
    assert not result.straddle_result.valid


def test_pipeline_rejects_excessive_quote_skew(monkeypatch):
    call_book = make_book(
        SELECTION.call_symbol,
        timestamp_ms=8000,
    )
    put_book = make_book(
        SELECTION.put_symbol,
        timestamp_ms=9501,
    )

    install_mock_books(
        monkeypatch,
        call_book=call_book,
        put_book=put_book,
    )

    result = validate_selected_straddle(
        SELECTION,
        QUANTITY,
        now_ms=NOW_MS,
        max_quote_skew_ms=1000,
    )

    assert result.call_result.valid
    assert result.put_result.valid
    assert not result.straddle_result.valid
    assert result.straddle_result.quote_skew_ms == 1501

def test_pipeline_propagates_market_data_error(monkeypatch):
    def mock_fetch(symbol, limit=5):
        raise MarketDataError("Simulated Testnet API failure")

    monkeypatch.setattr(
        "btc_options_straddle.validation_pipeline.fetch_testnet_orderbook",
        mock_fetch,
    )

    with pytest.raises(
        MarketDataError,
        match="Simulated Testnet API failure",
    ):
        validate_selected_straddle(
            SELECTION,
            QUANTITY,
            now_ms=NOW_MS,
        )
