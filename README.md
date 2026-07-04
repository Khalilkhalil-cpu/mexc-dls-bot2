# MEXC DLS Bot

Automated MEXC Futures bot for Khalil's DLS strategy.

## Strategy Rules

Only checks the `1h` and `2h` timeframes.

### BUY DLS
1. Candle 1 can be any candle.
2. Candle 2 takes the high of Candle 1.
3. Candle 2 closes below Candle 1 high.
4. Candle 3 takes the low of Candle 1.
5. Candle 3 closes above Candle 2 body.
6. Bot buys after Candle 3 closes.
7. Stop loss below Candle 3.
8. Take profit = 3R.
9. Move stop loss to break-even at 0.82R.

### SELL DLS
1. Candle 1 can be any candle.
2. Candle 2 takes the low of Candle 1.
3. Candle 2 closes above Candle 1 low.
4. Candle 3 takes the high of Candle 1.
5. Candle 3 closes below Candle 2 body.
6. Bot sells after Candle 3 closes.
7. Stop loss above Candle 3.
8. Take profit = 3R.
9. Move stop loss to break-even at 0.82R.

## Important Safety Note

The bot starts with `DRY_RUN=true`. This means it logs trades but does not place real orders.
Only change `DRY_RUN=false` after checking logs and testing with a small account/position.

Trading crypto futures is high risk. Use your own judgement.

## Railway Variables

In Railway, open your project, then go to **Variables** and add:

```env
MEXC_API_KEY=your_key
MEXC_SECRET_KEY=your_secret
SYMBOL=BTC/USDT:USDT
TIMEFRAMES=1h,2h
RISK_PERCENT=5
RISK_REWARD=3
BREAK_EVEN_R=0.82
LEVERAGE=1
DRY_RUN=true
POLL_SECONDS=60
```

## How to Upload to GitHub

1. Create a GitHub repository called `mexc-dls-bot`.
2. Upload all files in this folder.
3. Do not upload a `.env` file.
4. Connect the GitHub repository to Railway.
5. Railway should install `requirements.txt` and run `python main.py` from `railway.json`.

## How to Go Live

1. Confirm the bot is running in Railway logs.
2. Confirm it says `DryRun=True`.
3. Watch the logs for signals.
4. When you are ready for live trading, set Railway variable:

```env
DRY_RUN=false
```

5. Start with very small risk first.
