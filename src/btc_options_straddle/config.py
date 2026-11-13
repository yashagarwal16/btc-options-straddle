"""Bybit Testnet-only node configuration."""

from nautilus_trader.adapters.bybit import (
    BybitDataClientConfig,
    BybitEnvironment,
    BybitExecutionClientConfig,
    BybitProductType,
)

TRADER_ID = "STRADDLE-001"
NODE_NAME = "BTC-OPTIONS-TESTNET"
BYBIT_ENVIRONMENT = BybitEnvironment.TESTNET


def bybit_data_config() -> BybitDataClientConfig:
    return BybitDataClientConfig(
        product_types=[BybitProductType.OPTION],
        environment=BYBIT_ENVIRONMENT,
    )


def bybit_execution_config() -> BybitExecutionClientConfig:
    return BybitExecutionClientConfig(
        product_types=[BybitProductType.OPTION],
        environment=BYBIT_ENVIRONMENT,
    )
