from decimal import Decimal

import pytest
from nautilus_trader.model import (
    CryptoOption,
    Currency,
    InstrumentId,
    OptionKind,
    OrderSide,
    PositionSide,
    Price,
    Quantity,
    Symbol,
)

from btc_options_straddle.strategy import (
    BtcShortStraddle,
    combined_entry_premium,
    exit_reason,
    select_pair,
)


def option(kind: OptionKind, expiry: int = 2_000_000_000_000_000_000):
    suffix = "C" if kind == OptionKind.CALL else "P"
    symbol = f"BTC-25DEC26-100000-{suffix}-USDT-OPTION"
    return CryptoOption(
        instrument_id=InstrumentId.from_str(f"{symbol}.BYBIT"),
        raw_symbol=Symbol(symbol),
        underlying=Currency.from_str("BTC"),
        quote_currency=Currency.from_str("USDT"),
        settlement_currency=Currency.from_str("USDT"),
        is_inverse=False,
        option_kind=kind,
        strike_price=Price.from_str("100000"),
        activation_ns=1,
        expiration_ns=expiry,
        price_precision=2,
        size_precision=2,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_str("0.01"),
        ts_event=1,
        ts_init=1,
        multiplier=Quantity.from_str("1"),
        lot_size=Quantity.from_str("0.01"),
        min_quantity=Quantity.from_str("0.01"),
    )


def test_select_pair_requires_same_expiry_strike_and_settlement():
    call = option(OptionKind.CALL)
    put = option(OptionKind.PUT)

    assert select_pair([call, put], now_ns=1) == (call, put)
    assert select_pair([call], now_ns=1) is None
    assert select_pair([call, put], now_ns=call.expiration_ns) is None


def test_select_pair_rejects_different_strikes():
    call = option(OptionKind.CALL)
    other_put = CryptoOption(
        instrument_id=InstrumentId.from_str("BTC-25DEC26-101000-P-USDT-OPTION.BYBIT"),
        raw_symbol=Symbol("BTC-25DEC26-101000-P-USDT-OPTION"),
        underlying=Currency.from_str("BTC"),
        quote_currency=Currency.from_str("USDT"),
        settlement_currency=Currency.from_str("USDT"),
        is_inverse=False,
        option_kind=OptionKind.PUT,
        strike_price=Price.from_str("101000"),
        activation_ns=1,
        expiration_ns=call.expiration_ns,
        price_precision=2,
        size_precision=2,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_str("0.01"),
        ts_event=1,
        ts_init=1,
        multiplier=Quantity.from_str("1"),
    )
    assert select_pair([call, other_put], now_ns=1) is None


@pytest.mark.parametrize(
    ("entry", "buyback", "expected"),
    [
        (Decimal("100"), Decimal("101"), "stop_loss"),
        (Decimal("100"), Decimal("98"), "take_profit"),
        (Decimal("100"), Decimal("100.50"), None),
    ],
)
def test_combined_premium_exit_thresholds(entry, buyback, expected):
    assert exit_reason(entry, buyback) == expected


def test_partial_entry_premium_requires_equal_filled_quantities():
    assert combined_entry_premium(
        Decimal("0.005"), Decimal("0.50"), Decimal("0.01"), Decimal("2")
    ) is None
    assert combined_entry_premium(
        Decimal("0.01"), Decimal("1.01"), Decimal("0.01"), Decimal("2.02")
    ) == Decimal("303")


def test_partial_fills_accumulate_actual_entry_premium():
    class Cache:
        closed = {"CALL-ORDER": False, "PUT-ORDER": False}

        def order(self, order_id):
            return type("CachedOrder", (), {"is_closed": self.closed[order_id]})()

    class TestStrategy(BtcShortStraddle):
        @property
        def cache(self):
            return cache

    cache = Cache()
    strategy = TestStrategy()
    strategy.call_id = "CALL"
    strategy.put_id = "PUT"
    strategy.entry_orders = {"CALL-ORDER", "PUT-ORDER"}

    class Fill:
        client_order_id = "CALL-ORDER"
        instrument_id = "CALL"
        last_qty = Quantity.from_str("0.005")
        last_px = Price.from_str("100")
        order_side = OrderSide.SELL

    strategy.on_order_filled(Fill())
    Fill.client_order_id = "PUT-ORDER"
    Fill.instrument_id = "PUT"
    Fill.last_px = Price.from_str("200")
    strategy.on_order_filled(Fill())
    Fill.client_order_id = "CALL-ORDER"
    Fill.instrument_id = "CALL"
    Fill.last_px = Price.from_str("102")
    strategy.on_order_filled(Fill())
    Fill.client_order_id = "PUT-ORDER"
    Fill.instrument_id = "PUT"
    Fill.last_px = Price.from_str("202")
    cache.closed = {"CALL-ORDER": True, "PUT-ORDER": True}
    strategy.on_order_filled(Fill())

    assert strategy.entry_fills == {"CALL": Decimal("0.010"), "PUT": Decimal("0.010")}
    assert strategy.entry_premium == Decimal("302")


def test_rejected_entry_starts_one_exit_attempt(monkeypatch):
    strategy = BtcShortStraddle()
    strategy.entry_orders = {"CALL-ORDER"}
    exits = []
    monkeypatch.setattr(strategy, "_submit_exits", lambda: exits.append(True))

    class Rejection:
        client_order_id = "CALL-ORDER"
        instrument_id = "CALL"

    strategy.call_id = "CALL"
    strategy.put_id = "PUT"
    strategy.on_order_rejected(Rejection())

    assert exits == [True]


def test_rejected_exit_is_retried_once_then_reported(monkeypatch):
    strategy = BtcShortStraddle()
    attempts = []
    monkeypatch.setattr(strategy, "_submit_exits", lambda: attempts.append(True))
    strategy.exit_orders["EXIT-1"] = "CALL"

    strategy._retry_or_report_exit("EXIT-1", "rejected")
    assert attempts == [True]
    assert strategy.exit_retries == {"CALL": 1}

    strategy.exit_orders["EXIT-2"] = "CALL"
    strategy._retry_or_report_exit("EXIT-2", "rejected")
    assert attempts == [True]
    assert "EXIT-2" not in strategy.exit_orders


def test_restart_recovers_existing_matched_short_pair(monkeypatch):
    strategy = BtcShortStraddle()
    call = option(OptionKind.CALL)
    put = option(OptionKind.PUT)
    strategy._instruments = {call.id: call, put.id: put}
    subscriptions = []
    monkeypatch.setattr(strategy, "subscribe_quotes", lambda instrument_id: subscriptions.append(instrument_id))

    class Position:
        side = PositionSide.SHORT
        quantity = Quantity.from_str("0.01")
        avg_px_open = Price.from_str("100")

        def __init__(self, instrument_id, price):
            self.instrument_id = instrument_id
            self.avg_px_open = Price.from_str(price)

    assert strategy._recover_pair([Position(call.id, "100"), Position(put.id, "200")])
    assert strategy.call_id == call.id
    assert strategy.put_id == put.id
    assert strategy.entry_premium == Decimal("300")
    assert strategy.entered
    assert subscriptions == [call.id, put.id]
