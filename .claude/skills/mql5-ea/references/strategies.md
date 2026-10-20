# Useful strategy archetypes ("ท่า") and when they fail

The first four are built into the single EA from `scripts/scaffold_ea.py` (select with `InpStrategy`); others are added as extra options in that same EA. All need testing per symbol/timeframe — none is profitable by default.

| Archetype | Entry | Exit | Filters that usually help | Fails when | Source idea |
|---|---|---|---|---|---|
| MA crossover trend (`ma_cross`) | Fast MA crosses slow MA on closed bar | Opposite cross / ATR trail | ADX above threshold, higher-TF trend agreement | Sideways markets (whipsaw); many small losses, few big wins | Kaufman; Young (implementation) |
| Channel breakout (`donchian`) | Close above N-bar high / below N-bar low | M-bar opposite channel (M < N) | Skip after a winning breakout (Turtle variant), volatility floor | Range-bound periods; false breakouts around news | Faith (Turtles) |
| Mean reversion with trend filter (`bb_reversion`) | Close outside Bollinger band + RSI extreme, only with long-term trend | Back to middle band; ATR stop | Trade only in mean-reverting regimes; avoid around news | Strong trends ("band walking"); regime change | Chan (mean reversion) |
| Session range breakout (`session_breakout`) | First close outside the Asian/overnight range after it ends | End-of-day close; ATR stop | Minimum/maximum range width, weekday filter | Low-volatility days; broker server-time differences | Common intraday practice |
| Volatility contraction breakout | Breakout after narrow range (e.g. NR7, low ATR percentile) | Trail / time stop | Trend filter | Fake breakouts in quiet markets | Kaufman |
| Pullback in trend | Trend by long MA; enter on RSI/stochastic pullback | Prior swing / ATR multiple | Higher-TF trend, avoid late-trend | Trend reversals | Kaufman; Davey |
| Time-of-day / calendar effects | Fixed time entries | Time exit | Verify effect persists out-of-sample | Effect decays; spread at rollover | Davey (idea testing) |

## Building blocks that improve almost any EA
- ATR-based stop and position size (constant risk per trade).
- Trade on closed bars; one decision per bar.
- Spread filter and avoidance of rollover hour (wide spreads).
- Daily loss limit and max open risk across EAs.
- Time exit for trades that go nowhere.

## Anti-patterns (refuse or warn strongly)
- **Martingale / lot doubling after losses** — expectancy unchanged, risk of ruin approaches certainty.
- **Grid without hard cap and stop** — same as martingale in disguise.
- **No stop loss / "never close at a loss"**.
- **Optimising many parameters on one period** and trading the single best set.
- **Hiding risk with tiny TP / huge SL** (high win rate, rare catastrophic loss).
- **Signals on the forming bar** (looks great in "open prices only", fails live).
