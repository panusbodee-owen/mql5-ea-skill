# Risk & testing

## Position sizing (Tharp, Faith, Chan)
- Risk per trade = equity × risk% (typical 0.25–1%; >2% rarely survives drawdowns).
- Lots = risk money ÷ (stop distance ÷ tick size × tick value), rounded **down** to volume step.
- 1R = money risked on a trade; judge systems by expectancy in R and its spread (SQN idea), not win rate.
- Kelly fraction maximises growth only with exact edge estimates; use a fraction (¼–½) or fixed % instead.
- Portfolio caps: max total open risk (e.g. 3–5%), correlated symbols count as one bet, daily/weekly loss stop.
- Prop-firm rules (daily loss, max DD) → set `InpMaxDailyLossPct` below the firm limit and test with Monte Carlo DD.

## Strategy Tester settings
- Model: **Every tick based on real ticks** for final tests (1-minute OHLC only for quick screening).
- Realistic spread (or real tick spread), commission, swap; test the broker you will trade.
- Deposit/leverage like live; check both netting and hedging if the EA may run on either.
- Visual mode once to confirm entries/exits match the rules.

## Validation pipeline (Davey, Pardo, López de Prado)
1. **Idea check** — simple rules, few parameters, an economic reason.
2. **In-sample** — rough parameters; reject if not profitable across a broad range.
3. **Robustness** — neighbouring parameter values give similar results (plateau, not a spike); test 2–3 related symbols/timeframes.
4. **Out-of-sample** — untouched period ≥ 30% of data; similar expectancy/DD.
5. **Walk-forward** — rolling optimise→test windows; MT5 tester "Forward" setting gives a simple split.
6. **Monte Carlo** — `analyze_trades.py`: 95th-pct drawdown, 5th-pct profit, P(ruin).
7. **Incubation** — demo/small live for weeks; compare live vs backtest per trade.
8. **Live with kill criteria** — stop if drawdown exceeds MC 95th percentile or expectancy turns negative over N trades.

## Red flags
- < 100 trades, profit factor > 3 with high win rate, equity curve too smooth, results collapse with +1 spread point, best parameters at the edge of the range, many optimised parameters.
