from config import settings
from logger import log
from strategy import Signal
from trade_manager import Trade


def calculate_amount(client, symbol: str, signal: Signal) -> float:
    """Risk-based position sizing using account USDT balance and stop distance."""
    balance = client.balance_usdt()
    risk_usdt = balance * (settings.risk_percent / 100.0)
    if signal.risk_per_unit <= 0:
        raise ValueError("Invalid signal risk distance")
    amount = risk_usdt / signal.risk_per_unit
    amount = client.amount_to_precision(symbol, amount)
    if amount <= 0:
        raise ValueError("Calculated amount is zero. Increase balance/risk or use a larger market.")
    log.info(f"Balance={balance} Risk%={settings.risk_percent} RiskUSDT={risk_usdt} Amount={amount}")
    return amount


def should_move_to_break_even(trade: Trade, price: float) -> bool:
    if trade.break_even_moved:
        return False
    if trade.side == "buy":
        return price >= trade.break_even_price
    return price <= trade.break_even_price


def should_stop_or_take_profit(trade: Trade, price: float):
    if trade.side == "buy":
        if price <= trade.stop_loss:
            return "stop_loss"
        if price >= trade.take_profit:
            return "take_profit"
    else:
        if price >= trade.stop_loss:
            return "stop_loss"
        if price <= trade.take_profit:
            return "take_profit"
    return None
