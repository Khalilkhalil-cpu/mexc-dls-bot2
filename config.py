import os
from dotenv import load_dotenv

load_dotenv()

MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

SYMBOL = os.getenv("SYMBOL", "BTC/USDT:USDT")

TIMEFRAMES = ["1h", "2h"]

RISK_REWARD = 3.0
BREAK_EVEN_R = 0.82

TESTNET = os.getenv("TESTNET", "false").lower() == "true"
