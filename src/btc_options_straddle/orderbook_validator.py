
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class PriceLevel:
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    bids: Sequence[PriceLevel]
    asks: Sequence[PriceLevel]
    update_id: int
    timestamp_ms: int


@dataclass(frozen=True)
class InstrumentConstraints:
    min_quantity: Decimal
    quantity_increment: Decimal
    price_increment: Decimal


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    symbol: str
    reasons: tuple[str, ...]
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    bid_quantity: Decimal | None = None
    ask_quantity: Decimal | None = None
    spread: Decimal | None = None
    spread_pct: Decimal | None = None
    quote_age_ms: int | None = None
    requested_quantity: Decimal | None = None
    snapshot_timestamp_ms: int | None = None
    entry_vwap: Decimal | None = None
    exit_vwap: Decimal | None = None



def _is_multiple(value: Decimal, increment: Decimal) -> bool:
    return value % increment == 0

def _is_finite_decimal(value: Decimal) -> bool:
    return isinstance(value, Decimal) and value.is_finite()


def _available_quantity(levels: Sequence[PriceLevel]) -> Decimal:
    return sum(
        (level.quantity for level in levels),
        Decimal("0"),
    )


def validate_orderbook(
    snapshot: OrderBookSnapshot,
    constraints: InstrumentConstraints,
    requested_quantity: Decimal,
    now_ms: int,
    max_age_ms: int = 5000,
) -> ValidationResult:
    reasons = []
    decimal_fields = (
        ("requested quantity", requested_quantity),
        ("minimum quantity constraint", constraints.min_quantity),
        ("quantity increment", constraints.quantity_increment),
        ("price increment", constraints.price_increment),
    )

    for field_name, value in decimal_fields:
        if not _is_finite_decimal(value):
            reasons.append(f"Non-finite or invalid {field_name}")

    for side_name, levels in (
        ("bid", snapshot.bids),
        ("ask", snapshot.asks),
    ):
        for level in levels:
            if not _is_finite_decimal(level.price):
                reasons.append(f"Non-finite or invalid {side_name} price")

            if not _is_finite_decimal(level.quantity):
                reasons.append(f"Non-finite or invalid {side_name} quantity")

    if reasons:
        return ValidationResult(
            valid=False,
            symbol=snapshot.symbol,
            reasons=tuple(reasons),
            requested_quantity=requested_quantity,
            snapshot_timestamp_ms=snapshot.timestamp_ms,
        )

    if not snapshot.symbol:
        reasons.append("Missing instrument symbol")

    if snapshot.update_id <= 0:
        reasons.append("Invalid or negative order-book update ID")

    if not snapshot.bids:
        reasons.append("Order book has no bid levels")

    if not snapshot.asks:
        reasons.append("Order book has no ask levels")

    if requested_quantity <= 0:
        reasons.append("Requested quantity must be positive")

    if constraints.min_quantity <= 0:
        reasons.append("Invalid minimum quantity constraint")

    if constraints.quantity_increment <= 0:
        reasons.append("Invalid quantity increment")

    if constraints.price_increment <= 0:
        reasons.append("Invalid price increment")

    if max_age_ms < 0:
        reasons.append("Invalid maximum quote age")

    age_ms = now_ms - snapshot.timestamp_ms

    if snapshot.timestamp_ms <= 0:
        reasons.append("Invalid order-book timestamp")
    elif age_ms < 0:
        reasons.append("Order-book timestamp is in the future")
    elif age_ms > max_age_ms:
        reasons.append(f"Stale order book: {age_ms} ms old")

    if reasons:
        return ValidationResult(
            valid=False,
            symbol=snapshot.symbol,
            reasons=tuple(reasons),
            quote_age_ms=age_ms,
            requested_quantity=requested_quantity,
            snapshot_timestamp_ms=snapshot.timestamp_ms,
        )

    bids = list(snapshot.bids)
    asks = list(snapshot.asks)

    for side_name, levels in (("bid", bids), ("ask", asks)):
        for level in levels:
            if level.price <= 0:
                reasons.append(f"Invalid {side_name} price")

            if level.quantity <= 0:
                reasons.append(f"Invalid {side_name} quantity")

            if not _is_multiple(
                level.price,
                constraints.price_increment,
            ):
                reasons.append(
                    f"{side_name.capitalize()} price violates price increment"
                )

            if not _is_multiple(
                level.quantity,
                constraints.quantity_increment,
            ):
                reasons.append(
                    f"{side_name.capitalize()} quantity violates quantity increment"
                )

    if reasons:
        return ValidationResult(
            valid=False,
            symbol=snapshot.symbol,
            reasons=tuple(reasons),
            quote_age_ms=age_ms,
            requested_quantity=requested_quantity,
            snapshot_timestamp_ms=snapshot.timestamp_ms,
        )

    best_bid = bids[0]
    best_ask = asks[0]

    if any(
        bids[i].price < bids[i + 1].price
        for i in range(len(bids) - 1)
    ):
        reasons.append("Bid levels are not sorted descending")

    if any(
        asks[i].price > asks[i + 1].price
        for i in range(len(asks) - 1)
    ):
        reasons.append("Ask levels are not sorted ascending")

    if best_bid.price >= best_ask.price:
        reasons.append("Crossed or locked order book")

    if requested_quantity < constraints.min_quantity:
        reasons.append("Requested quantity is below minimum quantity")

    if not _is_multiple(
        requested_quantity,
        constraints.quantity_increment,
    ):
        reasons.append("Requested quantity violates quantity increment")

    bid_quantity = _available_quantity(bids)
    ask_quantity = _available_quantity(asks)

    if bid_quantity < requested_quantity:
        reasons.append("Insufficient total bid-side quantity")

    if ask_quantity < requested_quantity:
        reasons.append("Insufficient total ask-side quantity")

    entry_vwap = None
    exit_vwap = None

    if not reasons:
        entry_vwap = calculate_vwap(bids, requested_quantity)
        exit_vwap = calculate_vwap(asks, requested_quantity)

        if entry_vwap is None:
            reasons.append("Unable to calculate entry VWAP")

        if exit_vwap is None:
            reasons.append("Unable to calculate exit VWAP")

    spread = best_ask.price - best_bid.price










    spread_pct = (
        spread / best_ask.price * Decimal("100")
    )

    return ValidationResult(
        valid=not reasons,
        requested_quantity=requested_quantity,
        symbol=snapshot.symbol,
        reasons=tuple(reasons),
        best_bid=best_bid.price,
        best_ask=best_ask.price,
        bid_quantity=bid_quantity,
        ask_quantity=ask_quantity,
        spread=spread,
        spread_pct=spread_pct,
        quote_age_ms=age_ms,
        entry_vwap=entry_vwap,
        exit_vwap=exit_vwap,
        snapshot_timestamp_ms=snapshot.timestamp_ms,
    )


def calculate_vwap(
    levels: Sequence[PriceLevel],
    requested_quantity: Decimal,
) -> Decimal | None:
    """
    Estimate the average execution price across available book levels.

    Returns None when displayed depth cannot satisfy the requested quantity.
    """
    if not _is_finite_decimal(requested_quantity):
        raise ValueError("Requested quantity must be finite")

    if requested_quantity <= 0:
        raise ValueError("Requested quantity must be positive")

    remaining = requested_quantity
    total_value = Decimal("0")

    for level in levels:
        if (
            not _is_finite_decimal(level.price)
            or not _is_finite_decimal(level.quantity)
        ):
            raise ValueError("Order-book level values must be finite")

        if level.price <= 0 or level.quantity <= 0:
            raise ValueError("Invalid order-book level")

        filled_quantity = min(remaining, level.quantity)
        total_value += filled_quantity * level.price
        remaining -= filled_quantity

        if remaining == 0:
            return total_value / requested_quantity

    return None
