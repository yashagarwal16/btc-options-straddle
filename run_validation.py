import asyncio
from decimal import Decimal

from btc_options_straddle.instrument_selector import (
    select_atm_straddle,
)
from btc_options_straddle.validation_pipeline import (
    validate_selected_straddle,
    print_validation_report,
)


async def main():
    print("========== BTC SHORT STRADDLE VALIDATION ==========")
    print("Environment: BYBIT TESTNET")
    print("Execution: DISABLED")

    selection = await select_atm_straddle()

    quantity = Decimal("0.01")

    print("\nSelected instruments:")
    print("CALL:", selection.call_symbol)
    print("PUT:", selection.put_symbol)

    result = validate_selected_straddle(
        selection=selection,
        requested_quantity=quantity,
    )

    print_validation_report(
        selection=selection,
        requested_quantity=quantity,
        result=result,
    )


if __name__ == "__main__":
    asyncio.run(main())