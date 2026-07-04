from config import settings
from logger import log
from strategy import Signal
from trade_manager import Trade


def calculate_amount(client, symbol: str, signal: Signal) -> float:
    """
    Risk-based position sizing.

    Important for MEXC futures:
    BTC/USDT:USDT orders are usually sized in whole contracts, not decimal BTC.
    So we calculate the BTC/base amount first, then convert it into contracts
    using the market contractSize from ccxt.
    """
    balance = client.balance_usdt()
    risk_usdt = balance * (settings.risk_percent / 100.0)

    if signal.risk_per_unit <= 0:
        raise ValueError("Invalid signal risk distance")

    # Base asset amount, for example BTC amount.
    base_amount = risk_usdt / signal.risk_per_unit

    market = client.exchange.market(symbol)
    contract_size = market.get("contractSize") or 1

    # For swaps/futures, ccxt amount is normally number of contracts.
    if market.get("contract", False):
        raw_contracts = base_amount / float(contract_size)

        # MEXC requires whole contracts. Use floor so risk does not exceed the target too much.
        contracts = int(raw_contracts)

        if contracts < 1:
            contracts = 1
            log.warning(
                "Calculated size is below MEXC minimum. Using minimum 1 contract. "
                "This may risk more than your configured risk percent on small balances."
            )

        amount = float(contracts)

        approx_base_amount = amount * float(contract_size)
        approx_risk = approx_base_amount * signal.risk_per_unit

        log.info(
            f"Balance={balance:.4f} USDT | Risk%={settings.risk_percent} | "
            f"RiskUSDT={risk_usdt:.4f} | ContractSize={contract_size} | "
            f"Amount={amount} contracts | ApproxRisk={approx_risk:.4f} USDT"
        )
        return amount

    # Spot-style fallback. The bot is intended for futures, but this avoids crashing
    # if the market is not marked as a contract by the exchange metadata.
    amount = float(client.amount_to_precision(symbol, base_amount))

    if amount <= 0:
        raise ValueError("Calculated amount is zero. Increase balance/risk or use a larger market.")

    log.info(
        f"Balance={balance:.4f} USDT | Risk%={settings.risk_percent} | "
        f"RiskUSDT={risk_usdt:.4f} | Amount={amount}"
    )
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
