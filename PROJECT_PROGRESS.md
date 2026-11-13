# BTC Options Straddle — Project Progress

**Assignment:** Mernplus Technologies LLP, Software Engineer Intern — Algorithmic Trading
**Framework:** NautilusTrader 2.0.0rc8 (pinned)
**Python:** 3.14.10
**Venue:** Bybit Testnet only

## Current implementation

- Registers Bybit Testnet option data and execution clients on one `LiveNode`.
- Loads BTC option instruments through the native adapter/cache.
- Selects the soonest expiry and subscribes to the native option chain to receive
  the ATM strike derived from Bybit's option reference price.
- Submits SELL market orders for the matching ATM call and put.
- Tracks fill events and computes entry premium from actual fill quantities and
  prices.
- Monitors both option ask quotes for the assignment's 1% stop and 2% target.
- Submits BUY market exits for cached short positions; avoids a second entry
  when a matching short pair is found after execution reconciliation.
- Cancels outstanding orders and attempts to flatten short positions on normal
  strategy shutdown. Any residual exposure must be checked after restart.
- Refuses to submit a new entry when reconciled BTC option orders remain open.
- Retries a rejected, canceled, or expired exit once, then reports unresolved
  exposure for operator review.

## Verification status

- Offline unit tests cover pair selection, premium thresholds, partial fill
  accumulation, rejected entry handling, and restart recovery.
- Current offline test result: 10 passed.
- No Bybit Testnet trading session has been run.
- Bybit order acceptance, fills, exit behavior, and venue reconciliation have
  not been integration-verified.
- Bybit Testnet account/API access returned error `10024` for regulatory
  restrictions. No attempt was made to bypass the restriction or use another
  environment.
- Strategy-side stop/target checks do not run while the process is offline.

## Safety

- Both Bybit clients explicitly use `BybitEnvironment.TESTNET` and options only.
- Credentials are loaded from the Testnet-specific environment variables.
- There is no Mainnet fallback or Mainnet endpoint in the strategy path.
- Running `uv run python -m btc_options_straddle.main` enables Testnet execution
  and can submit orders. It has not been run during this work.
- `pyproject.toml` and `uv.lock` were not changed.

## Architecture

```text
src/btc_options_straddle/
  config.py
  main.py
  strategy.py
tests/
  test_strategy.py
```

The framework supplies adapter connectivity, instrument and quote data,
instrument constraints, orders, positions, lifecycle events, and execution
reconciliation. Strategy code contains the ATM pair choice, entry policy,
combined-premium calculation, and stop/target decisions.
