# BTC Options Straddle — Project Progress

**Organization:** Mernplus Technologies LLP
**Assignment:** Software Engineer Intern — Algorithmic Trading
**Strategy:** BTC ATM Short Straddle
**Exchange:** Bybit Testnet ONLY
**Framework:** NautilusTrader 2.0.0rc8
**Python:** 3.14.10

---

## 1. Project Objective

Build and test a BTC ATM Short Straddle using NautilusTrader
and Bybit Testnet.

The strategy must discover BTC option contracts, select matching
ATM call and put contracts, execute both short positions, monitor
combined premium, and manage exits.

## 2. Assignment Requirements

### Level 1
- [ ] Bybit Testnet integration
- [ ] Subscribe to BTC options market data
- [ ] Discover available BTC option contracts
- [ ] Retrieve BTC underlying reference price
- [ ] Select nearest ATM strike
- [ ] Match call and put by strike and expiry
- [ ] Submit SELL orders for both legs
- [ ] Track order acknowledgements and executions
- [ ] Track open positions
- [ ] Handle one-leg execution failures

### Level 2
- [ ] 1% stop-loss
- [ ] 2% take-profit
- [ ] Combined buyback premium using ask-side quotes
- [ ] Consistent quantity handling
- [ ] Partial-fill handling
- [ ] Duplicate exit prevention
- [ ] Rejected-order handling
- [ ] Missing/stale quote handling
- [ ] Verify both positions are closed

## 3. Environment

- OS: Windows 11 + WSL2 Ubuntu
- Python: 3.14.10
- NautilusTrader: 2.0.0rc8
- uv: 0.13.7
- Git: 2.53.0

Project directory:
`/home/yash/projects/btc-options-straddle`

Virtual environment:
`.venv`

## 4. Completed Milestones

### Milestone 0 — Environment and Repository
- [x] WSL2 configured
- [x] VS Code connected to WSL
- [x] Python installed
- [x] Virtual environment created
- [x] NautilusTrader installed and import verified
- [x] Git initialized
- [x] GitHub repository created
- [x] Initial README committed
- [x] Dependencies declared
- [x] Git working tree verified clean

### Milestone 1 — Adapter Inspection
- [x] Bybit adapter import verified
- [x] BybitDataClientConfig identified
- [x] BybitExecutionClientConfig identified
- [x] BybitDataClientFactory identified
- [x] BybitExecutionClientFactory identified
- [x] BybitEnvironment.TESTNET identified
- [x] BybitProductType.OPTION identified
- [x] Correct LiveNode import verified

## 5. Current Implementation Status

**Current milestone:** Bybit Testnet market-data integration

- [ ] LiveNode configuration
- [ ] Bybit data client registration
- [ ] Testnet connection
- [ ] BTC options instrument discovery
- [ ] Underlying reference price retrieval
- [ ] ATM contract selection

No trading functionality has been implemented or verified yet.

## 6. Safety Requirements

- Bybit Testnet only.
- Never submit live trading orders.
- No API credentials committed to Git.
- Keep execution disabled during market-data development.
- Validate all order quantities and prices.
- Prevent duplicate exit orders.
- Verify both option positions are closed.

## 7. Engineering Decisions and Debugging Log

### 2026-11-06
- Confirmed NautilusTrader 2.0.0rc8.
- Confirmed Bybit options product support.
- Confirmed TESTNET and OPTION enum members.
- Correct LiveNode import:
  `from nautilus_trader.live import LiveNode`
- Incorrect import discovered:
  `from nautilus_trader.live.node import LiveNode`
- Confirmed configuration classes are extension-backed.

## 8. GitHub

Repository:
https://github.com/yashagarwal16/btc-options-straddle

## 9. Final Documentation Checklist

- [ ] README with installation and usage
- [ ] PROJECT_PROGRESS.md
- [ ] PROJECT_HANDOVER.md
- [ ] Architecture documentation
- [ ] Configuration and environment documentation
- [ ] Strategy explanation
- [ ] Risk management explanation
- [ ] Test results
- [ ] Known limitations
- [ ] Interview preparation notes
