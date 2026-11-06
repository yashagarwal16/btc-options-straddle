# BTC Options ATM Short Straddle — NautilusTrader

A Python-based BTC options short-straddle project built using **NautilusTrader 2.0.0rc8** and **Bybit Testnet**.

The project focuses on identifying an at-the-money (ATM) BTC options CALL/PUT pair, retrieving market data, validating order-book quality, and evaluating the combined short-straddle opportunity.

**Current implementation: Phase 3 — Strategy Validation and Market Data Integration**

---

## Project Overview

A short straddle involves selling a CALL option and a PUT option with the same underlying asset, strike price, and expiration date.

The objective is to collect premium from both option legs while managing the risks associated with changes in the underlying asset's price and option premiums.

This project establishes the market-data and validation foundation for a BTC ATM short-straddle strategy using Bybit Testnet.

### Strategy Concept

- Underlying asset: BTC
- Instruments: European-style BTC options
- Strategy: Short ATM straddle
- CALL leg: Sell CALL
- PUT leg: Sell PUT
- Strike: Same for both legs
- Expiry: Same for both legs
- Exchange environment: Bybit Testnet only

---

## Current Implementation

The project has progressed through the following development milestones.

### Phase 1 — Project Setup and Environment

- Configured the Python project using `uv`.
- Integrated NautilusTrader 2.0.0rc8.
- Established the Bybit Testnet-only environment.
- Organized the project into modular components.

### Phase 2 — Instrument Discovery and ATM Selection

- Retrieved BTC option instruments from Bybit.
- Identified available CALL and PUT contracts.
- Retrieved the BTC underlying reference price.
- Identified the nearest available expiry.
- Selected matching CALL and PUT contracts with the strike closest to the BTC reference price.
- Extracted instrument-specific quantity and price constraints.

### Phase 3 — Market Data and Strategy Validation

Implemented the following components:

**1. Testnet Market Data Adapter**
- Retrieves option order-book snapshots through Bybit's public Testnet REST API.
- Normalizes exchange responses into internal order-book structures.
- Handles malformed API responses and invalid numeric values.
- Preserves empty order books and invalid update IDs for downstream validation.

**2. Order-Book Validation**
- Validates bid and ask availability.
- Checks order-book update IDs.
- Validates quote timestamps and maximum quote age.
- Checks price and quantity increments.
- Detects invalid, locked and crossed order books.
- Checks displayed liquidity against requested quantity.
- Rejects non-finite Decimal values.

**3. VWAP Calculation**
- Estimates entry VWAP using bid-side liquidity.
- Estimates buyback VWAP using ask-side liquidity.
- Supports multiple order-book levels.
- Rejects insufficient displayed depth.

**4. Combined Straddle Validation**
- Validates CALL and PUT legs independently.
- Checks quantity consistency.
- Checks quote timestamp synchronization.
- Rejects the combined setup if either leg fails validation.
- Calculates combined entry credit and estimated buyback cost.

**5. Validation Reporting**
- Displays selected instruments and strike.
- Reports individual CALL and PUT validation results.
- Displays quote age, bid/ask prices and VWAP estimates.
- Reports combined straddle validation results and rejection reasons.

---

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.14+ |
| Trading framework | NautilusTrader 2.0.0rc8 |
| Exchange | Bybit |
| Exchange environment | Bybit Testnet |
| Dependency management | uv |
| Numeric calculations | Python Decimal |
| Market data | Bybit V5 REST API |
| Testing | pytest |
| Version control | Git and GitHub |

---

## Project Architecture

```text
btc-options-straddle/
│
├── src/
│   └── btc_options_straddle/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── instrument_selector.py
│       ├── market_data.py
│       ├── orderbook_validator.py
│       ├── straddle_validator.py
│       └── validation_pipeline.py
│
├── tests/
│   ├── test_market_data.py
│   ├── test_orderbook_validator.py
│   ├── test_straddle_validator.py
│   └── test_validation_pipeline.py
│
├── run_validation.py
├── PROJECT_PROGRESS.md
├── pyproject.toml
├── uv.lock
└── README.md
```

