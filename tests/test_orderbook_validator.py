import pytest
from decimal import Decimal
from btc_options_straddle.orderbook_validator import calculate_vwap
from btc_options_straddle.orderbook_validator import (
    InstrumentConstraints,
    OrderBookSnapshot,
    PriceLevel,
    validate_orderbook,
)


CONSTRAINTS = InstrumentConstraints(
    min_quantity=Decimal("0.01"),
    quantity_increment=Decimal("0.01"),
    price_increment=Decimal("5"),
)


def make_book(
    bids=None,
    asks=None,
    update_id=100,
    timestamp_ms=10000,
):
    return OrderBookSnapshot(
        symbol="BTC-TEST-C-USDT",
        bids=bids if bids is not None else [
            PriceLevel(Decimal("690"), Decimal("1.00"))
        ],
        asks=asks if asks is not None else [
            PriceLevel(Decimal("695"), Decimal("1.00"))
        ],
        update_id=update_id,
        timestamp_ms=timestamp_ms,
    )


def test_valid_orderbook():
    result = validate_orderbook(
        make_book(),
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000
    )

    assert result.valid
    assert result.best_bid == Decimal("690")
    assert result.best_ask == Decimal("695")
    assert result.spread == Decimal("5")


def test_reject_negative_update_id():
    result = validate_orderbook(
        make_book(update_id=-1),
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000,
    )

    assert not result.valid
    assert any("update ID" in reason for reason in result.reasons)


def test_reject_empty_orderbook():
    result = validate_orderbook(
        make_book(bids=[], asks=[]),
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000,
    )

    assert not result.valid
    assert any("no bid" in reason for reason in result.reasons)
    assert any("no ask" in reason for reason in result.reasons)


def test_reject_stale_orderbook():
    result = validate_orderbook(
        make_book(timestamp_ms=1000),
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=10000,
        max_age_ms=5000,
    )

    assert not result.valid
    assert any("Stale" in reason for reason in result.reasons)


def test_reject_insufficient_quantity():
    result = validate_orderbook(
        make_book(),
        CONSTRAINTS,
        Decimal("2.00"),
        now_ms=11000,
    )

    assert not result.valid
    assert any(
        "Insufficient total bid-side quantity" in reason
        for reason in result.reasons
    )
    assert any(
        "Insufficient total ask-side quantity" in reason
        for reason in result.reasons
    )


def test_reject_crossed_book():
    result = validate_orderbook(
        make_book(
            bids=[PriceLevel(Decimal("700"), Decimal("1.00"))],
            asks=[PriceLevel(Decimal("695"), Decimal("1.00"))],
        ),
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000,
    )

    assert not result.valid
    assert any("Crossed" in reason for reason in result.reasons)


def test_vwap_single_level():
    levels = [
        PriceLevel(Decimal("690"), Decimal("1.00"))
    ]

    result = calculate_vwap(
        levels,
        Decimal("0.50"),
    )

    assert result == Decimal("690")


def test_vwap_multiple_levels():
    levels = [
        PriceLevel(Decimal("690"), Decimal("0.04")),
        PriceLevel(Decimal("685"), Decimal("0.06")),
    ]

    result = calculate_vwap(
        levels,
        Decimal("0.10"),
    )

    expected = (
        Decimal("690") * Decimal("0.04")
        + Decimal("685") * Decimal("0.06")
    ) / Decimal("0.10")

    assert result == expected


def test_vwap_rejects_insufficient_depth():
    levels = [
        PriceLevel(Decimal("690"), Decimal("0.04")),
        PriceLevel(Decimal("685"), Decimal("0.03")),
    ]

    result = calculate_vwap(
        levels,
        Decimal("0.10"),
    )

    assert result is None


def test_vwap_rejects_invalid_quantity():
    levels = [
        PriceLevel(Decimal("690"), Decimal("1.00"))
    ]

    try:
        calculate_vwap(levels, Decimal("0"))
        assert False, "Expected ValueError"
    except ValueError:
        pass



def test_validation_returns_entry_and_exit_vwap():
    book = make_book(
        bids=[
            PriceLevel(Decimal("690"), Decimal("0.04")),
            PriceLevel(Decimal("685"), Decimal("0.06")),
        ],
        asks=[
            PriceLevel(Decimal("695"), Decimal("0.04")),
            PriceLevel(Decimal("700"), Decimal("0.06")),
        ],
    )

    result = validate_orderbook(
        book,
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000,
    )

    assert result.valid
    assert result.entry_vwap == Decimal("687")
    assert result.exit_vwap == Decimal("698")


def test_vwap_fields_are_none_when_depth_is_insufficient():
    book = make_book(
        bids=[
            PriceLevel(Decimal("690"), Decimal("0.04")),
        ],
        asks=[
            PriceLevel(Decimal("695"), Decimal("0.04")),
        ],
    )

    result = validate_orderbook(
        book,
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000,
    )

    assert not result.valid
    assert result.entry_vwap is None
    assert result.exit_vwap is None


@pytest.mark.parametrize(
    "bad_value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_reject_non_finite_requested_quantity(bad_value):
    result = validate_orderbook(
        make_book(),
        CONSTRAINTS,
        bad_value,
        now_ms=11000,
    )

    assert not result.valid
    assert any(
        "requested quantity" in reason
        for reason in result.reasons
    )


@pytest.mark.parametrize(
    "field",
    [
        "min_quantity",
        "quantity_increment",
        "price_increment",
    ],
)
@pytest.mark.parametrize(
    "bad_value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_reject_non_finite_constraints(field, bad_value):
    constraints = InstrumentConstraints(
        min_quantity=(
            bad_value if field == "min_quantity"
            else CONSTRAINTS.min_quantity
        ),
        quantity_increment=(
            bad_value if field == "quantity_increment"
            else CONSTRAINTS.quantity_increment
        ),
        price_increment=(
            bad_value if field == "price_increment"
            else CONSTRAINTS.price_increment
        ),
    )

    result = validate_orderbook(
        make_book(),
        constraints,
        Decimal("0.10"),
        now_ms=11000,
    )

    assert not result.valid
    assert result.reasons


@pytest.mark.parametrize(
    "bad_value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
@pytest.mark.parametrize("side", ["bid", "ask"])
@pytest.mark.parametrize("field", ["price", "quantity"])
def test_reject_non_finite_orderbook_levels(bad_value, side, field):
    price = bad_value if field == "price" else Decimal("690")
    quantity = bad_value if field == "quantity" else Decimal("1.00")

    level = PriceLevel(price, quantity)

    book = (
        make_book(bids=[level])
        if side == "bid"
        else make_book(asks=[level])
    )

    result = validate_orderbook(
        book,
        CONSTRAINTS,
        Decimal("0.10"),
        now_ms=11000,
    )

    assert not result.valid
    assert result.reasons


@pytest.mark.parametrize(
    "bad_value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_vwap_rejects_non_finite_requested_quantity(bad_value):
    levels = [
        PriceLevel(Decimal("690"), Decimal("1.00"))
    ]

    with pytest.raises(ValueError):
        calculate_vwap(levels, bad_value)


@pytest.mark.parametrize(
    "bad_value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
@pytest.mark.parametrize("field", ["price", "quantity"])
def test_vwap_rejects_non_finite_levels(bad_value, field):
    price = bad_value if field == "price" else Decimal("690")
    quantity = bad_value if field == "quantity" else Decimal("1.00")

    levels = [PriceLevel(price, quantity)]

    with pytest.raises(ValueError):
        calculate_vwap(levels, Decimal("0.10"))
