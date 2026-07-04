from logger import log
from strategy import Signal
from trade_manager import TradeManager, Trade
from risk_manager import calculate_amount


class OrderManager:
    def __init__(self, client, trade_manager: TradeManager):
        self.client = client
        self.trade_manager = trade_manager

    def open_signal(self, symbol: str, signal: Signal):
        if self.trade_manager.has_trade_for_signal(symbol, signal.timeframe, signal.candle3_time):
            log.info(f"Signal already traded: {symbol} {signal.timeframe} {signal.candle3_time}")
            return None

        amount = calculate_amount(self.client, symbol, signal)
        self.client.create_market_order(symbol, signal.side, amount, reduce_only=False)
        return self.trade_manager.add_trade(symbol, signal, amount)

    def close_trade(self, trade: Trade, reason: str, price: float):
        close_side = "sell" if trade.side == "buy" else "buy"
        self.client.create_market_order(trade.symbol, close_side, trade.amount, reduce_only=True)
        self.trade_manager.close_trade(trade, price, reason)
