from dataclasses import dataclass
from typing import Literal, Optional
import pandas as pd

Side = Literal["buy", "sell"]


@dataclass
class Signal:
    side: Side
    timeframe: str
    entry: float
    stop_loss: float
    take_profit: float
    break_even_price: float
    risk_per_unit: float
    candle3_time: int


def candle_body_high(row) -> float:
    return max(float(row["open"]), float(row["close"]))


def candle_body_low(row) -> float:
    return min(float(row["open"]), float(row["close"]))


def detect_dls_signal(
    df: pd.DataFrame,
    timeframe: str,
    risk_reward: float = 3.0,
    break_even_r: float = 0.82,
) -> Optional[Signal]:
    """
    DLS strategy using ONLY your rules.

    BUY setup:
    1. Candle 1 can be any candle.
    2. Candle 2 must take/sweep Candle 1 high.
    3. Candle 2 must close below Candle 1 high.
    4. Candle 3 must take/sweep Candle 1 low.
    5. Candle 3 must close above Candle 2 body.
       - Candle 3 does NOT need to close inside Candle 1 range.
       - It is valid even if Candle 3 closes outside the DLS range,
         as long as it closes above Candle 2 body.

    SELL setup:
    1. Candle 1 can be any candle.
    2. Candle 2 must take/sweep Candle 1 low.
    3. Candle 2 must close above Candle 1 low.
    4. Candle 3 must take/sweep Candle 1 high.
    5. Candle 3 must close below Candle 2 body.
       - Candle 3 does NOT need to close inside Candle 1 range.
       - It is valid even if Candle 3 closes outside the DLS range,
         as long as it closes below Candle 2 body.

    The function only checks the last 3 CLOSED candles.
    """
    if len(df) < 3:
        return None

    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c3 = df.iloc[-1]

    c1_high = float(c1["high"])
    c1_low = float(c1["low"])

    c2_high = float(c2["high"])
    c2_low = float(c2["low"])
    c2_close = float(c2["close"])

    c3_high = float(c3["high"])
    c3_low = float(c3["low"])
    c3_close = float(c3["close"])

    c2_body_top = candle_body_high(c2)
    c2_body_bottom = candle_body_low(c2)

    entry = c3_close
    candle3_time = int(c3["timestamp"])

    # BUY DLS:
    # C2 sweeps C1 high and closes weak below C1 high.
    # C3 sweeps C1 low and closes above the TOP of C2 body.
    buy_ok = (
        c2_high > c1_high and
        c2_close < c1_high and
        c3_low < c1_low and
        c3_close > c2_body_top
    )

    if buy_ok:
        stop = c3_low
        risk = entry - stop
        if risk <= 0:
            return None

        return Signal(
            side="buy",
            timeframe=timeframe,
            entry=entry,
            stop_loss=stop,
            take_profit=entry + (risk * risk_reward),
            break_even_price=entry + (risk * break_even_r),
            risk_per_unit=risk,
            candle3_time=candle3_time,
        )

    # SELL DLS:
    # C2 sweeps C1 low and closes weak above C1 low.
    # C3 sweeps C1 high and closes below the BOTTOM of C2 body.
    sell_ok = (
        c2_low < c1_low and
        c2_close > c1_low and
        c3_high > c1_high and
        c3_close < c2_body_bottom
    )

    if sell_ok:
        stop = c3_high
        risk = stop - entry
        if risk <= 0:
            return None

        return Signal(
            side="sell",
            timeframe=timeframe,
            entry=entry,
            stop_loss=stop,
            take_profit=entry - (risk * risk_reward),
            break_even_price=entry - (risk * break_even_r),
            risk_per_unit=risk,
            candle3_time=candle3_time,
        )

    return None
