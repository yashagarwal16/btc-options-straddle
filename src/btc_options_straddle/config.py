
from nautilus_trader.adapters.bybit import (
    BybitDataClientConfig,
    BybitEnvironment,
    BybitProductType,
)

TRADER_ID = "STRADDLE-001"
NODE_NAME = "BTC-OPTIONS-TESTNET"

BYBIT_ENVIRONMENT = BybitEnvironment.TESTNET

BYBIT_PRODUCT_TYPES = [
    BybitProductType.OPTION,
]


def get_bybit_data_config() -> BybitDataClientConfig:
    if BYBIT_ENVIRONMENT != BybitEnvironment.TESTNET:
        raise RuntimeError("Only Bybit Testnet is permitted.")

    return BybitDataClientConfig(
        product_types=BYBIT_PRODUCT_TYPES,
        environment=BYBIT_ENVIRONMENT,
    )
