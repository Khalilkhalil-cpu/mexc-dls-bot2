from dataclasses import dataclass, asdict
from typing import Literal
import csv
import os
from datetime import datetime, timezone
from logger import log
from strategy import Signal

Side = Literal["buy", "sell"]


@dataclass
class Trade:
    trade_id: str
    symbol: str
    side: Side
    timeframe: str
    amount: float
    entry: float
    stop_loss: float
    take_profit: float
    break_even_price: float
    risk_per_unit: float
    candle3_time: int
    break_even_moved: bool = False
    is_open: bool = True


class TradeManager:
    def __init__(self):
        self.open_trades: list[Trade] = []
        os.makedirs("logs", exist_ok=True)
        self.history_path = "logs/trade_history.csv"
        if not os.path.exists(self.history_path):
            with open(self.history_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "closed_at_utc", "trade_id", "symbol", "side", "timeframe", "amount",
                    "entry", "exit_price", "stop_loss", "take_profit", "reason", "pnl_estimate"
                ])

    def has_trade_for_signal(self, symbol: str, timeframe: str, candle3_time: int) -> bool:
        return any(
            t.symbol == symbol and t.timeframe == timeframe and t.candle3_time == candle3_time
            for t in self.open_trades
        )

    def add_trade(self, symbol: str, signal: Signal, amount: float) -> Trade:
        trade = Trade(
            trade_id=f"{symbol}-{signal.timeframe}-{signal.candle3_time}-{signal.side}",
            symbol=symbol,
            side=signal.side,
            timeframe=signal.timeframe,
            amount=amount,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            break_even_price=signal.break_even_price,
            risk_per_unit=signal.risk_per_unit,
            candle3_time=signal.candle3_time,
        )
        self.open_trades.append(trade)
        log.info(f"Trade opened: {asdict(trade)}")
        return trade

    def close_trade(self, trade: Trade, exit_price: float, reason: str):
        if not trade.is_open:
            return
        trade.is_open = False
        if trade.side == "buy":
            pnl = (exit_price - trade.entry) * trade.amount
        else:
            pnl = (trade.entry - exit_price) * trade.amount
        with open(self.history_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now(timezone.utc).isoformat(), trade.trade_id, trade.symbol, trade.side,
                trade.timeframe, trade.amount, trade.entry, exit_price, trade.stop_loss,
                trade.take_profit, reason, pnl
            ])
        log.info(f"Trade closed: {trade.trade_id} reason={reason} exit={exit_price} pnl_estimate={pnl}")
        self.open_trades = [t for t in self.open_trades if t.is_open]
