
from nautilus_trader.common import Environment
from nautilus_trader.live import LiveNode
from nautilus_trader.model import TraderId

from nautilus_trader.adapters.bybit import (
    BybitDataClientFactory,
    BybitEnvironment,
)

from btc_options_straddle.config import (
    NODE_NAME,
    TRADER_ID,
    BYBIT_ENVIRONMENT,
    get_bybit_data_config,
)


def build_node() -> LiveNode:
    """Build a read-only Bybit Testnet market-data node."""

    # Enforce Testnet before constructing the client.
    if BYBIT_ENVIRONMENT != BybitEnvironment.TESTNET:
        raise RuntimeError(
            "SAFETY ERROR: Only Bybit TESTNET is permitted."
        )

    config = get_bybit_data_config()

    node = (
        LiveNode.builder(
            NODE_NAME,
            TraderId.from_str(TRADER_ID),
            Environment.LIVE,
        )
        .add_data_client(
            None,
            BybitDataClientFactory(),
            config,
        )
        .build()
    )

    return node


def main() -> None:
    print("=" * 55)
    print("BTC OPTIONS STRADDLE")
    print("BYBIT TESTNET MARKET DATA")
    print("=" * 55)

    print("[SAFETY] Environment: TESTNET")
    print("[SAFETY] Product: OPTION")
    print("[SAFETY] Execution client: DISABLED")
    print("[SAFETY] Order submission: DISABLED")

    node = build_node()

    print("\nStarting NautilusTrader node...")

    node.run()


if __name__ == "__main__":
    main()
