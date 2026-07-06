# Master ICT + DLS + SPM Bot — LIVE 24H Version

Includes:
- ICT engine
- DLS Type 1
- DLS Type 2
- Extended DLS with inside candles
- SPM engine
- Weekly bias
- Daily SPM fallback
- 4H SPM alignment filter
- Risk 3% of account
- 3R target
- Break-even at 0.82R
- 24h trading mode

Defaults:
```env
DRY_RUN=false
USE_LIVE_ORDERS=true
TRADING_SESSIONS=ALL
RISK_PER_TRADE=0.03
RR_TARGET=3
RISK_REWARD=3
LEVERAGE=50
MARGIN_MODE=isolated
```

Railway uses:
```text
worker: python main.py
```
