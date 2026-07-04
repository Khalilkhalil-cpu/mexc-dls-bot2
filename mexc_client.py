import ccxt
import pandas as pd
from config import settings
from logger import log


class MexcClient:
    def __init__(self):
        self.exchange = ccxt.mexc({
            "apiKey": settings.mexc_api_key,
            "secret": settings.mexc_secret_key,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
        self.exchange.load_markets()
        if settings.leverage:
            try:
                self.exchange.set_leverage(settings.leverage, settings.symbol)
                log.info(f"Leverage set to {settings.leverage}x for {settings.symbol}")
            except Exception as exc:
                log.warning(f"Could not set leverage: {exc}")

    def fetch_closed_candles(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        # Remove the newest candle because it may still be forming.
        if len(df) > 0:
            df = df.iloc[:-1].copy()
        return df

    def last_price(self, symbol: str) -> float:
        ticker = self.exchange.fetch_ticker(symbol)
        return float(ticker["last"])

    def balance_usdt(self) -> float:
        bal = self.exchange.fetch_balance()
        for key in ("USDT", "usdt"):
            if key in bal.get("total", {}):
                return float(bal["total"][key])
        return float(bal.get("total", {}).get("USDT", 0) or 0)

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        return float(self.exchange.amount_to_precision(symbol, amount))

    def price_to_precision(self, symbol: str, price: float) -> float:
        return float(self.exchange.price_to_precision(symbol, price))

    def create_market_order(self, symbol: str, side: str, amount: float, reduce_only: bool = False):
        params = {"reduceOnly": reduce_only} if reduce_only else {}
        if settings.dry_run:
            log.info(f"DRY_RUN order: {side.upper()} {amount} {symbol} reduce_only={reduce_only}")
            return {"id": "dry_run", "side": side, "amount": amount, "symbol": symbol}
        return self.exchange.create_order(symbol, "market", side, amount, None, params)
