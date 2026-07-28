MEXC AI EXTERNAL SWING ENGINE LIVE BOT v2.02

IMPORTANT v2.02 CHANGE
- Leverage is NOT configured for all symbols at startup.
- This prevents MEXC code 510: Requests are too frequent.
- After a setup passes the strategy and AI review, the bot configures the approved symbol only.
- It configures both BUY and SELL isolated leverage before sending the entry.
- Rate-limit errors are retried with exponential backoff.
- If leverage cannot be confirmed, the entry is cancelled and NO live order is sent.

Railway variables:
LIVE_TRADING=true
POSITION_NOTIONAL_USDT=200
LEVERAGE=40
MARGIN_MODE=isolated
LEVERAGE_RETRY_ATTEMPTS=5
LEVERAGE_RETRY_DELAY_SECONDS=2.0
STATE_FILE=/data/state.json

Keep the Railway persistent volume mounted at /data because stop-loss, take-profit and break-even management use the state file.

MEXC AI EXTERNAL SWING ENGINE LIVE BOT v2.00

WHAT CHANGED
- 1H pivots require left/right confirmation and become available only after confirmation.
- Consecutive same-side pivots are compressed to the most extreme price.
- Opposite pivots smaller than MAIN_SWING_MIN_ATR are ignored as inside swings.
- A 1H swing is accepted only when aligned with EMA50/100/200 direction.
- Fibonacci is drawn only on accepted external 1H impulses.
- 15m entry requires: Fibonacci touch, confirmed 15m liquidity sweep, then a later structure break.
- Candidate score must meet MINIMUM_CANDIDATE_SCORE.
- AI can only APPROVE, REJECT or WAIT. It cannot change prices.
- Missing API, AI failure, wrong candidate ID or low confidence = NO TRADE.
- Bot manages accepted positions locally using persistent state.

START
1. Copy .env.example to .env and enter keys.
2. Keep LIVE_TRADING=false for dry-run testing.
3. Run START_WINDOWS.bat.
4. Review AI REVIEW and APPROVED SIGNAL logs.
5. Only after testing, change LIVE_TRADING=true.

IMPORTANT
Stops and take profit remain software-managed by this bot. The process must stay online.
AI review does not guarantee profit. Verify this version with backtesting and dry-run logs before real funds.


v2.01 MEXC LEVERAGE FIX
- Configures leverage separately for LONG and SHORT with openType/positionType.
- Passes the same MEXC position parameters on entries and closes.
- LIVE mode fails closed if leverage cannot be confirmed.
- LEVERAGE and POSITION_NOTIONAL_USDT remain editable environment variables.
