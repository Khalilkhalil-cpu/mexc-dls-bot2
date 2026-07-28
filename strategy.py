from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import Settings


@dataclass(frozen=True)
class Signal:
    signal_id: str
    candidate_id: str
    symbol: str
    side: str
    swing_start_time: pd.Timestamp
    swing_end_time: pd.Timestamp
    confirmation_time: pd.Timestamp
    swing_start: float
    swing_end: float
    zone_low: float
    zone_high: float
    liquidity_price: float
    structure_break_price: float
    entry_reference: float
    stop_loss: float
    take_profit: float
    break_even_price: float
    score: int


def resample_to_1h(df15: pd.DataFrame) -> pd.DataFrame:
    out = df15.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    counts = df15["close"].resample("1h", label="left", closed="left").count()
    return out[counts == 4].dropna()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for period in (50, 100, 200):
        out[f"ema{period}"] = out["close"].ewm(span=period, adjust=False).mean()
    prev = out["close"].shift(1)
    tr = pd.concat(
        [(out["high"] - out["low"]), (out["high"] - prev).abs(), (out["low"] - prev).abs()], axis=1
    ).max(axis=1)
    out["atr14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return out


def trend_side(row: pd.Series, sep_bps: float) -> Optional[str]:
    if any(pd.isna(row.get(x)) for x in ("ema50", "ema100", "ema200", "close")):
        return None
    sep = sep_bps / 10_000.0
    buy = (
        row.close > row.ema50 > row.ema100 > row.ema200
        and (row.ema50 - row.ema100) / row.close >= sep
        and (row.ema100 - row.ema200) / row.close >= sep
    )
    sell = (
        row.close < row.ema50 < row.ema100 < row.ema200
        and (row.ema100 - row.ema50) / row.close >= sep
        and (row.ema200 - row.ema100) / row.close >= sep
    )
    return "buy" if buy else "sell" if sell else None


def confirmed_pivots(df: pd.DataFrame, left: int, right: int) -> list[dict]:
    pivots: list[dict] = []
    for i in range(left, len(df) - right):
        hi = float(df.high.iloc[i]); lo = float(df.low.iloc[i])
        if hi > float(df.high.iloc[i-left:i].max()) and hi >= float(df.high.iloc[i+1:i+right+1].max()):
            pivots.append({"kind":"high", "time":df.index[i], "confirm_time":df.index[i+right], "price":hi, "i":i})
        if lo < float(df.low.iloc[i-left:i].min()) and lo <= float(df.low.iloc[i+1:i+right+1].min()):
            pivots.append({"kind":"low", "time":df.index[i], "confirm_time":df.index[i+right], "price":lo, "i":i})
    return sorted(pivots, key=lambda x:(x["confirm_time"], x["time"], x["kind"]))


def compress_same_kind(pivots: list[dict]) -> list[dict]:
    out: list[dict] = []
    for p in pivots:
        if not out or out[-1]["kind"] != p["kind"]:
            out.append(p.copy()); continue
        better = p["price"] > out[-1]["price"] if p["kind"] == "high" else p["price"] < out[-1]["price"]
        if better:
            out[-1] = p.copy()
    return out


def main_h1_swings(h1: pd.DataFrame, cfg: Settings) -> list[dict]:
    raw = compress_same_kind(confirmed_pivots(h1, cfg.h1_pivot_left, cfg.h1_pivot_right))
    accepted: list[dict] = []
    for p in raw:
        if not accepted:
            accepted.append(p); continue
        prev = accepted[-1]
        if p["kind"] == prev["kind"]:
            continue
        atr = float(h1.loc[p["confirm_time"], "atr14"])
        distance = abs(p["price"] - prev["price"])
        if not np.isfinite(atr) or distance < cfg.main_swing_min_atr * atr:
            continue
        accepted.append(p)

    swings: list[dict] = []
    for a, b in zip(accepted, accepted[1:]):
        if a["kind"] == "low" and b["kind"] == "high" and b["price"] > a["price"]:
            side = "buy"
        elif a["kind"] == "high" and b["kind"] == "low" and b["price"] < a["price"]:
            side = "sell"
        else:
            continue
        available = max(a["confirm_time"], b["confirm_time"])
        if available not in h1.index or trend_side(h1.loc[available], cfg.ema_separation_bps) != side:
            continue
        distance = abs(b["price"] - a["price"])
        if side == "buy":
            zone_low = b["price"] - cfg.fib_deep * distance
            zone_high = b["price"] - cfg.fib_shallow * distance
        else:
            zone_low = b["price"] + cfg.fib_shallow * distance
            zone_high = b["price"] + cfg.fib_deep * distance
        swings.append({
            "side":side, "start":a, "end":b, "available_time":available,
            "zone_low":float(zone_low), "zone_high":float(zone_high), "distance":float(distance),
        })
    return swings


def _touches(row: pd.Series, low: float, high: float) -> bool:
    return float(row.low) <= high and float(row.high) >= low


def _score_candidate(side: str, swing: dict, liq: dict, break_row: pd.Series, entry: float, stop: float, h1row: pd.Series, cfg: Settings) -> int:
    score = 0
    score += 25  # Main external H1 swing already validated.
    score += 20  # EMA trend alignment already validated.
    depth = (swing["end"]["price"] - entry) / swing["distance"] if side == "buy" else (entry - swing["end"]["price"]) / swing["distance"]
    if 0.618 <= depth <= 0.705: score += 20
    elif cfg.fib_shallow <= depth <= cfg.fib_deep: score += 12
    wick = (min(float(break_row.open), float(break_row.close)) - float(break_row.low)) if side == "buy" else (float(break_row.high) - max(float(break_row.open), float(break_row.close)))
    body = abs(float(break_row.close) - float(break_row.open))
    if wick > body: score += 10
    risk_pct = abs(entry - stop) / entry
    if cfg.min_stop_pct <= risk_pct <= cfg.preferred_max_stop_pct: score += 10
    if side == "buy" and float(h1row.ema50) > float(h1row.ema100) > float(h1row.ema200): score += 10
    if side == "sell" and float(h1row.ema50) < float(h1row.ema100) < float(h1row.ema200): score += 10
    if abs(entry - liq["price"]) / entry >= cfg.minimum_sweep_pct: score += 5
    return min(score, 100)


def find_new_signal(symbol: str, df15: pd.DataFrame, cfg: Settings, already_used: set[str]) -> tuple[Optional[Signal], dict]:
    context: dict = {"symbol":symbol, "status":"NO_SETUP"}
    if len(df15) < 900:
        return None, context
    h1 = add_indicators(resample_to_1h(df15))
    m15 = add_indicators(df15)
    swings = main_h1_swings(h1, cfg)
    m15_pivots = compress_same_kind(confirmed_pivots(m15, cfg.m15_pivot_left, cfg.m15_pivot_right))
    if not swings or not m15_pivots:
        return None, context

    latest_i = len(m15) - 1
    latest_time = m15.index[latest_i]
    for swing in reversed(swings):
        signal_id = f"{symbol}|{swing['side']}|{swing['start']['time'].isoformat()}|{swing['end']['time'].isoformat()}"
        if signal_id in already_used:
            continue
        side = swing["side"]
        start_i = int(m15.index.searchsorted(swing["available_time"], side="left"))
        piv = [p for p in m15_pivots if p["confirm_time"] >= swing["available_time"]]
        if len(piv) < 2:
            continue
        zone_touch = None
        swept = None
        break_level = None
        for i in range(start_i, len(m15)):
            row = m15.iloc[i]; ts=m15.index[i]; h1_time=ts.floor("1h")
            if h1_time not in h1.index or trend_side(h1.loc[h1_time], cfg.ema_separation_bps) != side:
                continue
            if side == "buy" and float(row.low) <= swing["start"]["price"]: break
            if side == "sell" and float(row.high) >= swing["start"]["price"]: break
            if zone_touch is None:
                if _touches(row, swing["zone_low"], swing["zone_high"]): zone_touch=i
                continue
            if i-zone_touch > cfg.max_confirmation_bars_15m: break
            eligible = [p for p in piv if p["confirm_time"] <= ts and p["i"] < i]
            if swept is None:
                lows=[p for p in eligible if p["kind"]=="low"]
                highs=[p for p in eligible if p["kind"]=="high"]
                if side=="buy" and lows:
                    liq=lows[-1]
                    if float(row.low) < liq["price"] and float(row.close) > liq["price"]:
                        prior_highs=[p for p in highs if p["time"] > liq["time"]]
                        if prior_highs: swept=liq; break_level=prior_highs[-1]["price"]
                elif side=="sell" and highs:
                    liq=highs[-1]
                    if float(row.high) > liq["price"] and float(row.close) < liq["price"]:
                        prior_lows=[p for p in lows if p["time"] > liq["time"]]
                        if prior_lows: swept=liq; break_level=prior_lows[-1]["price"]
                continue
            confirmed = float(row.close) > break_level if side=="buy" else float(row.close) < break_level
            if not confirmed:
                continue
            if i != latest_i or ts != latest_time:
                break
            entry=float(row.close); buffer=entry*cfg.stop_buffer_bps/10_000
            stop=(swept["price"]-buffer) if side=="buy" else (swept["price"]+buffer)
            risk=abs(entry-stop); risk_pct=risk/entry
            if risk <= 0 or not (cfg.min_stop_pct <= risk_pct <= cfg.max_stop_pct):
                return None, {"symbol":symbol,"status":"REJECT_STOP_DISTANCE","risk_pct":risk_pct}
            tp=entry+cfg.reward_risk*risk if side=="buy" else entry-cfg.reward_risk*risk
            be=entry+cfg.break_even_at_r*risk if side=="buy" else entry-cfg.break_even_at_r*risk
            score=_score_candidate(side,swing,swept,row,entry,stop,h1.loc[h1_time],cfg)
            candidate_id=f"{signal_id}|{swept['time'].isoformat()}|{ts.isoformat()}"
            context={
                "symbol":symbol,"status":"CANDIDATE","trend":side,"candidate_id":candidate_id,
                "h1_swing":{"start_time":swing['start']['time'].isoformat(),"start_price":swing['start']['price'],"end_time":swing['end']['time'].isoformat(),"end_price":swing['end']['price']},
                "fib_zone":[swing['zone_low'],swing['zone_high']],"m15_liquidity":{"time":swept['time'].isoformat(),"price":swept['price']},
                "structure_break_price":break_level,"entry":entry,"stop":stop,"target":tp,"score":score,
            }
            if score < cfg.minimum_candidate_score:
                context["status"]="REJECT_LOW_SCORE"
                return None, context
            return Signal(signal_id,candidate_id,symbol,side,swing['start']['time'],swing['end']['time'],ts,float(swing['start']['price']),float(swing['end']['price']),float(swing['zone_low']),float(swing['zone_high']),float(swept['price']),float(break_level),entry,float(stop),float(tp),float(be),score), context
    return None, context
