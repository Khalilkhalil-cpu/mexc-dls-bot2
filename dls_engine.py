from __future__ import annotations
from typing import Optional, List
import pandas as pd
from models import Signal
from config import settings
from spm_engine import latest_spm, has_ec_before_spm


def body_high(row) -> float:
    return max(float(row["open"]), float(row["close"]))


def body_low(row) -> float:
    return min(float(row["open"]), float(row["close"]))


def _signal(symbol: str, side: str, timeframe: str, entry: float, stop: float, candle3_time, strategy: str, reason: str) -> Optional[Signal]:
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    target = entry + risk * settings.risk_reward if side == "buy" else entry - risk * settings.risk_reward
    be = entry + risk * settings.break_even_r if side == "buy" else entry - risk * settings.break_even_r
    sid = f"{symbol}|{strategy}|{timeframe}|{side}|{candle3_time}|{round(entry,8)}|{round(stop,8)}"
    return Signal(symbol=symbol, strategy=strategy, side=side, timeframe=timeframe, entry=entry, stop=stop, target=target, break_even_price=be, risk_per_unit=risk, signal_time=candle3_time, signal_id=sid, score=100, reason=reason)


def detect_dls_type1(symbol: str, df: pd.DataFrame, timeframe: str) -> Optional[Signal]:
    if len(df) < 3:
        return None
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    entry = float(c3.close)
    t = c3.datetime if "datetime" in df.columns else int(c3.timestamp)

    buy_ok = (
        float(c2.high) > float(c1.high) and
        float(c2.close) < float(c1.high) and
        float(c3.low) < float(c1.low) and
        float(c3.close) > body_high(c2)
    )
    if buy_ok:
        return _signal(symbol, "buy", timeframe, entry, float(c3.low), t, "DLS_TYPE1", "DLS Type 1 buy: C2 swept C1 high; C3 swept C1 low and closed above C2 body")

    sell_ok = (
        float(c2.low) < float(c1.low) and
        float(c2.close) > float(c1.low) and
        float(c3.high) > float(c1.high) and
        float(c3.close) < body_low(c2)
    )
    if sell_ok:
        return _signal(symbol, "sell", timeframe, entry, float(c3.high), t, "DLS_TYPE1", "DLS Type 1 sell: C2 swept C1 low; C3 swept C1 high and closed below C2 body")
    return None


def detect_dls_type2_candidate(df: pd.DataFrame, timeframe: str):
    """Return a Type 2 setup that needs lower-timeframe EC + SPM confirmation."""
    if len(df) < 3:
        return None
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    t = c3.datetime if "datetime" in df.columns else int(c3.timestamp)

    buy_ok = (
        float(c2.high) > float(c1.high) and
        float(c2.close) < float(c1.high) and
        float(c3.low) < float(c1.low) and
        float(c3.close) <= float(c2.open)  # did not close above Candle 2 open
    )
    if buy_ok:
        return {"side": "buy", "timeframe": timeframe, "c3_low": float(c3.low), "c3_high": float(c3.high), "candle3_time": t}

    sell_ok = (
        float(c2.low) < float(c1.low) and
        float(c2.close) > float(c1.low) and
        float(c3.high) > float(c1.high) and
        float(c3.close) >= float(c2.open)  # did not close below Candle 2 open
    )
    if sell_ok:
        return {"side": "sell", "timeframe": timeframe, "c3_low": float(c3.low), "c3_high": float(c3.high), "candle3_time": t}
    return None


def detect_dls_type2_confirmed(symbol: str, htf_df: pd.DataFrame, lower_df: pd.DataFrame, timeframe: str, lower_timeframe: str) -> Optional[Signal]:
    setup = detect_dls_type2_candidate(htf_df, timeframe)
    if not setup:
        return None
    spm = latest_spm(lower_df, lower_timeframe, side=setup["side"], only_after_time=setup["candle3_time"])
    if not spm:
        return None
    if not has_ec_before_spm(lower_df, spm):
        return None

    entry = float(spm.confirm_close)
    if setup["side"] == "buy":
        # Stop below both original DLS C3 low and lower-TF SPM C2 low.
        stop = min(float(setup["c3_low"]), float(spm.candle2_low))
    else:
        # Stop above both original DLS C3 high and lower-TF SPM C2 high.
        stop = max(float(setup["c3_high"]), float(spm.candle2_high))
    return _signal(symbol, setup["side"], timeframe, entry, stop, spm.confirm_time, "DLS_TYPE2", f"DLS Type 2 {setup['side']} on {timeframe}; EC + {lower_timeframe} SPM confirmed")


def detect_dls_signals(symbol: str, dfs: dict) -> List[Signal]:
    signals: List[Signal] = []
    if settings.enable_dls_type1:
        for tf in settings.dls_tf_list:
            if tf in dfs:
                sig = detect_dls_type1(symbol, dfs[tf], tf)
                if sig:
                    signals.append(sig)
    if settings.enable_dls_type2:
        if "1h" in dfs and "15m" in dfs:
            sig = detect_dls_type2_confirmed(symbol, dfs["1h"], dfs["15m"], "1h", "15m")
            if sig:
                signals.append(sig)
        if "2h" in dfs and "30m" in dfs:
            sig = detect_dls_type2_confirmed(symbol, dfs["2h"], dfs["30m"], "2h", "30m")
            if sig:
                signals.append(sig)
    return signals
