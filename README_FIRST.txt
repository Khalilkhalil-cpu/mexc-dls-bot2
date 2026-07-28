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
