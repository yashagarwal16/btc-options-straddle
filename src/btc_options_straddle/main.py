"""Build and run the Bybit Testnet BTC straddle node."""

from nautilus_trader.common import Environment
from nautilus_trader.live import LiveNode
from nautilus_trader.model import TraderId
from nautilus_trader.adapters.bybit import (
    BybitDataClientFactory,
    BybitEnvironment,
    BybitExecutionClientFactory,
)

from btc_options_straddle.config import (
    NODE_NAME,
    TRADER_ID,
    bybit_data_config,
    bybit_execution_config,
)
from btc_options_straddle.strategy import BtcShortStraddle


def build_node() -> LiveNode:
    """Build a Testnet-only node with Bybit data and execution clients."""
    if bybit_data_config().environment != BybitEnvironment.TESTNET:
        raise RuntimeError("Only Bybit Testnet is permitted")
    if bybit_execution_config().environment != BybitEnvironment.TESTNET:
        raise RuntimeError("Only Bybit Testnet execution is permitted")

    node = (
        LiveNode.builder(
            NODE_NAME,
            TraderId.from_str(TRADER_ID),
            Environment.LIVE,
        )
        .add_data_client(None, BybitDataClientFactory(), bybit_data_config())
        .add_exec_client(None, BybitExecutionClientFactory(), bybit_execution_config())
        .build()
    )
    node.add_strategy(BtcShortStraddle())
    return node


def main() -> None:
    print("Bybit Testnet BTC short straddle")
    print("Execution is enabled. This program can submit Testnet orders.")
    node = build_node()
    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main()
