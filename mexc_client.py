import ccxt
from config import MEXC_API_KEY, MEXC_SECRET_KEY

exchange = ccxt.mexc({
    "apiKey": MEXC_API_KEY,
    "secret": MEXC_SECRET_KEY,
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})


def get_balance():
    return exchange.fetch_balance()


def get_ohlcv(symbol, timeframe, limit=100):
    return exchange.fetch_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit
    )


def get_ticker(symbol):
    return exchange.fetch_ticker(symbol)


def create_market_buy(symbol, amount):
    return exchange.create_market_buy_order(symbol, amount)


def create_market_sell(symbol, amount):
    return exchange.create_market_sell_order(symbol, amount)


def create_limit_buy(symbol, amount, price):
    return exchange.create_limit_buy_order(symbol, amount, price)


def create_limit_sell(symbol, amount, price):
    return exchange.create_limit_sell_order(symbol, amount, price)


def cancel_order(order_id, symbol):
    return exchange.cancel_order(order_id, symbol)


def fetch_positions():
    try:
        return exchange.fetch_positions()
    except Exception:
        return []
