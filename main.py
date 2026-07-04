import time
import traceback

from config import settings
from logger import log
from mexc_client import MexcClient
from order_manager import OrderManager
from strategy import detect_dls_signal


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

                # Prevent the same closed candle signal being opened again every minute.
                signal_key = (symbol, timeframe, signal.side, signal.candle3_time)
                if signal_key in _seen_signals:
                    log.info(f"Signal already processed: {symbol} {timeframe} {signal.side} {signal.candle3_time}")
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


def manage_open_trades(client: MexcClient, orders: OrderManager):
    for symbol in settings.symbols:
        try:
            orders.manage_open_trades(symbol)
        except Exception as exc:
            log.error(f"Error managing trades for {symbol}: {exc}")
            log.error(traceback.format_exc())


def main():
    log.info("Starting MEXC DLS bot")
    log.info(f"Symbols={settings.symbols} Timeframes={settings.timeframes} DryRun={settings.dry_run}")

    client = MexcClient()
    orders = OrderManager(client)

    while True:
        try:
            check_new_signals(client, orders)
            manage_open_trades(client, orders)
        except Exception as exc:
            log.error(f"Bot error: {exc}")
            log.error(traceback.format_exc())

        time.sleep(settings.check_interval_seconds)


if __name__ == "__main__":
    main()
