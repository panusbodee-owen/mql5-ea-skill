# Reading list → what this skill takes from each

Summaries are paraphrased ideas, not quotations. Buy/read the books for the full treatment.

| Book | Author | Ideas used in this skill |
|---|---|---|
| Expert Advisor Programming for MetaTrader 5 | Andrew R. Young | EA structure (OnInit/OnTick/OnDeinit), CTrade-style order wrappers, position checks by magic number, new-bar detection, trailing stops, input organisation |
| MQL5 Programming for Traders (free, mql5.com) | Stanislav Korotky / MetaQuotes | Indicator handles + CopyBuffer, netting vs hedging accounts, trade retcodes, OnTradeTransaction, tester specifics, symbol properties (tick value/size, volume step, stops/freeze level) |
| Way of the Turtle | Curtis Faith | Channel (Donchian) breakouts, volatility-based ("N"/ATR) position sizing, unit limits, following rules mechanically |
| Trade Your Way to Financial Freedom | Van K. Tharp | R-multiples, expectancy, position sizing as the main driver of results, system quality measured by expectancy/variability (SQN idea) |
| Building Winning Algorithmic Trading Systems | Kevin J. Davey | Idea → backtest → walk-forward → Monte Carlo → incubation (demo) → live; reject most ideas early; realistic costs |
| The Evaluation and Optimization of Trading Strategies | Robert Pardo | Walk-forward analysis, parameter robustness (stable regions instead of single best values), enough trades/degrees of freedom |
| Algorithmic Trading: Winning Strategies and Their Rationale | Ernest P. Chan | Mean reversion vs momentum regimes, testing stationarity/mean reversion before trading it, pitfalls of backtests (look-ahead, survivorship) |
| Quantitative Trading | Ernest P. Chan | Backtest hygiene, transaction cost modelling, Kelly-based sizing (and why fractional Kelly) |
| Trading Systems and Methods | Perry J. Kaufman | Catalogue of trend/mean-reversion/volatility methods, filters, adaptive indicators, system testing |
| Advances in Financial Machine Learning | Marcos López de Prado | Backtest overfitting: many trials inflate results; prefer fewer, economically motivated parameters |

Use: cite the idea + book when explaining a design choice ("ATR-based sizing — Turtle/Faith"), never paste book text.
