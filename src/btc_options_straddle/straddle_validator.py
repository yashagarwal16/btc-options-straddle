
from dataclasses import dataclass
from decimal import Decimal

from btc_options_straddle.orderbook_validator import ValidationResult


@dataclass(frozen=True)
class StraddleValidationResult:
    valid: bool
    reasons: tuple[str, ...]
    quantity: Decimal | None = None
    entry_credit_per_unit: Decimal | None = None
    buyback_cost_per_unit: Decimal | None = None
    entry_credit_total: Decimal | None = None
    buyback_cost_total: Decimal | None = None
    quote_skew_ms: int | None = None


def validate_straddle(
    call: ValidationResult,
    put: ValidationResult,
    max_quote_skew_ms: int = 1000,
) -> StraddleValidationResult:

    reasons = []

    if not call.valid:
        reasons.append("CALL order book validation failed")

    if not put.valid:
        reasons.append("PUT order book validation failed")

    call_quantity = call.requested_quantity
    put_quantity = put.requested_quantity

    if call_quantity is None or put_quantity is None:
        reasons.append("Validated quantity is unavailable")

    elif call_quantity <= 0 or put_quantity <= 0:
        reasons.append("Straddle quantities must be positive")

    elif call_quantity != put_quantity:
        reasons.append("CALL and PUT quantities must match")

    if call.entry_vwap is None or call.exit_vwap is None:
        reasons.append("CALL VWAP estimates are unavailable")

    if put.entry_vwap is None or put.exit_vwap is None:
        reasons.append("PUT VWAP estimates are unavailable")

    quote_skew_ms = None

    if max_quote_skew_ms < 0:
        reasons.append("Invalid maximum quote timestamp difference")

    call_timestamp = call.snapshot_timestamp_ms
    put_timestamp = put.snapshot_timestamp_ms

    if call_timestamp is None or put_timestamp is None:
        reasons.append("CALL or PUT snapshot timestamp is unavailable")
    elif call_timestamp <= 0 or put_timestamp <= 0:
        reasons.append("Invalid CALL or PUT snapshot timestamp")
    else:
        quote_skew_ms = abs(call_timestamp - put_timestamp)

        if quote_skew_ms > max_quote_skew_ms:
            reasons.append(
                f"CALL/PUT quote timestamp difference too large: "
                f"{quote_skew_ms} ms"
            )

    if reasons:
        return StraddleValidationResult(
            valid=False,
            reasons=tuple(reasons),
            quote_skew_ms=quote_skew_ms,
        )

    quantity = call_quantity

    entry_credit_per_unit = call.entry_vwap + put.entry_vwap
    buyback_cost_per_unit = call.exit_vwap + put.exit_vwap

    return StraddleValidationResult(
        valid=True,
        reasons=(),
        quantity=quantity,
        entry_credit_per_unit=entry_credit_per_unit,
        buyback_cost_per_unit=buyback_cost_per_unit,
        entry_credit_total=entry_credit_per_unit * quantity,
        buyback_cost_total=buyback_cost_per_unit * quantity,
        quote_skew_ms=quote_skew_ms,
    )


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
    assert "CALL or PUT snapshot timestamp is unavailable" in result.reasons
