import time
from config import settings
from logger import log
from mexc_client import MexcClient
from strategy import detect_dls_signal
from trade_manager import TradeManager
from order_manager import OrderManager
from risk_manager import should_move_to_break_even, should_stop_or_take_profit


def check_new_signals(client: MexcClient, orders: OrderManager):
    for timeframe in settings.timeframes:
        df = client.fetch_closed_candles(settings.symbol, timeframe, limit=100)
        signal = detect_dls_signal(
            df,
            timeframe=timeframe,
            risk_reward=settings.risk_reward,
            break_even_r=settings.break_even_r,
        )
        if signal:
            log.info(
                f"DLS signal found: {signal.side.upper()} {settings.symbol} {timeframe} "
                f"entry={signal.entry} sl={signal.stop_loss} tp={signal.take_profit} be={signal.break_even_price}"
            )
            orders.open_signal(settings.symbol, signal)


def manage_open_trades(client: MexcClient, trades: TradeManager, orders: OrderManager):
    if not trades.open_trades:
        return
    price = client.last_price(settings.symbol)
    for trade in list(trades.open_trades):
        if should_move_to_break_even(trade, price):
            trade.stop_loss = trade.entry
            trade.break_even_moved = True
            log.info(f"Moved SL to break-even: {trade.trade_id} new_sl={trade.stop_loss}")

        reason = should_stop_or_take_profit(trade, price)
        if reason:
            orders.close_trade(trade, reason, price)


def main():
    log.info("Starting MEXC DLS bot")
    log.info(f"Symbol={settings.symbol} Timeframes={settings.timeframes} DryRun={settings.dry_run}")
    if not settings.dry_run and (not settings.mexc_api_key or not settings.mexc_secret_key):
        raise RuntimeError("MEXC_API_KEY and MEXC_SECRET_KEY are required for live trading")

    client = MexcClient()
    trades = TradeManager()
    orders = OrderManager(client, trades)

    while True:
        try:
            manage_open_trades(client, trades, orders)
            check_new_signals(client, orders)
        except Exception as exc:
            log.exception(f"Bot error: {exc}")
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
