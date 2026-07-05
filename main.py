import time
import traceback
from datetime import datetime, timezone

from config import settings
from logger import log
from mexc_client import MexcClient
from strategy import detect_dls_signal
from trade_manager import TradeManager
from order_manager import OrderManager
from risk_manager import should_move_to_break_even, should_stop_or_take_profit

BOT_VERSION = "multi-symbol-fix-v3-rate-limit"
_seen_signals = set()
_last_price_cache = {}


def get_setting(name, default):
    return getattr(settings, name, default)


def safe_sleep(seconds):
    try:
        time.sleep(float(seconds))
    except Exception:
        time.sleep(1)


def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "requests are too frequent" in text or "code\":510" in text or "code=510" in text


def cached_last_price(client: MexcClient, symbol: str):
    ttl = float(get_setting("PRICE_CACHE_SECONDS", 15))
    now = time.time()
    cached = _last_price_cache.get(symbol)
    if cached and now - cached["time"] <= ttl:
        return cached["price"]

    price = client.last_price(symbol)
    _last_price_cache[symbol] = {"price": price, "time": now}
    safe_sleep(get_setting("REQUEST_DELAY_SECONDS", 0.5))
    return price


def check_new_signals(client: MexcClient, orders: OrderManager):
    max_symbols = int(get_setting("MAX_SYMBOLS_PER_CYCLE", len(settings.symbols)))
    symbols = list(settings.symbols)[:max_symbols]

    for symbol in symbols:
        for timeframe in settings.timeframes:
            try:
                df = client.fetch_closed_candles(symbol, timeframe, limit=100)
                safe_sleep(get_setting("REQUEST_DELAY_SECONDS", 0.5))

                signal = detect_dls_signal(
                    df,
                    timeframe=timeframe,
                    risk_reward=settings.risk_reward,
                    break_even_r=settings.break_even_r,
                )

                if signal is None:
                    log.info(f"No DLS setup found: {symbol} {timeframe}")
                    continue

                signal_key = (symbol, timeframe, signal.side, signal.candle3_time)
                if signal_key in _seen_signals:
                    log.info(f"Signal already processed: {symbol} {timeframe} {signal.side}")
                    continue

                _seen_signals.add(signal_key)

                log.info(
                    f"DLS signal found: {signal.side.upper()} {symbol} {timeframe} "
                    f"entry={signal.entry} sl={signal.stop_loss} "
                    f"tp={signal.take_profit} be={signal.break_even_price}"
                )

                orders.open_signal(symbol, signal)
                safe_sleep(get_setting("ORDER_DELAY_SECONDS", 1.0))

            except Exception as exc:
                log.error(f"Error checking {symbol} {timeframe}: {exc}")
                log.error(traceback.format_exc())
                if is_rate_limit_error(exc):
                    backoff = get_setting("RATE_LIMIT_BACKOFF_SECONDS", 60)
                    log.warning(f"MEXC rate limit hit while scanning. Sleeping {backoff}s")
                    safe_sleep(backoff)

        safe_sleep(get_setting("SYMBOL_DELAY_SECONDS", 1.0))


def manage_open_trades(client: MexcClient, trades: TradeManager, orders: OrderManager):
    for trade in list(trades.open_trades):
        try:
            price = cached_last_price(client, trade.symbol)

            if should_move_to_break_even(trade, price):
                trade.stop_loss = trade.entry
                trade.break_even_moved = True
                log.info(f"Moved SL to break-even: {trade.trade_id}")

            reason = should_stop_or_take_profit(trade, price)
            if reason:
                orders.close_trade(trade, reason, price)
                safe_sleep(get_setting("ORDER_DELAY_SECONDS", 1.0))

        except Exception as exc:
            log.error(f"Error managing trade {trade.trade_id}: {exc}")
            log.error(traceback.format_exc())
            if is_rate_limit_error(exc):
                backoff = get_setting("RATE_LIMIT_BACKOFF_SECONDS", 60)
                log.warning(f"MEXC rate limit hit while managing trades. Sleeping {backoff}s")
                safe_sleep(backoff)


def main():
    log.info(f"Starting MEXC DLS bot | version={BOT_VERSION}")
    log.info(
        f"Symbols={settings.symbols} Timeframes={settings.timeframes} DryRun={settings.dry_run} "
        f"MaxSymbols={get_setting('MAX_SYMBOLS_PER_CYCLE', len(settings.symbols))} "
        f"RequestDelay={get_setting('REQUEST_DELAY_SECONDS', 0.5)} "
        f"SymbolDelay={get_setting('SYMBOL_DELAY_SECONDS', 1.0)} "
        f"PriceCache={get_setting('PRICE_CACHE_SECONDS', 15)}s"
    )

    client = MexcClient()
    trades = TradeManager()
    orders = OrderManager(client, trades)

    while True:
        manage_open_trades(client, trades, orders)
        check_new_signals(client, orders)
        safe_sleep(get_setting("check_interval_seconds", get_setting("CHECK_INTERVAL_SECONDS", 120)))


if __name__ == "__main__":
    main()
