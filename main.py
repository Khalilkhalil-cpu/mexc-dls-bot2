from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

from config import settings
from mexc_client import MexcClient
from state_store import StateStore
from strategy import Signal, find_new_signal
from ai_reviewer import AIReviewer


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


log = logging.getLogger("ema-fib-live")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def position_map(client: MexcClient) -> dict[str, dict]:
    return {p["symbol"]: p for p in client.fetch_positions()}


def live_trade_record(signal: Signal, amount: float, actual_entry: float, order_id: str) -> dict:
    risk = abs(actual_entry - signal.stop_loss)
    if signal.side == "buy":
        tp = actual_entry + settings.reward_risk * risk
        be_trigger = actual_entry + settings.break_even_at_r * risk
    else:
        tp = actual_entry - settings.reward_risk * risk
        be_trigger = actual_entry - settings.break_even_at_r * risk

    return {
        "signal_id": signal.signal_id,
        "symbol": signal.symbol,
        "side": signal.side,
        "amount": amount,
        "entry": actual_entry,
        "initial_stop": signal.stop_loss,
        "active_stop": signal.stop_loss,
        "take_profit": tp,
        "break_even_trigger": be_trigger,
        "break_even_moved": False,
        "entry_order_id": order_id,
        "opened_at": now_iso(),
    }


def manage_trades(client: MexcClient, state: StateStore, positions: dict[str, dict]) -> None:
    for symbol, trade in list(state.managed_trades.items()):
        position = positions.get(symbol)
        if position is None:
            log.info("Managed position no longer open | %s | removing state", symbol)
            state.remove_trade(symbol)
            continue

        price = client.ticker_price(symbol)
        side = trade["side"]
        entry = float(trade["entry"])
        active_stop = float(trade["active_stop"])
        tp = float(trade["take_profit"])
        be_trigger = float(trade["break_even_trigger"])

        if not trade.get("break_even_moved", False):
            reached_be = price >= be_trigger if side == "buy" else price <= be_trigger
            if reached_be:
                trade["active_stop"] = entry
                trade["break_even_moved"] = True
                state.set_trade(symbol, trade)
                active_stop = entry
                log.warning(
                    "BREAK-EVEN ACTIVATED | %s | side=%s | entry=%.10g",
                    symbol, side, entry,
                )

        hit_stop = price <= active_stop if side == "buy" else price >= active_stop
        hit_tp = price >= tp if side == "buy" else price <= tp
        if not (hit_stop or hit_tp):
            continue

        reason = "TAKE_PROFIT" if hit_tp else (
            "BREAK_EVEN" if trade.get("break_even_moved") and active_stop == entry else "STOP_LOSS"
        )
        amount = min(float(trade["amount"]), float(position["amount"]))

        if settings.live_trading:
            order = client.close_position(symbol, side, amount)
            order_id = str(order.get("id") or "")
        else:
            order_id = "DRY_RUN_CLOSE"

        log.warning(
            "POSITION CLOSED | %s | reason=%s | side=%s | amount=%s | price=%.10g | order_id=%s",
            symbol, reason, side, amount, price, order_id,
        )
        state.remove_trade(symbol)


def reconcile_unmanaged(state: StateStore, positions: dict[str, dict]) -> set[str]:
    blocked: set[str] = set()
    for symbol, position in positions.items():
        if symbol not in state.managed_trades:
            blocked.add(symbol)
            log.warning(
                "UNMANAGED LIVE POSITION | %s | side=%s | amount=%s | action=BLOCK_NEW_ENTRY",
                symbol, position["side"], position["amount"],
            )
    return blocked


def open_signal(client: MexcClient, state: StateStore, signal: Signal) -> None:
    reference_price = client.ticker_price(signal.symbol)
    amount = client.amount_for_notional(
        signal.symbol,
        settings.position_notional_usdt,
        reference_price,
    )

    if settings.live_trading:
        order = client.create_entry(signal.symbol, signal.side, amount)
        order_id = str(order.get("id") or "")
        actual_entry = float(order.get("average") or order.get("price") or reference_price)
    else:
        order_id = "DRY_RUN_ENTRY"
        actual_entry = reference_price

    record = live_trade_record(signal, amount, actual_entry, order_id)
    state.set_trade(signal.symbol, record)
    state.mark_signal_used(signal.signal_id)

    estimated_margin = settings.position_notional_usdt / settings.leverage
    log.warning(
        "ENTRY OPENED | %s | side=%s | notional=%.2f USDT | leverage=%sx | "
        "estimated_margin=%.2f USDT | amount=%s | entry=%.10g | SL=%.10g | "
        "BE=%.10g | TP=%.10g | order_id=%s",
        signal.symbol,
        signal.side,
        settings.position_notional_usdt,
        settings.leverage,
        estimated_margin,
        amount,
        actual_entry,
        record["initial_stop"],
        record["break_even_trigger"],
        record["take_profit"],
        order_id,
    )


