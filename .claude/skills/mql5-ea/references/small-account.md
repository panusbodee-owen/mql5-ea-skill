# Small accounts ($10–$100) and money goals

## The user's own method comes first
Small-account results come from the method, not from a generic template. When the user has a method that already worked:
1. **Collect the rules** — symbol, timeframe, session/hours, entry trigger, stop, target/exit, trades per day, lot (fixed 0.01?), what they do after a loss. Ask only for what is missing.
2. **Collect the evidence** — MT5 History → right-click → Report/Export, or Strategy Tester deals → CSV.
3. **Measure it** — `analyze_trades.py history.csv --initial <start>`: expectancy, PF, max DD, losing streak, Monte Carlo.
4. **Probability of repeating it** — `goal_planner.py --capital <start> --target <goal> --trades history.csv --risk-usd <typical $ loss per losing trade> --min-risk-usd <$ loss at 0.01 lot>`.
5. **Encode it in the same EA** as a new strategy option (`STRAT_<NAME>`), using `InpLotMode = LOT_FIXED` + `InpFixedLot = 0.01` if that is how it was traded.
6. **Verify the EA reproduces the manual results** in the Strategy Tester on the same period (trade-by-trade spot check) before any new period.
Respect a track record the user reports; still show the drawdown/streak numbers so the risk is a conscious choice.

## Facts that decide small-account outcomes
| Fact | Consequence |
|---|---|
| Min lot is usually 0.01 | On a $10–20 standard account one 0.01-lot loss can be 5–20% of equity. Size is fixed by the broker, not by % risk |
| Value per move differs by symbol | EURUSD 0.01 lot ≈ $0.10 per pip; XAUUSD 0.01 lot ≈ $1 per $1 move (verify with tick value) — gold grows (and blows) small accounts fastest |
| Cent accounts (USC) | Balance shown ×100, 0.01 lot ≈ 1/100 of the standard risk → real % sizing becomes possible from $10 |
| Compounding needs positive expectancy | Expectancy ≤ 0R cannot be fixed by lot size or targets; only by the method |
| Losing streaks are normal | 45% win rate → 8–10 losses in a row will happen over a few hundred trades; at 10–15% per loss that is account-ending |
| Spread/commission | A larger share of small targets; include `--cost-r` in the planner |

## EA inputs for small accounts
- `InpLotMode = LOT_FIXED`, `InpFixedLot = 0.01` — trade like the manual method.
- `InpMaxRiskCapPct` — skip setups whose stop would cost more than X% (e.g. 15). 0 = no cap.
- `InpMaxDrawdownPct` — hard stop from peak (default 50) so one bad week cannot take everything.
- `InpEquityTarget` — goal; EA closes and stops so profit can be withdrawn. Restart with `InpResetPeak = true` after deposits/withdrawals.
- `InpReduceRiskDDPct` — halve size during drawdowns.
- Daily loss limit (`InpMaxDailyLossPct`) — stops tilt-like sequences.

## Goal setting (use goal_planner output, not promises)
- Express the goal as required growth: e.g. $15 → $1,015 in 12 months = ×68 ≈ +42%/month.
- Report P(goal), P(lost half) and median drawdown for the user's actual edge, then let the user choose the risk level.
- Staircase plan: withdraw the starting capital once doubled; then trade "house money" with the same rules.
- Alternative path for small capital: prop/funded challenges (fee for access to larger capital; strict daily/total loss rules — set the EA's limits below them).

## Never
Martingale, averaging down without a hard cap, removing the stop loss to "give it room", or raising lot size to recover losses.
