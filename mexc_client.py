import time
import requests
import ccxt
import pandas as pd
from config import settings
from logger import log


MEXC_FUTURES_BASE_URL = "https://contract.mexc.com"


class MexcClient:
    def __init__(self):
        self.exchange = ccxt.mexc({
            "apiKey": settings.mexc_api_key,
            "secret": settings.mexc_secret_key,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })

        # load_markets is useful for order precision and live orders.
        # Candle data below uses MEXC Futures REST directly because MEXC does not support native 2h futures candles.
        try:
            self.exchange.load_markets()
        except Exception as exc:
            log.warning(f"Could not load markets from ccxt yet: {exc}")

        if settings.leverage:
            try:
                self.exchange.set_leverage(settings.leverage, settings.symbol)
                log.info(f"Leverage set to {settings.leverage}x for {settings.symbol}")
            except Exception as exc:
                log.warning(f"Could not set leverage: {exc}")

    def _contract_symbol(self, symbol: str) -> str:
        """
        Convert ccxt-style symbols like BTC/USDT:USDT into MEXC contract symbols like BTC_USDT.
        """
        s = symbol.strip().upper()

        if "/" in s:
            base = s.split("/")[0]
            quote_part = s.split("/")[1]
            quote = quote_part.split(":")[0]
            return f"{base}_{quote}"

        if "_" in s:
            return s

        if s.endswith("USDT"):
            return f"{s[:-4]}_USDT"

        return s

    def _fetch_futures_1h_candles(self, symbol: str, limit: int = 300) -> pd.DataFrame:
        """
        Fetch 1H futures candles directly from MEXC contract API.
        MEXC Futures candle interval for 1H is Min60.
        """
        contract_symbol = self._contract_symbol(symbol)

        end = int(time.time())
        # Add extra hours so after removing active candle and aggregating 2H we still have enough history.
        start = end - (limit + 10) * 60 * 60

        url = f"{MEXC_FUTURES_BASE_URL}/api/v1/contract/kline/{contract_symbol}"
        params = {
            "interval": "Min60",
            "start": start,
            "end": end,
        }

        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()

        if not payload.get("success", False):
            raise RuntimeError(f"MEXC kline error: {payload}")

        data = payload.get("data", {})

        # MEXC normally returns dict arrays:
        # {"time":[...], "open":[...], "close":[...], "high":[...], "low":[...], "vol":[...]}
        if isinstance(data, dict):
            times = data.get("time", [])
            opens = data.get("open", [])
            highs = data.get("high", [])
            lows = data.get("low", [])
            closes = data.get("close", [])
            volumes = data.get("vol", data.get("volume", []))

            rows = []
            for i in range(min(len(times), len(opens), len(highs), len(lows), len(closes))):
                rows.append({
                    "timestamp": int(times[i]) * 1000,
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "volume": float(volumes[i]) if i < len(volumes) else 0.0,
                })
            df = pd.DataFrame(rows)

        # Fallback if API returns list-style rows.
        elif isinstance(data, list):
            rows = []
            for row in data:
                if isinstance(row, dict):
                    ts = row.get("time") or row.get("t") or row.get("timestamp")
                    rows.append({
                        "timestamp": int(ts) * 1000 if int(ts) < 10_000_000_000 else int(ts),
                        "open": float(row.get("open", row.get("o"))),
                        "high": float(row.get("high", row.get("h"))),
                        "low": float(row.get("low", row.get("l"))),
                        "close": float(row.get("close", row.get("c"))),
                        "volume": float(row.get("vol", row.get("volume", row.get("v", 0)))),
                    })
                else:
                    # common format: [time, open, high, low, close, volume]
                    ts = int(row[0])
                    rows.append({
                        "timestamp": ts * 1000 if ts < 10_000_000_000 else ts,
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]) if len(row) > 5 else 0.0,
                    })
            df = pd.DataFrame(rows)

        else:
            raise RuntimeError(f"Unexpected MEXC kline response format: {payload}")

        if df.empty:
            raise RuntimeError(f"No candles returned for {contract_symbol}")

        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)

        # Remove the current active 1H candle.
        current_1h_start_ms = (int(time.time()) // 3600) * 3600 * 1000
        df = df[df["timestamp"] < current_1h_start_ms].copy()

        return df.tail(limit).reset_index(drop=True)

    def _aggregate_2h_from_1h(self, df_1h: pd.DataFrame, limit: int = 100) -> pd.DataFrame:
        """
        Build 2H candles from closed 1H candles.
        """
        df = df_1h.copy()
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("datetime")

        agg = df.resample("2h", label="left", closed="left").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        # Keep only completed 2H candles.
        current_2h_start_ms = (int(time.time()) // 7200) * 7200 * 1000
        agg["timestamp"] = (agg.index.view("int64") // 1_000_000).astype("int64")
        agg = agg[agg["timestamp"] < current_2h_start_ms]

        return agg[["timestamp", "open", "high", "low", "close", "volume"]].tail(limit).reset_index(drop=True)

    def fetch_closed_candles(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        timeframe = timeframe.lower().strip()

        if timeframe == "1h":
            df = self._fetch_futures_1h_candles(symbol, limit=limit + 5)
            log.info(f"Fetched {len(df)} closed 1h candles for {symbol}")
            return df.tail(limit).reset_index(drop=True)

        if timeframe == "2h":
            # Need roughly double the 1H candles to build 2H candles.
            df_1h = self._fetch_futures_1h_candles(symbol, limit=(limit * 2) + 10)
            df_2h = self._aggregate_2h_from_1h(df_1h, limit=limit)
            log.info(f"Built {len(df_2h)} closed 2h candles for {symbol} from 1h data")
            return df_2h

        raise ValueError("This bot only supports 1h and 2h timeframes.")

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
