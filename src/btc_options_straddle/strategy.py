"""Minimal Bybit BTC short-straddle strategy.

Entries and exits are ordinary market orders. Stop and target conditions are
evaluated locally from the two option ask quotes, so they only operate while
the node and its market-data connection are running.
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.adapters.bybit import BYBIT
from nautilus_trader.adapters.bybit import BybitEnvironment
from nautilus_trader.model import (
    CryptoOption,
    OptionChainSlice,
    OptionSeriesId,
    OrderSide,
    PositionSide,
    StrikeRange,
    TimeInForce,
)
from nautilus_trader.trading import Strategy

from btc_options_straddle.config import BYBIT_ENVIRONMENT

ENTRY_QUANTITY = Decimal("0.01")
STOP_LOSS = Decimal("0.01")
TAKE_PROFIT = Decimal("0.02")
MAX_QUOTE_AGE_NS = 5_000_000_000
MAX_QUOTE_SKEW_NS = 1_000_000_000


def select_pair(instruments, now_ns: int):
    """Return the soonest-expiring BTC call/put pair at a shared strike."""
    options = [
        instrument
        for instrument in instruments
        if isinstance(instrument, CryptoOption)
        and str(instrument.id.venue) == BYBIT
        and str(instrument.underlying).upper() == "BTC"
        and instrument.expiration_ns > now_ns
    ]
    if not options:
        return None

    # Prefer USDT settlement where both settlements are listed.
    expiries = sorted({instrument.expiration_ns for instrument in options})
    for expiry_ns in expiries:
        expiry_options = [i for i in options if i.expiration_ns == expiry_ns]
        settlements = sorted({str(i.settlement_currency) for i in expiry_options})
        if "USDT" in settlements:
            settlements.remove("USDT")
            settlements.insert(0, "USDT")
        for settlement in settlements:
            legs = {}
            for instrument in expiry_options:
                if str(instrument.settlement_currency) != settlement:
                    continue
                key = (str(instrument.strike_price), str(instrument.option_kind).upper())
                legs[key] = instrument
            strikes = sorted({key[0] for key in legs}, key=Decimal)
            for strike in strikes:
                call = legs.get((strike, "CALL"))
                put = legs.get((strike, "PUT"))
                if call is not None and put is not None:
                    return call, put
    return None


def exit_reason(entry_premium: Decimal, buyback_premium: Decimal) -> str | None:
    """Return the first triggered exit based on the combined premiums."""
    if entry_premium <= 0 or buyback_premium < 0:
        return None
    change = (buyback_premium - entry_premium) / entry_premium
    if change >= STOP_LOSS:
        return "stop_loss"
    if change <= -TAKE_PROFIT:
        return "take_profit"
    return None


def combined_entry_premium(
    call_quantity: Decimal,
    call_notional: Decimal,
    put_quantity: Decimal,
    put_notional: Decimal,
) -> Decimal | None:
    """Return per-unit combined credit only for equal, positive fills."""
    if call_quantity <= 0 or call_quantity != put_quantity:
        return None
    return call_notional / call_quantity + put_notional / put_quantity


class BtcShortStraddle(Strategy):
    """Select one BTC ATM pair, enter it once, and monitor its combined ask."""

    def __init__(self, quantity: str = str(ENTRY_QUANTITY)) -> None:
        super().__init__()
        if BYBIT_ENVIRONMENT != BybitEnvironment.TESTNET:
            raise RuntimeError("Only Bybit Testnet is permitted")
        self.quantity = Decimal(quantity)
        self.series_id: OptionSeriesId | None = None
        self.call_id = None
        self.put_id = None
        self.call_quote = None
        self.put_quote = None
        self.entry_orders: set = set()
        self.active_entry_orders: set = set()
        self.exit_orders: dict = {}
        self.exit_retries: dict = {}
        self.entry_fills: dict = {}
        self.entry_notional: dict = {}
        self.entry_premium: Decimal | None = None
        self.entered = False
        self.exiting = False

    def on_start(self) -> None:
        self._instruments = {
            instrument.id: instrument
            for instrument in self.cache.instruments()
            if isinstance(instrument, CryptoOption)
            and str(instrument.id.venue) == BYBIT
            and str(instrument.underlying).upper() == "BTC"
        }

        open_orders = [
            order
            for order in self.cache.orders_open()
            if order.instrument_id in self._instruments
        ]
        if open_orders:
            self.log.error("Reconciled BTC option orders found; refusing duplicate entry")
            self.stop()
            return

        # The execution engine reconciles venue state before strategy startup.
        # Resume a matching short pair from reconciled positions instead of
        # submitting duplicate entry orders after a restart.
        open_positions = [
            position
            for position in self.cache.positions_open()
            if position.instrument_id in self._instruments
        ]
        if open_positions:
            if self._recover_pair(open_positions):
                return
            self.log.error("Unmatched reconciled BTC option positions; refusing new entry")
            self.stop()
            return
        options = [
            self._instruments[instrument_id]
            for instrument_id in self._instruments
        ]
        pair = select_pair(options, self.clock.timestamp_ns())
        if pair is None:
            self.log.error("No unexpired matching BTC call/put pair in cache")
            self.stop()
            return

        call, put = pair
        self.call_id, self.put_id = call.id, put.id
        self.series_id = OptionSeriesId(
            BYBIT,
            "BTC",
            str(call.settlement_currency),
            call.expiration_ns,
        )
        self.subscribe_option_chain(
            series_id=self.series_id,
            strike_range=StrikeRange.atm_relative(strikes_above=1, strikes_below=1),
            snapshot_interval_ms=1_000,
        )

    def _recover_pair(self, positions) -> bool:
        by_instrument = {}
        for position in positions:
            if position.side != PositionSide.SHORT:
                return False
            by_instrument.setdefault(position.instrument_id, []).append(position)
        if len(by_instrument) != 2:
            return False

        call_put = {}
        for instrument_id, leg_positions in by_instrument.items():
            instrument = self._instruments[instrument_id]
            call_put[str(instrument.option_kind).upper()] = (
                instrument,
                leg_positions,
            )
        if "CALL" not in call_put or "PUT" not in call_put:
            return False
        call, call_positions = call_put["CALL"]
        put, put_positions = call_put["PUT"]
        if (
            call.expiration_ns != put.expiration_ns
            or call.strike_price != put.strike_price
            or call.settlement_currency != put.settlement_currency
        ):
            return False

        call_quantity = sum((p.quantity.as_decimal() for p in call_positions), Decimal(0))
        put_quantity = sum((p.quantity.as_decimal() for p in put_positions), Decimal(0))
        if call_quantity != put_quantity or call_quantity <= 0:
            return False

        self.call_id, self.put_id = call.id, put.id
        call_premium = sum(
            (p.quantity.as_decimal() * Decimal(str(p.avg_px_open)) for p in call_positions),
            Decimal(0),
        ) / call_quantity
        put_premium = sum(
            (p.quantity.as_decimal() * Decimal(str(p.avg_px_open)) for p in put_positions),
            Decimal(0),
        ) / put_quantity
        self.entry_premium = call_premium + put_premium
        self.entered = True
        self.subscribe_quotes(self.call_id)
        self.subscribe_quotes(self.put_id)
        self.log.info("Resumed matched short straddle from reconciled positions")
        return True

    def on_option_chain(self, chain: OptionChainSlice) -> None:
        if self.entered or chain.atm_strike is None:
            return
        call, put = select_pair(
            [
                instrument
                for instrument in self.cache.instruments()
                if isinstance(instrument, CryptoOption)
                and instrument.expiration_ns == chain.series_id.expiration_ns
                and str(instrument.settlement_currency) == str(chain.series_id.settlement_currency)
                and Decimal(str(instrument.strike_price))
                == Decimal(str(chain.atm_strike))
            ],
            self.clock.timestamp_ns(),
        ) or (None, None)
        if call is None or put is None:
            return

        self.call_id, self.put_id = call.id, put.id
        self.unsubscribe_option_chain(series_id=chain.series_id)

        # Reconciliation can restore positions after restart. Never open a
        # second straddle over existing exposure; require the strategy to
        # manage the reconciled position from its native position state.
        existing = [
            position
            for instrument_id in (self.call_id, self.put_id)
            for position in self.cache.positions_open(instrument_id=instrument_id)
        ]
        if existing:
            self.log.error(
                "Reconciled option position found; refusing duplicate entry. "
                "Manual review is required before this strategy can resume exits."
            )
            self.stop()
            return

        self.subscribe_quotes(self.call_id)
        self.subscribe_quotes(self.put_id)

    def on_quote(self, quote) -> None:
        if quote.instrument_id == self.call_id:
            self.call_quote = quote
        elif quote.instrument_id == self.put_id:
            self.put_quote = quote
        else:
            return

        if self.call_quote is None or self.put_quote is None:
            return
        now_ns = self.clock.timestamp_ns()
        quote_times = (self.call_quote.ts_event, self.put_quote.ts_event)
        if any(now_ns - ts > MAX_QUOTE_AGE_NS or ts > now_ns for ts in quote_times):
            self.log.warning("Skipping decision because an option quote is stale")
            return
        if abs(quote_times[0] - quote_times[1]) > MAX_QUOTE_SKEW_NS:
            self.log.warning("Skipping decision because option quotes are unsynchronized")
            return
        if self.call_quote.ask_price <= 0 or self.put_quote.ask_price <= 0:
            self.log.warning("Skipping decision because an option ask is unavailable")
            return
        if not self.entered:
            self._submit_entry()
        elif self.entry_premium is not None and not self.exiting:
            buyback = Decimal(str(self.call_quote.ask_price)) + Decimal(
                str(self.put_quote.ask_price)
            )
            reason = exit_reason(self.entry_premium, buyback)
            if reason:
                self.log.warning(f"Combined premium triggered {reason}: {buyback}")
                self._submit_exits()

    def _submit_entry(self) -> None:
        call = self.cache.instrument(self.call_id)
        put = self.cache.instrument(self.put_id)
        call_quantity = call.make_qty(float(self.quantity))
        put_quantity = put.make_qty(float(self.quantity))
        if call_quantity != put_quantity:
            self.log.error("Option size increments do not allow equal leg quantities")
            self.stop()
            return
        if call_quantity < call.min_quantity or put_quantity < put.min_quantity:
            self.log.error("Configured quantity is below an option minimum")
            self.stop()
            return

        self.entered = True
        for instrument_id, quantity in (
            (self.call_id, call_quantity),
            (self.put_id, put_quantity),
        ):
            order = self.order_factory.market(
                instrument_id=instrument_id,
                order_side=OrderSide.SELL,
                quantity=quantity,
                time_in_force=TimeInForce.GTC,
            )
            self.entry_orders.add(order.client_order_id)
            self.active_entry_orders.add(order.client_order_id)
            self.submit_order(order)

    def on_order_filled(self, event) -> None:
        client_order_id = event.client_order_id
        instrument_id = event.instrument_id
        self.log.info(
            f"Order fill: id={client_order_id} instrument={instrument_id} "
            f"side={event.order_side} qty={event.last_qty} px={event.last_px}"
        )
        if client_order_id in self.exit_orders:
            order = self.cache.order(client_order_id)
            if order is not None and order.is_closed:
                instrument_id = self.exit_orders.pop(client_order_id, None)
                if instrument_id is not None:
                    self.exit_retries.pop(instrument_id, None)
                self._submit_exits()
            return
        if client_order_id not in self.entry_orders:
            return

        quantity = Decimal(str(event.last_qty))
        price = Decimal(str(event.last_px))
        self.entry_fills[instrument_id] = self.entry_fills.get(instrument_id, Decimal(0)) + quantity
        self.entry_notional[instrument_id] = self.entry_notional.get(instrument_id, Decimal(0)) + quantity * price
        order = self.cache.order(client_order_id)
        if order is not None and order.is_closed:
            self.active_entry_orders.discard(client_order_id)

        if self.call_id in self.entry_fills and self.put_id in self.entry_fills:
            call_qty = self.entry_fills[self.call_id]
            put_qty = self.entry_fills[self.put_id]
            all_entry_orders_closed = all(
                (order := self.cache.order(order_id)) is not None and order.is_closed
                for order_id in self.entry_orders
            )
            self.entry_premium = (
                combined_entry_premium(
                    call_qty,
                    self.entry_notional[self.call_id],
                    put_qty,
                    self.entry_notional[self.put_id],
                )
                if all_entry_orders_closed
                else None
            )
            if all_entry_orders_closed and self.entry_premium is None:
                self._handle_entry_failure(event)
        if self.exiting:
            self._submit_exits()

    def on_order_accepted(self, event) -> None:
        self.log.info(
            f"Order accepted: id={event.client_order_id} instrument={event.instrument_id}"
        )

    def on_position_opened(self, event) -> None:
        self.log.info(
            f"Position opened: id={event.position_id} instrument={event.instrument_id}"
        )

    def on_position_closed(self, event) -> None:
        self.log.info(
            f"Position closed: id={event.position_id} instrument={event.instrument_id}"
        )

    def on_order_canceled(self, event) -> None:
        if event.client_order_id in self.exit_orders:
            self._retry_or_report_exit(event.client_order_id, "canceled")
        elif event.client_order_id in self.entry_orders:
            self.active_entry_orders.discard(event.client_order_id)
            if self.exiting:
                self._submit_exits()
            else:
                self._handle_entry_failure(event)

    def on_order_rejected(self, event) -> None:
        if event.client_order_id in self.exit_orders:
            self._retry_or_report_exit(event.client_order_id, "rejected")
            return
        if event.client_order_id not in self.entry_orders:
            return
        self.active_entry_orders.discard(event.client_order_id)
        self._handle_entry_failure(event)

    def on_order_denied(self, event) -> None:
        if event.client_order_id in self.entry_orders:
            self.active_entry_orders.discard(event.client_order_id)
            self._handle_entry_failure(event)
        elif event.client_order_id in self.exit_orders:
            self._retry_or_report_exit(event.client_order_id, "denied")

    def on_order_expired(self, event) -> None:
        if event.client_order_id in self.exit_orders:
            self._retry_or_report_exit(event.client_order_id, "expired")
        elif event.client_order_id in self.entry_orders:
            self.active_entry_orders.discard(event.client_order_id)
            self._handle_entry_failure(event)

    def _retry_or_report_exit(self, client_order_id, outcome: str) -> None:
        instrument_id = self.exit_orders.pop(client_order_id, None)
        if instrument_id is None:
            return
        retries = self.exit_retries.get(instrument_id, 0)
        if retries >= 1:
            self.log.error(
                f"Exit {outcome} twice; short exposure may remain on {instrument_id}"
            )
            return
        self.exit_retries[instrument_id] = retries + 1
        self.log.warning(f"Exit {outcome}; retrying once for {instrument_id}")
        self._submit_exits()

    def _handle_entry_failure(self, event) -> None:
        self.log.error(f"Entry failed or leg fills do not match: {event.client_order_id}")
        self._submit_exits()

    def _submit_exits(self) -> None:
        if not self.exiting:
            for client_order_id in self.active_entry_orders:
                self.cancel_order(client_order_id)
        self.exiting = True
        for instrument_id in (self.call_id, self.put_id):
            if instrument_id is None:
                continue
            if instrument_id in self.exit_orders.values():
                continue
            for position in self.cache.positions_open(instrument_id=instrument_id):
                if (
                    position.side != PositionSide.SHORT
                    or position.quantity.as_decimal() <= 0
                ):
                    continue
                order = self.order_factory.market(
                    instrument_id=instrument_id,
                    order_side=OrderSide.BUY,
                    quantity=position.quantity,
                    time_in_force=TimeInForce.GTC,
                    reduce_only=True,
                )
                self.exit_orders[order.client_order_id] = instrument_id
                self.submit_order(order)

    def on_stop(self) -> None:
        # Best effort only: a local shutdown cannot guarantee exchange fills.
        # Cancel entry orders while keeping already-submitted exits alive.
        for client_order_id in self.active_entry_orders:
            self.cancel_order(client_order_id)
        if self.entered:
            self._submit_exits()
        if self.series_id is not None:
            self.unsubscribe_option_chain(series_id=self.series_id)
        if self.call_id is not None:
            self.unsubscribe_quotes(self.call_id)
        if self.put_id is not None:
            self.unsubscribe_quotes(self.put_id)
