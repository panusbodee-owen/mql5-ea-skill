# mql5-ea — Claude Skill for MetaTrader 5 Expert Advisors

![Demo: generate the single EA, lint it, lint a legacy MQL4-style EA, analyse trades](docs/demo.gif)

Builds **one** safe MQL5 Expert Advisor that contains well-known strategy archetypes (choose with the `InpStrategy` input), reviews/ports existing code, and evaluates results — with the rules drawn from established EA and trading-system books (see [references/books.md](.claude/skills/mql5-ea/references/books.md); ideas are paraphrased, not copied).

| Task | How |
|---|---|
| One EA | `scripts/scaffold_ea.py` → a single self-contained `.mq5` with 4 selectable strategies: MA crossover + ADX, Donchian (Turtle) breakout, Bollinger + RSI reversion with trend filter, session range breakout. Only the selected strategy creates indicator handles. Re-running refuses to create a second EA; new ideas are added as extra options in the same file |
| Safety core in every EA | Risk-% sizing from ATR stop (volume rounded down, skip below min lot), margin check, spread & time-window filters, daily loss limit, ATR trailing stop, magic-number isolation, closed-bar signals, retcode checks, handle release |
| Review / port MQL4 | `scripts/check_mq5.py` → MQL4 leftovers (`start()`, `OrderSelect(...MODE_TRADES)`, `Close[]`, `Ask`, 7-arg `iMA`…), handles created in `OnTick`, unchecked trades, missing stop loss, fixed lots, martingale |
| Small accounts & goals | EA inputs: `InpLotMode` (risk % or **fixed lot, e.g. 0.01**), `InpMaxRiskCapPct` (skip trades that would risk too much), `InpEquityTarget` (close & stop at the goal so profit can be withdrawn), `InpMaxDrawdownPct` (hard stop from peak, default 50%), `InpReduceRiskDDPct` (halve size in drawdown). `scripts/goal_planner.py` turns a target such as $10 → $1,000 into P(goal), P(lost half), P(stuck) and median drawdown per risk level — from win rate/RR or bootstrapped from your real trade history, including the broker minimum-lot constraint |
| Daily plan | `InpLotMode = LOT_TIERS` with `InpLotTiers` (equity:lot steps — compounding, not martingale), `InpDailyTargetPoints` / `InpDailyTargetMoney` (stop for the day at target), `InpDailyLossMoney` (stop for the day after losing e.g. $5), `InpUseLocalTime` + GMT offsets (trade 12:00–22:00 Thai time). Ready-made preset for a gold daily plan in `references/small-account.md` |
| Your own method | `references/small-account.md`: collect your rules + MT5 history → measure with `analyze_trades.py` → estimate repeatability with `goal_planner.py --trades` → encode as a new strategy option in the same EA → confirm the tester reproduces your trades |
| Evaluate results | `scripts/analyze_trades.py` → profit factor, win rate, payoff, expectancy ($ and R), SQN, max DD, recovery factor, losing streak + Monte Carlo (95th-pct DD, 5th-pct profit, P(ruin)) and red flags; optional Excel |
| Knowledge | `references/ea-patterns.md` (correct API use), `strategies.md` (archetypes, when they fail, anti-patterns), `risk-and-testing.md` (sizing, tester settings, walk-forward, incubation), `small-account.md` (cent accounts, min-lot math, goal setting, prop accounts) |

```bash
python3 .claude/skills/mql5-ea/scripts/scaffold_ea.py MultiStrategyEA --out MQL5/Experts
python3 .claude/skills/mql5-ea/scripts/check_mq5.py MQL5/Experts/MultiStrategyEA.mq5
python3 .claude/skills/mql5-ea/scripts/analyze_trades.py trades.csv --initial 10000 --risk 100 --xlsx report.xlsx
python3 .claude/skills/mql5-ea/scripts/goal_planner.py --capital 10 --target 1000 --months 3 --trades-per-month 60 --trades history.csv --risk-usd 3 --min-risk-usd 1
```
Generated example: [`examples/MultiStrategyEA.mq5`](examples/MultiStrategyEA.mq5).

## Installation
**claude.ai / Claude Desktop** — zip the `mql5-ea` folder (zip must contain `mql5-ea/SKILL.md`), Settings → Capabilities → Skills → Upload skill.

**Claude Code**
```bash
git clone https://github.com/panusbodee-owen/mql5-ea-skill.git
mkdir -p ~/.claude/skills && cp -r mql5-ea-skill/.claude/skills/mql5-ea ~/.claude/skills/
```
Python 3; `openpyxl` only for `--xlsx`.

## Status — read before trading
- The generated EA was checked by the linter and for structure, but **not compiled here** (no MetaEditor in the build environment). Compile in MetaEditor (F7) and fix any compiler messages first.
- Demo GIF trade figures come from **synthetic** data, not a real strategy.
- No strategy here is profitable by default. Backtest with "Every tick based on real ticks", validate out-of-sample, Monte Carlo, then demo before live money. **Not financial advice.**
