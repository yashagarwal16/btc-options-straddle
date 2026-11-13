# BTC ATM Short Straddle

A small NautilusTrader strategy for Bybit Testnet. It discovers BTC option
instruments through the Bybit data client, uses NautilusTrader's option-chain
subscription to identify the ATM strike, submits SELL market orders for the
matching call and put, and monitors the combined ask premium for the assignment's
1% stop and 2% target.

## Safety

The data and execution clients are configured with `BybitEnvironment.TESTNET`.
Credentials are read by the adapter from `BYBIT_TESTNET_API_KEY` and
`BYBIT_TESTNET_API_SECRET`; the program has no Mainnet fallback. Do not set
Mainnet credentials for this program.

**Running `uv run python -m btc_options_straddle.main` enables Testnet execution
and can submit orders to Bybit Testnet.** It has not been run as part of this
refactor. No Testnet execution has been verified.

Stops and targets are strategy-side triggers based on streaming option ask
quotes. They are not exchange-hosted protective orders and do not operate while
the process or market-data connection is down. On shutdown, the strategy asks
NautilusTrader to cancel its orders and submits best-effort market exits for
short positions. An exit may not fill before shutdown; the next startup uses
framework reconciliation and refuses a new entry if it finds an unmatched
position. A matched short call/put pair is recovered from the reconciled cache
and monitored again.

Entry failure cancels strategy orders and attempts to close any filled short
legs. If an exit is rejected or canceled, the strategy logs unresolved
exposure, retries once, then requires operator review if it still fails.
Reconciled open BTC option orders also stop startup to prevent duplicate entry.

## Environment

- Python 3.14+
- NautilusTrader 2.0.0rc8 (pinned)
- Bybit Testnet, options product
- `uv`

Install dependencies with `uv sync`. Offline unit tests can be run with
`uv run pytest` (10 tests). The tests do not connect to Bybit or submit orders.

## Structure

```text
src/btc_options_straddle/
  config.py    # fixed Testnet-only Bybit client configs
  main.py      # LiveNode and Bybit client registration
  strategy.py  # pair selection, entry, fills, exits, and recovery
tests/
  test_strategy.py
```

The strategy uses NautilusTrader's instrument cache, option-chain and quote
subscriptions, order factory, order/position cache, lifecycle callbacks, and
execution reconciliation. ATM pairing and combined-premium risk rules remain
strategy-specific.

## Current verification limits

Offline tests cover pair selection, premium thresholds, equal partial-fill
accounting, entry rejection handling, and restart recovery. They do not prove
Bybit Testnet order acceptance, fills, exit behavior, or position
reconciliation. No live or Testnet trading session has been run. Bybit Testnet
access displayed error `10024` with a regulatory restriction during account/API
access, so the execution path could not be integration-tested. This restriction
has not been bypassed.
