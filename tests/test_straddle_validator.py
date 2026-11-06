
from decimal import Decimal

from btc_options_straddle.orderbook_validator import (
    InstrumentConstraints,
    OrderBookSnapshot,
    PriceLevel,
    validate_orderbook,
)
from btc_options_straddle.straddle_validator import validate_straddle


CONSTRAINTS = InstrumentConstraints(
    min_quantity=Decimal("0.01"),
    quantity_increment=Decimal("0.01"),
    price_increment=Decimal("5"),
)


def make_valid_leg(
    symbol,
    bid,
    ask,
    quantity=Decimal("0.10"),
):

    snapshot = OrderBookSnapshot(
        symbol=symbol,
        bids=[PriceLevel(Decimal(bid), Decimal("1.00"))],
        asks=[PriceLevel(Decimal(ask), Decimal("1.00"))],
        update_id=100,
        timestamp_ms=10000,
    )

    return validate_orderbook(
    snapshot,
    CONSTRAINTS,
    quantity,
    now_ms=11000,
    )


def test_valid_call_and_put_straddle():
    call = make_valid_leg("BTC-CALL", "690", "695", Decimal("0.10"))
    put = make_valid_leg(
        "BTC-PUT",
        "730",
        "735",
        Decimal("0.10"),
    )

    result = validate_straddle(call, put)

    assert result.valid
    assert result.entry_credit_per_unit == Decimal("1420")
    assert result.buyback_cost_per_unit == Decimal("1430")
    assert result.entry_credit_total == Decimal("142.00")
    assert result.buyback_cost_total == Decimal("143.00")


def test_reject_invalid_call_leg():
    call = make_valid_leg("BTC-CALL", "690", "695")

    invalid_snapshot = OrderBookSnapshot(
        symbol="BTC-PUT",
        bids=[],
        asks=[],
        update_id=-1,
        timestamp_ms=10000,
    )

    put = validate_orderbook(
        invalid_snapshot,
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000,
    )

    result = validate_straddle(call, put)

    assert not result.valid
    assert "PUT order book validation failed" in result.reasons


def test_reject_quantity_mismatch():
    call = make_valid_leg("BTC-CALL", "690", "695", Decimal("0.10"))
    put = make_valid_leg(
        "BTC-PUT",
        "730",
        "735",
        Decimal("0.20"),
    )


    result = validate_straddle(call, put)

    assert not result.valid
    assert "CALL and PUT quantities must match" in result.reasons


def test_reject_missing_vwap():
    from dataclasses import replace

    call = make_valid_leg("BTC-CALL", "690", "695")
    put = make_valid_leg("BTC-PUT", "730", "735")

    invalid_put = replace(
        put,
        entry_vwap=None,
        exit_vwap=None,
    )

    result = validate_straddle(call, invalid_put)

    assert not result.valid
    assert "PUT VWAP estimates are unavailable" in result.reasons
def test_accept_synchronized_quotes():
    call = make_valid_leg("BTC-CALL", "690", "695")
    put = make_valid_leg("BTC-PUT", "730", "735")

    result = validate_straddle(call, put)

    assert result.valid
    assert result.quote_skew_ms == 0


def test_reject_unsynchronized_quotes():
    from dataclasses import replace

    call = make_valid_leg("BTC-CALL", "690", "695")
    put = make_valid_leg("BTC-PUT", "730", "735")

    put = replace(
        put,
        snapshot_timestamp_ms=call.snapshot_timestamp_ms + 1500,
    )

    result = validate_straddle(
        call,
        put,
        max_quote_skew_ms=1000,
    )

    assert not result.valid
    assert result.quote_skew_ms == 1500
    assert any(
        "timestamp difference too large" in reason
        for reason in result.reasons
    )


def test_reject_missing_snapshot_timestamp():
    from dataclasses import replace

    call = make_valid_leg("BTC-CALL", "690", "695")
    put = make_valid_leg("BTC-PUT", "730", "735")

    put = replace(put, snapshot_timestamp_ms=None)

    result = validate_straddle(call, put)

    assert not result.valid
    assert (
        "CALL or PUT snapshot timestamp is unavailable"
        in result.reasons
    )
