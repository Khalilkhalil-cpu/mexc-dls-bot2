import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    mexc_api_key: str = os.getenv("MEXC_API_KEY", "")
    mexc_secret_key: str = os.getenv("MEXC_SECRET_KEY", "")
    symbol: str = os.getenv("SYMBOL", "BTC/USDT:USDT")
    timeframes: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv("TIMEFRAMES", "1h,2h").split(",") if x.strip()
    )
    risk_percent: float = _float("RISK_PERCENT", 5.0)
    risk_reward: float = _float("RISK_REWARD", 3.0)
    break_even_r: float = _float("BREAK_EVEN_R", 0.82)
    leverage: int = _int("LEVERAGE", 1)
    dry_run: bool = _bool("DRY_RUN", True)
    poll_seconds: int = _int("POLL_SECONDS", 60)


settings = Settings()

if any(tf not in {"1h", "2h"} for tf in settings.timeframes):
    raise ValueError("This DLS bot only supports TIMEFRAMES=1h,2h")
