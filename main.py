import time
import traceback

from config import settings
from logger import log
from mexc_client import MexcClient
from strategy import detect_dls_signal
from trade_manager import TradeManager
from order_manager import OrderManager
from risk_manager import should_move_to_break_even, should_stop_or_take_profit


BOT_VERSION = "multi-symbol-fix-v2"
_seen_signals = set()


def check_new_signals(client: MexcClient, orders: OrderManager):
    for symbol in settings.symbols:
        for timeframe in settings.timeframes:
            try:
                df = client.fetch_closed_candles(symbol, timeframe, limit=100)

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

            except Exception as exc:
                log.error(f"Error checking {symbol} {timeframe}: {exc}")
                log.error(traceback.format_exc())


def manage_open_trades(client: MexcClient, trades: TradeManager, orders: OrderManager):
    for trade in list(trades.open_trades):
        try:
            price = client.last_price(trade.symbol)

            if should_move_to_break_even(trade, price):
                trade.stop_loss = trade.entry
                trade.break_even_moved = True
                log.info(f"Moved SL to break-even: {trade.trade_id}")

            reason = should_stop_or_take_profit(trade, price)
            if reason:
                orders.close_trade(trade, reason, price)

        except Exception as exc:
            log.error(f"Error managing trade {trade.trade_id}: {exc}")
            log.error(traceback.format_exc())


def main():
    log.info(f"Starting MEXC DLS bot | version={BOT_VERSION}")
    log.info(f"Symbols={settings.symbols} Timeframes={settings.timeframes} DryRun={settings.dry_run}")

    client = MexcClient()
    trades = TradeManager()
    orders = OrderManager(client, trades)

    while True:
        manage_open_trades(client, trades, orders)
        check_new_signals(client, orders)
        time.sleep(settings.check_interval_seconds)


if __name__ == "__main__":
    main()