def run() -> None:
    configure_logging()
    settings.validate()

    log.info("=" * 72)
    log.info("MEXC AI EXTERNAL SWING ENGINE LIVE BOT v2.00")
    log.info("EXTERNAL 1H SWINGS + RANKED 15M LIQUIDITY + AI FAIL-CLOSED REVIEW")
    log.info("=" * 72)
    log.info(
        "MODE=%s | position_notional=%.2f USDT | leverage=%sx | margin=%s",
        "LIVE" if settings.live_trading else "DRY_RUN",
        settings.position_notional_usdt,
        settings.leverage,
        settings.margin_mode,
    )
    log.info(
        "TP=%.2fR | BE=%.2fR | symbols=%s",
        settings.reward_risk,
        settings.break_even_at_r,
        ", ".join(settings.symbols),
    )
    log.warning(
        "Stops and take-profit are managed persistently by the running bot. "
        "Keep the process and /data state volume online."
    )

    state = StateStore(settings.state_file)
    client = MexcClient(settings)
    reviewer = AIReviewer(settings)
    client.validate_symbols()

    for symbol in settings.symbols:
        client.configure_symbol(symbol)

    equity, available = client.account_summary()
    positions = position_map(client)
    log.info(
        "CONNECTED | markets=%s | equity=%.2f USDT | available=%.2f USDT | open_positions=%s",
        len(client.markets), equity, available, len(positions),
    )

    last_heartbeat = 0.0
    last_processed_candle: dict[str, object] = {}

    while True:
        cycle_start = time.time()
        try:
            positions = position_map(client)
            manage_trades(client, state, positions)
            positions = position_map(client)
            unmanaged = reconcile_unmanaged(state, positions)

            for symbol in settings.symbols:
                if symbol in positions or symbol in state.managed_trades or symbol in unmanaged:
                    continue
                if len(positions) >= settings.max_open_positions:
                    break

                try:
                    df15 = client.fetch_closed_15m(symbol, settings.history_15m_bars)
                    if df15.empty:
                        continue

                    closed_time = df15.index[-1]
                    if last_processed_candle.get(symbol) == closed_time:
                        continue
                    last_processed_candle[symbol] = closed_time

                    signal, analysis_context = find_new_signal(
                        symbol, df15, settings, state.used_signals,
                    )
                    if signal is None:
                        log.info("SCAN | %s | closed=%s | status=%s", symbol, closed_time, analysis_context.get("status"))
                        continue

                    approved, decision, reason = reviewer.review(signal, analysis_context)
                    log.warning(
                        "AI REVIEW | %s | candidate=%s | side=%s | score=%s | decision=%s | approved=%s | reason=%s",
                        symbol, signal.candidate_id, signal.side, signal.score, decision, approved, reason,
                    )
                    if not approved:
                        continue

                    log.warning(
                        "APPROVED SIGNAL | %s | side=%s | confirmation=%s | fib=%.10g-%.10g | liquidity=%.10g | break=%.10g | score=%s",
                        symbol, signal.side, signal.confirmation_time, signal.zone_low, signal.zone_high,
                        signal.liquidity_price, signal.structure_break_price, signal.score,
                    )
                    open_signal(client, state, signal)
                    positions = position_map(client)
                except Exception:
                    log.exception("SYMBOL ERROR | %s", symbol)

            if time.time() - last_heartbeat >= settings.heartbeat_seconds:
                equity, available = client.account_summary()
                positions = position_map(client)
                log.info(
                    "HEARTBEAT | equity=%.2f | available=%.2f | "
                    "open_positions=%s | managed=%s",
                    equity,
                    available,
                    len(positions),
                    len(state.managed_trades),
                )
                last_heartbeat = time.time()

        except KeyboardInterrupt:
            log.warning("Shutdown requested.")
            return
        except Exception:
            log.exception("MAIN LOOP ERROR")

        elapsed = time.time() - cycle_start
        time.sleep(max(1.0, settings.poll_seconds - elapsed))


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("startup").exception("FATAL STARTUP ERROR: %s", exc)
        sys.exit(1)