### Component Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Testnet environment and data-client configuration |
| `instrument_selector.py` | BTC ATM CALL/PUT instrument selection |
| `market_data.py` | Testnet order-book retrieval and normalization |
| `orderbook_validator.py` | Individual order-book validation and VWAP |
| `straddle_validator.py` | Combined CALL/PUT validation |
| `validation_pipeline.py` | End-to-end validation orchestration |
| `run_validation.py` | Validation workflow entry point |
| `main.py` | NautilusTrader read-only Testnet node setup |

---

## Installation and Setup

### Prerequisites

- Python 3.14 or later
- uv package manager
- Git

### 1. Clone the repository

```bash
git clone https://github.com/yashagarwal16/btc-options-straddle.git

cd btc-options-straddle
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Run the automated tests

```bash
uv run pytest -v
```

### 4. Run the validation workflow

```bash
uv run python run_validation.py
```

The validation workflow retrieves BTC option instruments, selects a matching ATM CALL/PUT pair and attempts to validate their Testnet order books.

**Note:** Actual validation results depend on the availability and quality of Bybit Testnet market data. Empty or insufficient order books may result in a rejected straddle.

---

## Testing and Validation

The project includes automated unit and integration tests.

**Current test results: 74 passed**

| Test module | Test cases |
|---|---:|
| Order-book validator | 45 |
| Market-data adapter | 15 |
| Straddle validator | 7 |
| Validation pipeline | 7 |
| **Total** | **74** |

Test coverage includes:

- Valid and invalid order books.
- Empty bid and ask sides.
- Invalid update IDs.
- Insufficient liquidity.
- Price and quantity increment validation.
- VWAP calculations across multiple levels.
- Stale and future timestamps.
- CALL/PUT quote timestamp skew.
- Malformed API responses.
- NaN and Infinity handling.
- Market-data error propagation.
- Combined straddle acceptance and rejection.

Tests use controlled inputs and mocked market-data responses where appropriate. They do not place exchange orders.

---

## Exchange Environment and Safety

**Exchange environment: Bybit Testnet ONLY**

The current implementation is focused on market-data retrieval and strategy validation.

- No live trading.
- No Mainnet execution.
- No Demo environment fallback.
- No order-submission workflow implemented.
- No automated position management implemented.
- No API trading credentials required for the public REST market-data validation workflow.

The NautilusTrader node configuration is intended for read-only Testnet market-data integration. The current validation runner uses the Testnet REST adapter.

---

## Known Limitations

Bybit Testnet option order books may have limited or inconsistent liquidity.

During development, the following conditions were observed:

- Empty order-book snapshots for selected options.
- Limited two-sided quotes.
- Insufficient displayed quantity.
- Inconsistent update IDs.
- Quote timestamp differences exceeding the configured threshold.

The validation pipeline intentionally rejects unsuitable market data instead of treating unavailable liquidity as executable.

The current implementation does not establish that a straddle is executable or profitable.

---

## Future Development Roadmap

The following capabilities are planned for subsequent development stages:

### Phase 4 — NautilusTrader Market Data Integration
- Integrate the Testnet streaming market-data client.
- Subscribe to selected CALL and PUT instruments.
- Inspect and normalize incoming market-data events.
- Validate order-book update consistency and freshness.

### Phase 5 — Strategy Execution
- Implement short-straddle order management.
- Handle CALL and PUT order submissions.
- Track order acknowledgements and fills.
- Handle partial fills and one-leg execution failures.

### Phase 6 — Risk Management and Position Monitoring
- Implement stop-loss and take-profit conditions.
- Monitor combined option premiums.
- Handle rejected and stale-quote scenarios.
- Prevent duplicate exit orders.
- Verify position closure.

These are roadmap items and are not represented as completed functionality.

---

## Repository

**GitHub:** https://github.com/yashagarwal16/btc-options-straddle

---

## Author

**Yash Agarwal**

B.Tech — Artificial Intelligence and Data Science

GitHub: https://github.com/yashagarwal16

LinkedIn: https://www.linkedin.com/in/yashagarwal-ai

---

*Developed as part of the Software Engineer Intern — Algorithmic Trading assignment at Mernplus Technologies LLP.*