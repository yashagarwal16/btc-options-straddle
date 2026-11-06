
import time
from dataclasses import dataclass
from decimal import Decimal

from btc_options_straddle.instrument_selector import StraddleSelection
from btc_options_straddle.market_data import fetch_testnet_orderbook
from btc_options_straddle.orderbook_validator import (
    ValidationResult,
    validate_orderbook,
)
from btc_options_straddle.straddle_validator import (
    StraddleValidationResult,
    validate_straddle,
)


@dataclass(frozen=True)
class PipelineResult:
    call_result: ValidationResult
    put_result: ValidationResult
    straddle_result: StraddleValidationResult


def validate_selected_straddle(
    selection: StraddleSelection,
    requested_quantity: Decimal,
    now_ms: int | None = None,
    max_age_ms: int = 5000,
    max_quote_skew_ms: int = 1000,
) -> PipelineResult:

    # Fetch both Testnet snapshots.
    call_snapshot = fetch_testnet_orderbook(
        selection.call_symbol,
        limit=25,
    )

    put_snapshot = fetch_testnet_orderbook(
        selection.put_symbol,
        limit=25,
    )

    # Capture time after both snapshots arrive.
    if now_ms is None:
        now_ms = time.time_ns() // 1_000_000

    # Validate each leg independently.
    call_result = validate_orderbook(
        snapshot=call_snapshot,
        constraints=selection.call_constraints,
        requested_quantity=requested_quantity,
        now_ms=now_ms,
        max_age_ms=max_age_ms,
    )

    put_result = validate_orderbook(
        snapshot=put_snapshot,
        constraints=selection.put_constraints,
        requested_quantity=requested_quantity,
        now_ms=now_ms,
        max_age_ms=max_age_ms,
    )

    # Validate the combined straddle.
    straddle_result = validate_straddle(
        call=call_result,
        put=put_result,
        max_quote_skew_ms=max_quote_skew_ms,
    )

    return PipelineResult(
        call_result=call_result,
        put_result=put_result,
        straddle_result=straddle_result,
    )


def print_validation_report(
    selection: StraddleSelection,
    requested_quantity: Decimal,
    result: PipelineResult,
) -> None:

    print("\n========== TESTNET VALIDATION PIPELINE ==========")
    print("Environment: BYBIT TESTNET")
    print("Execution: DISABLED")
    print("Strike:", selection.strike)
    print("Expiry:", selection.expiry)
    print("Requested quantity:", requested_quantity)

    for label, leg in (
        ("CALL", result.call_result),
        ("PUT", result.put_result),
    ):
        print(f"\n========== {label} VALIDATION ==========")
        print("Symbol:", leg.symbol)
        print("Valid:", leg.valid)
        print("Quote age (ms):", leg.quote_age_ms)
        print("Best bid:", leg.best_bid)
        print("Best ask:", leg.best_ask)
        print("Entry VWAP:", leg.entry_vwap)
        print("Exit VWAP:", leg.exit_vwap)

        if leg.reasons:
            print("Rejection reasons:")
            for reason in leg.reasons:
                print("-", reason)

    straddle = result.straddle_result

    print("\n========== STRADDLE VALIDATION ==========")
    print("Valid:", straddle.valid)
    print("Quote skew (ms):", straddle.quote_skew_ms)
    print("Entry credit per unit:", straddle.entry_credit_per_unit)
    print("Buyback cost per unit:", straddle.buyback_cost_per_unit)

    if straddle.reasons:
        print("Rejection reasons:")
        for reason in straddle.reasons:
            print("-", reason)

    print("\nExecution: DISABLED")
