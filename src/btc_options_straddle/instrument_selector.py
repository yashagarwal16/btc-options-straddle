
import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime, timezone

from nautilus_trader.adapters.bybit import (
    BybitHttpClient,
    BybitProductType,
    BybitTickersParams,
)


@dataclass(frozen=True)
class StraddleSelection:
    underlying_price: float
    expiry: datetime
    strike: float
    call_symbol: str
    put_symbol: str


async def resolve(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def select_atm_straddle():
    client = BybitHttpClient(
        testnet=True,
        timeout_secs=30,
        max_retries=2,
    )

    # Retrieve BTC option instruments.
    instruments = await resolve(
        client.request_instruments(
            product_type=BybitProductType.OPTION,
            base_coin="BTC",
        )
    )

    # Retrieve BTC option tickers.
    tickers = await resolve(
        client.request_tickers(
            BybitTickersParams(
                category=BybitProductType.OPTION,
                base_coin="BTC",
            )
        )
    )

    if not instruments or not tickers:
        raise RuntimeError("No BTC option instruments or tickers found.")

    # Obtain BTC index price.
    index_prices = [
        float(ticker.index_price)
        for ticker in tickers
        if float(ticker.index_price or 0) > 0
    ]

    if not index_prices:
        raise RuntimeError("BTC index price unavailable.")

    underlying_price = index_prices[0]

    now_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

    # Group active instruments by expiry and strike.
    contracts = {}

    for instrument in instruments:
        if instrument.expiration_ns <= now_ns:
            continue

        expiry = instrument.expiration_ns
        strike = float(instrument.strike_price)

        option_kind = str(instrument.option_kind).upper()

        if option_kind not in ("CALL", "PUT"):
            continue

        contracts.setdefault(expiry, {}).setdefault(
            strike, {}
        )[option_kind] = instrument

    # Find nearest expiry with matching call and put.
    valid_expiries = []

    for expiry, strikes in contracts.items():
        matching = [
            strike
            for strike, legs in strikes.items()
            if "CALL" in legs and "PUT" in legs
        ]

        if matching:
            valid_expiries.append(expiry)

    if not valid_expiries:
        raise RuntimeError("No matching call/put contracts found.")

    nearest_expiry = min(valid_expiries)

    # Find strike nearest to BTC index price.
    matching_strikes = [
        strike
        for strike, legs in contracts[nearest_expiry].items()
        if "CALL" in legs and "PUT" in legs
    ]

    selected_strike = min(
        matching_strikes,
        key=lambda strike: abs(strike - underlying_price),
    )

    legs = contracts[nearest_expiry][selected_strike]

    return StraddleSelection(
        underlying_price=underlying_price,
        expiry=datetime.fromtimestamp(
            nearest_expiry / 1_000_000_000,
            tz=timezone.utc,
        ),
        strike=selected_strike,
        call_symbol=str(legs["CALL"].raw_symbol),
        put_symbol=str(legs["PUT"].raw_symbol),
    )


async def main():
    selection = await select_atm_straddle()

    print("\n========== ATM STRADDLE SELECTION ==========")
    print("Environment: BYBIT TESTNET")
    print("Underlying BTC:", selection.underlying_price)
    print("Expiry:", selection.expiry)
    print("Strike:", selection.strike)
    print("CALL:", selection.call_symbol)
    print("PUT:", selection.put_symbol)
    print("Execution: DISABLED")


if __name__ == "__main__":
    asyncio.run(main())
