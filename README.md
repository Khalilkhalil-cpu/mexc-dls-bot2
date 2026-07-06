# Master ICT + DLS Bot v1

Combined bot with:
- ICT strategy
- DLS Type 1
- DLS Type 2 with lower-timeframe EC + SPM confirmation
- Weekly bias engine
- Daily SPM fallback
- 4H SPM alignment filter
- 2% account risk sizing by default
- Win/loss statistics in `logs/stats.json`
- Trade history in `logs/trades.csv`

## Railway variables

```env
MEXC_API_KEY=your_key
MEXC_SECRET=your_secret
DRY_RUN=false
USE_LIVE_ORDERS=true
RISK_PER_TRADE=0.02
SIZING_MODE=risk_percent
LEVERAGE=50
MARGIN_MODE=isolated
MAX_OPEN_POSITIONS=2
MAX_NEW_TRADES_PER_CYCLE=1
TRADING_SESSIONS=NEWYORK
LOOP_SECONDS=120
MAX_SYMBOLS_PER_CYCLE=8
REQUEST_DELAY_SECONDS=0.5
SYMBOL_DELAY_SECONDS=1.0
RATE_LIMIT_BACKOFF_SECONDS=60
```

## Important
This is live-ready, but test with small balance first. Risk is set to 2% by default as requested.
