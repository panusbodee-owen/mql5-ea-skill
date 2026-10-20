# MQL5 EA patterns (correct API usage)

| Need | Do | Don't |
|---|---|---|
| Indicators | Create handle once in `OnInit` (`iMA`, `iATR`, `iBands`…), check `INVALID_HANDLE`, read with `CopyBuffer(h, buf, shift, count, arr)`, check returned count, `IndicatorRelease` in `OnDeinit` | MQL4 style `iMA(...,shift)` returning a value; creating handles in `OnTick` |
| Signals | Evaluate on closed bars (shift 1/2) once per new bar (`iTime(_Symbol,_Period,0)` changed) | Signals on the forming bar (repaints, tester/live mismatch) |
| Orders | `CTrade` with `SetExpertMagicNumber`, `SetDeviationInPoints`, `SetTypeFillingBySymbol`; check `ResultRetcode()` = `TRADE_RETCODE_DONE`/`PLACED` | Ignoring return codes; fixed filling mode |
| Own positions | Loop `PositionsTotal()-1..0`, `PositionGetTicket(i)`, filter `POSITION_SYMBOL` + `POSITION_MAGIC` | `OrderSelect(i, SELECT_BY_POS, MODE_TRADES)` (MQL4) |
| Netting vs hedging | Check `ACCOUNT_MARGIN_MODE`; on netting one position per symbol — opposite order reduces/reverses it | Assuming hedging everywhere |
| Prices | `SymbolInfoDouble(_Symbol, SYMBOL_ASK/BID)`, `NormalizeDouble(x, _Digits)` | `Ask`, `Bid`, `Point`, `Digits` (MQL4 vars) |
| Stops | Respect `SYMBOL_TRADE_STOPS_LEVEL` (min distance) and `SYMBOL_TRADE_FREEZE_LEVEL` (no modify near price) | SL/TP inside stops level → retcode 10016 invalid stops |
| Volume | Round down to `SYMBOL_VOLUME_STEP`, clamp to MIN/MAX; skip trade if below MIN | Rounding up to min lot (silently exceeds risk) |
| Margin | `OrderCalcMargin` vs `ACCOUNT_MARGIN_FREE` before sending | Sending and hoping (Market validator rejects) |
| Money per point | `SYMBOL_TRADE_TICK_VALUE / SYMBOL_TRADE_TICK_SIZE` (or `OrderCalcProfit`) | Assuming $10/pip; breaks on gold, indices, JPY pairs |
| Events | `OnTradeTransaction` for fills/partial fills; `OnTimer` for multi-symbol or scheduled work | Polling history every tick |
| State | Recover state from open positions/history on restart; `GlobalVariableSet` for small persisted values | Keeping critical state only in globals (lost on restart) |
| Logging | `PrintFormat` with retcode + description on failure only | Printing every tick (slows tester, huge logs) |
| Multi-symbol | Per-symbol handles + `SymbolSelect`, check `SERIES_SYNCHRONIZED`/bars count before reading | Reading other symbols' data without checking it is loaded |

Common retcodes: 10009 DONE · 10004 requote · 10006 rejected · 10013 invalid request · 10014 invalid volume · 10015 invalid price · 10016 invalid stops · 10019 no money · 10027 autotrading disabled by client · 10030 invalid fill mode.
