from __future__ import annotations

import logging
from typing import Optional

import ccxt
import pandas as pd

from config import Settings

log = logging.getLogger("mexc_client")


class MexcClient:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.exchange = ccxt.mexc({
            "apiKey": cfg.api_key,
            "secret": cfg.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "defaultSubType": "linear",
                "adjustForTimeDifference": True,
            },
        })
        self.markets = self.exchange.load_markets()

    def validate_symbols(self) -> None:
        missing = []
        for symbol in self.cfg.symbols:
            market = self.markets.get(symbol)
            if not market or not market.get("swap") or not market.get("linear"):
                missing.append(symbol)
        if missing:
            raise ValueError(f"Unavailable USDT perpetual symbols: {', '.join(missing)}")

    def _position_params(self, side: str) -> dict:
        # MEXC contract API: openType 1=isolated, 2=cross; positionType 1=long, 2=short.
        open_type = 1 if self.cfg.margin_mode == "isolated" else 2
        position_type = 1 if side == "buy" else 2
        return {
            "openType": open_type,
            "positionType": position_type,
            "leverage": int(self.cfg.leverage),
        }

    @staticmethod
    def _benign_setup_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(x in text for x in (
            "not modified",
            "same leverage",
            "already",
            "no need to change",
        ))

    def configure_symbol(self, symbol: str) -> None:
        # MEXC keeps leverage separately for long and short positions. Configure both.
        errors = []
        for side in ("buy", "sell"):
            params = self._position_params(side)
            try:
                self.exchange.set_leverage(
                    int(self.cfg.leverage),
                    symbol,
                    {
                        "openType": params["openType"],
                        "positionType": params["positionType"],
                    },
                )
                log.info(
                    "LEVERAGE CONFIGURED | %s | side=%s | leverage=%sx | margin=%s",
                    symbol, side.upper(), self.cfg.leverage, self.cfg.margin_mode,
                )
            except Exception as exc:
                if self._benign_setup_error(exc):
                    log.info(
                        "LEVERAGE ALREADY SET | %s | side=%s | leverage=%sx | margin=%s",
                        symbol, side.upper(), self.cfg.leverage, self.cfg.margin_mode,
                    )
                else:
                    errors.append(f"{side}: {exc}")

        if errors:
            message = f"Unable to confirm leverage for {symbol}: " + " | ".join(errors)
            if self.cfg.live_trading:
                raise RuntimeError(message)
            log.warning(message)

    def fetch_closed_15m(self, symbol: str, limit: int) -> pd.DataFrame:
        rows = self.exchange.fetch_ohlcv(symbol, timeframe="15m", limit=limit)
        if not rows:
            raise RuntimeError(f"No 15m candles returned for {symbol}")
        df = pd.DataFrame(
            rows,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)

        # Remove the currently forming candle.
        now = pd.Timestamp.now(tz="UTC")
        current_open = now.floor("15min")
        return df[df.index < current_open]

    def ticker_price(self, symbol: str) -> float:
        ticker = self.exchange.fetch_ticker(symbol)
        for key in ("last", "mark", "close", "bid", "ask"):
            value = ticker.get(key)
            if value is not None:
                return float(value)
        raise RuntimeError(f"No usable ticker price for {symbol}")

    def amount_for_notional(self, symbol: str, notional_usdt: float, price: float) -> float:
        market = self.markets[symbol]
        contract_size = float(market.get("contractSize") or 1.0)
        raw_contracts = notional_usdt / (price * contract_size)
        amount = float(self.exchange.amount_to_precision(symbol, raw_contracts))
        minimum = ((market.get("limits") or {}).get("amount") or {}).get("min")
        if minimum is not None and amount < float(minimum):
            raise ValueError(
                f"{symbol} amount {amount} is below exchange minimum {minimum}. "
                f"Increase POSITION_NOTIONAL_USDT."
            )
        if amount <= 0:
            raise ValueError(f"Calculated amount for {symbol} is zero.")
        return amount

    def create_entry(self, symbol: str, side: str, amount: float) -> dict:
        order_side = "buy" if side == "buy" else "sell"
        params = self._position_params(side)
        return self.exchange.create_order(symbol, "market", order_side, amount, None, params)

    def close_position(self, symbol: str, side: str, amount: float) -> dict:
        close_side = "sell" if side == "buy" else "buy"
        params = self._position_params(side)
        params["reduceOnly"] = True
        return self.exchange.create_order(symbol, "market", close_side, amount, None, params)

    def fetch_positions(self) -> list[dict]:
        positions = self.exchange.fetch_positions(list(self.cfg.symbols))
        out = []
        for p in positions:
            contracts = float(p.get("contracts") or 0.0)
            if contracts <= 0:
                continue
            side = str(p.get("side") or "").lower()
            if side not in {"long", "short"}:
                continue
            out.append({
                "symbol": p.get("symbol"),
                "side": "buy" if side == "long" else "sell",
                "amount": contracts,
                "entry_price": float(p.get("entryPrice") or 0.0),
                "unrealized_pnl": float(p.get("unrealizedPnl") or 0.0),
            })
        return out

    def account_summary(self) -> tuple[float, float]:
        balance = self.exchange.fetch_balance({"type": "swap"})
        usdt = balance.get("USDT") or {}
        equity = float(usdt.get("total") or balance.get("total", {}).get("USDT") or 0.0)
        available = float(usdt.get("free") or balance.get("free", {}).get("USDT") or 0.0)
        return equity, available
