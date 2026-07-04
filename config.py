import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str):
    return tuple(x.strip() for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    mexc_api_key: str = os.getenv("MEXC_API_KEY", "")
    mexc_secret_key: str = os.getenv("MEXC_SECRET_KEY", "")

    symbols: tuple = _split_csv(
        os.getenv("SYMBOLS", os.getenv("SYMBOL", "BTC/USDT:USDT"))
    )

    timeframes: tuple = _split_csv(os.getenv("TIMEFRAMES", "1h,2h"))

    risk_percent: float = float(os.getenv("RISK_PERCENT", "5"))
    risk_reward: float = float(os.getenv("RISK_REWARD", "3"))
    break_even_r: float = float(os.getenv("BREAK_EVEN_R", "0.82"))

    # MEXC futures settings
    leverage: int = int(os.getenv("LEVERAGE", "50"))
    margin_mode: str = os.getenv("MARGIN_MODE", "isolated").lower()

    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    check_interval_seconds: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))


settings = Settings()
