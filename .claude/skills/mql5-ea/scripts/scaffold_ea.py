#!/usr/bin/env python3
"""Generate ONE self-contained MQL5 Expert Advisor (.mq5) that contains every strategy
archetype; the active one is chosen with the input `InpStrategy`.

Usage: scaffold_ea.py NAME [--default ma_cross|donchian|bb_reversion|session_breakout]
                      [--magic 240001] [--author "..."] [--out Experts/]
Safety core shared by all strategies: risk-% position sizing from ATR stop, margin check,
spread/time filters, daily loss limit, ATR trailing stop, magic-number isolation,
signals on closed bars only, retcode checks, handle release.
Only the selected strategy creates indicator handles. Prints only the output path.
"""
import argparse
import os
import sys
from string import Template

STRATEGIES = {
    "ma_cross": {
        "label": "MA crossover (trend)",
        "desc": "Trend following: fast/slow MA crossover on closed bars, optional ADX strength filter",
        "inputs": """input int            InpFastMA     = 20;        // Fast MA period
input int            InpSlowMA     = 50;        // Slow MA period
input ENUM_MA_METHOD InpMAMethod   = MODE_EMA;  // MA method
input bool           InpUseADX     = true;      // Require trend strength (ADX)
input int            InpADXPeriod  = 14;        // ADX period
input double         InpADXMin     = 20.0;      // Minimum ADX""",
        "globals": "int hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hADX = INVALID_HANDLE;",
        "init": """   if(InpFastMA >= InpSlowMA) { Print("Fast MA must be shorter than slow MA"); return INIT_PARAMETERS_INCORRECT; }
   hFast = iMA(_Symbol, _Period, InpFastMA, 0, InpMAMethod, PRICE_CLOSE);
   hSlow = iMA(_Symbol, _Period, InpSlowMA, 0, InpMAMethod, PRICE_CLOSE);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE) { Print("MA handle failed: ", GetLastError()); return INIT_FAILED; }
   if(InpUseADX)
   {
      hADX = iADX(_Symbol, _Period, InpADXPeriod);
      if(hADX == INVALID_HANDLE) { Print("ADX handle failed: ", GetLastError()); return INIT_FAILED; }
   }""",
        "deinit": "   ReleaseHandle(hFast); ReleaseHandle(hSlow); ReleaseHandle(hADX);",
        "entry": """   double f1 = Buf(hFast, 0, 1), f2 = Buf(hFast, 0, 2);
   double s1 = Buf(hSlow, 0, 1), s2 = Buf(hSlow, 0, 2);
   if(f1 == EMPTY_VALUE || f2 == EMPTY_VALUE || s1 == EMPTY_VALUE || s2 == EMPTY_VALUE) return 0;
   if(InpUseADX)
   {
      double adx = Buf(hADX, 0, 1);
      if(adx == EMPTY_VALUE || adx < InpADXMin) return 0;
   }
   if(f2 <= s2 && f1 > s1) return 1;    // golden cross on the last closed bar
   if(f2 >= s2 && f1 < s1) return -1;   // death cross
   return 0;""",
        "exit": """   double f1 = Buf(hFast, 0, 1), s1 = Buf(hSlow, 0, 1);
   if(f1 == EMPTY_VALUE || s1 == EMPTY_VALUE) return false;
   return dir > 0 ? f1 < s1 : f1 > s1;   // opposite cross""",
    },
    "donchian": {
        "label": "Donchian breakout (Turtle)",
        "desc": "Breakout (Turtle-style): close beyond N-bar channel, exit on M-bar opposite channel",
        "inputs": """input int InpEntryBars = 20;   // Entry channel (bars)
input int InpExitBars  = 10;   // Exit channel (bars)""",
        "globals": "",
        "init": """   if(InpExitBars >= InpEntryBars) Print("Note: exit channel is usually shorter than entry channel");""",
        "deinit": "",
        "entry": """   double c = iClose(_Symbol, _Period, 1);
   int hi = iHighest(_Symbol, _Period, MODE_HIGH, InpEntryBars, 2);   // channel excludes the signal bar
   int lo = iLowest(_Symbol, _Period, MODE_LOW, InpEntryBars, 2);
   if(c == 0 || hi < 0 || lo < 0) return 0;
   if(c > iHigh(_Symbol, _Period, hi)) return 1;
   if(c < iLow(_Symbol, _Period, lo)) return -1;
   return 0;""",
        "exit": """   double c = iClose(_Symbol, _Period, 1);
   if(dir > 0)
   {
      int lo = iLowest(_Symbol, _Period, MODE_LOW, InpExitBars, 2);
      return lo >= 0 && c < iLow(_Symbol, _Period, lo);
   }
   int hi = iHighest(_Symbol, _Period, MODE_HIGH, InpExitBars, 2);
   return hi >= 0 && c > iHigh(_Symbol, _Period, hi);""",
    },
    "bb_reversion": {
        "label": "Bollinger + RSI reversion",
        "desc": "Mean reversion with trend filter: close outside Bollinger band + RSI extreme, only in the direction of the long MA; exit at middle band",
        "inputs": """input int    InpBBPeriod  = 20;    // Bollinger period
input double InpBBDev     = 2.0;   // Bollinger deviation
input int    InpRSIPeriod = 14;    // RSI period
input double InpRSILow    = 30;    // RSI oversold
input double InpRSIHigh   = 70;    // RSI overbought
input int    InpTrendMA   = 200;   // Trend filter SMA (0 = off)""",
        "globals": "int hBB = INVALID_HANDLE, hRSI = INVALID_HANDLE, hTrend = INVALID_HANDLE;",
        "init": """   hBB  = iBands(_Symbol, _Period, InpBBPeriod, 0, InpBBDev, PRICE_CLOSE);
   hRSI = iRSI(_Symbol, _Period, InpRSIPeriod, PRICE_CLOSE);
   if(hBB == INVALID_HANDLE || hRSI == INVALID_HANDLE) { Print("Indicator handle failed: ", GetLastError()); return INIT_FAILED; }
   if(InpTrendMA > 0)
   {
      hTrend = iMA(_Symbol, _Period, InpTrendMA, 0, MODE_SMA, PRICE_CLOSE);
      if(hTrend == INVALID_HANDLE) { Print("Trend MA handle failed: ", GetLastError()); return INIT_FAILED; }
   }""",
        "deinit": "   ReleaseHandle(hBB); ReleaseHandle(hRSI); ReleaseHandle(hTrend);",
        "entry": """   double c = iClose(_Symbol, _Period, 1);
   double upper = Buf(hBB, 1, 1), lower = Buf(hBB, 2, 1), rsi = Buf(hRSI, 0, 1);
   if(c == 0 || upper == EMPTY_VALUE || lower == EMPTY_VALUE || rsi == EMPTY_VALUE) return 0;
   bool upTrend = true, downTrend = true;
   if(InpTrendMA > 0)
   {
      double t = Buf(hTrend, 0, 1);
      if(t == EMPTY_VALUE) return 0;
      upTrend = c > t; downTrend = c < t;
   }
   if(c < lower && rsi < InpRSILow && upTrend) return 1;     // pullback in uptrend
   if(c > upper && rsi > InpRSIHigh && downTrend) return -1; // rally in downtrend
   return 0;""",
        "exit": """   double c = iClose(_Symbol, _Period, 1), mid = Buf(hBB, 0, 1);
   if(c == 0 || mid == EMPTY_VALUE) return false;
   return dir > 0 ? c >= mid : c <= mid;   // back to the mean""",
    },
    "session_breakout": {
        "label": "Session range breakout",
        "desc": "Session range breakout: range between two server hours, first close outside the range after it ends (one trade per day), flat at close hour",
        "inputs": """input int InpRangeStartHour = 0;    // Range start (server hour)
input int InpRangeEndHour   = 7;    // Range end (server hour, exclusive)
input int InpCloseHour      = 22;   // Close open trade at (server hour)""",
        "globals": "int g_tradedDay = -1;",
        "init": """   if(InpRangeStartHour >= InpRangeEndHour) { Print("Range start must be before range end"); return INIT_PARAMETERS_INCORRECT; }
   if(PeriodSeconds(_Period) > 3600) Print("Use H1 or lower for session breakout");""",
        "deinit": "",
        "entry": """   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if(dt.hour < InpRangeEndHour || dt.hour >= InpCloseHour || g_tradedDay == dt.day_of_year) return 0;
   datetime dayStart = iTime(_Symbol, PERIOD_D1, 0);
   if(dayStart == 0) return 0;
   int first = iBarShift(_Symbol, _Period, dayStart + InpRangeStartHour * 3600, false);
   int last  = iBarShift(_Symbol, _Period, dayStart + InpRangeEndHour * 3600 - 1, false);
   if(first < 0 || last < 0 || first < last) return 0;
   int count = first - last + 1;
   int ih = iHighest(_Symbol, _Period, MODE_HIGH, count, last);
   int il = iLowest(_Symbol, _Period, MODE_LOW, count, last);
   if(ih < 0 || il < 0) return 0;   // never trade on missing data
   double hi = iHigh(_Symbol, _Period, ih), lo = iLow(_Symbol, _Period, il);
   double c  = iClose(_Symbol, _Period, 1);
   if(hi <= 0 || lo <= 0 || c <= 0) return 0;
   if(c > hi) { g_tradedDay = dt.day_of_year; return 1; }
   if(c < lo) { g_tradedDay = dt.day_of_year; return -1; }
   return 0;""",
        "exit": """   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   return dt.hour >= InpCloseHour;   // flat before the end of the day""",
    },
}

CORE = Template(r"""//+------------------------------------------------------------------+
//| ${name}.mq5 — single EA, strategy chosen with input InpStrategy
${strategy_list}//| Generated by the mql5-ea skill. Test in the Strategy Tester before any live use.
//+------------------------------------------------------------------+
#property copyright "${author}"
#property version   "1.00"
#property description "One EA, ${count} selectable strategies (InpStrategy). Risk-% sizing, ATR stops, daily loss limit."

#include <Trade\Trade.mqh>

enum ENUM_STRATEGY
{
${enum_values}
};

input group "Strategy selection"
input ENUM_STRATEGY InpStrategy = ${default_enum};   // Active strategy
${inputs}
enum ENUM_LOT_MODE
{
   LOT_RISK_PERCENT = 0,   // Risk % of equity (size from stop distance)
   LOT_FIXED = 1           // Fixed lot (e.g. 0.01)
};

input group "Risk"
input ENUM_LOT_MODE InpLotMode  = LOT_RISK_PERCENT; // Position sizing
input double InpRiskPercent     = 1.0;   // Risk per trade (% of equity) — risk mode
input double InpFixedLot        = 0.01;  // Lot size — fixed mode
input double InpMaxRiskCapPct   = 0;     // Skip a trade if its risk exceeds this % of equity (0 = no cap)
input int    InpATRPeriod       = 14;    // ATR period
input double InpSL_ATR          = 2.0;   // Stop loss (x ATR)
input double InpTP_ATR          = 0.0;   // Take profit (x ATR, 0 = none)
input double InpTrail_ATR       = 0.0;   // Trailing stop (x ATR, 0 = off)
input double InpMaxDailyLossPct = 3.0;   // Stop trading for the day after this equity loss (%, 0 = off)
input group "Small account & goals"
input double InpEquityTarget    = 0;     // Goal: stop & close when equity reaches this (0 = off)
input double InpMaxDrawdownPct  = 50;    // Hard stop: equity this % below its peak (0 = off)
input double InpReduceRiskDDPct = 0;     // Halve size while equity is this % below peak (0 = off)
input bool   InpResetPeak       = false; // Reset stored peak (set true once after deposit/withdrawal)
input group "Filters"
input int    InpMaxSpreadPts    = 30;    // Max spread (points)
input int    InpStartHour       = 0;     // Trading window start (server hour)
input int    InpEndHour         = 24;    // Trading window end (server hour)
input group "Execution"
input ulong  InpMagic           = ${magic};  // Magic number (unique per EA/symbol)
input int    InpSlippagePts     = 10;    // Max slippage (points)

CTrade   trade;
int      hATR = INVALID_HANDLE;
${globals}
datetime g_lastBar = 0;
int      g_day = -1;
double   g_dayStartEquity = 0;
double   g_peakEquity = 0;
bool     g_halted = false;

void   CloseMine();    // forward declarations
string PeakKey();

//--- helpers -------------------------------------------------------
double Buf(const int handle, const int buffer, const int shift)
{
   double v[];
   if(handle == INVALID_HANDLE || CopyBuffer(handle, buffer, shift, 1, v) != 1) return EMPTY_VALUE;
   return v[0];
}

void ReleaseHandle(int &handle)
{
   if(handle != INVALID_HANDLE) IndicatorRelease(handle);
   handle = INVALID_HANDLE;
}

bool IsNewBar()
{
   datetime t = iTime(_Symbol, _Period, 0);
   if(t == 0 || t == g_lastBar) return false;
   g_lastBar = t;
   return true;
}

bool IsMine()   // call right after PositionGetTicket()
{
   return PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagic;
}

int PositionDir()   // +1 long, -1 short, 0 flat (this symbol + magic only)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) == 0 || !IsMine()) continue;
      return PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
   }
   return 0;
}

double NormalizeVolume(double lots)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) return 0;
   lots = MathFloor(lots / step) * step;
   if(lots < vmin) return 0;   // risk budget too small for the minimum lot: skip, never round up
   int digits = (int)MathMax(0, MathCeil(-MathLog10(step)));
   return NormalizeDouble(MathMin(lots, vmax), digits);
}

double LotsForTrade(const double slDistance)
{
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   if(slDistance <= 0 || tickValue <= 0 || tickSize <= 0 || equity <= 0) return 0;
   double lossPerLot = slDistance / tickSize * tickValue;
   double scale = 1.0;   // halve size while in drawdown (if enabled)
   if(InpReduceRiskDDPct > 0 && g_peakEquity > 0 && equity <= g_peakEquity * (1.0 - InpReduceRiskDDPct / 100.0)) scale = 0.5;
   double lots;
   if(InpLotMode == LOT_FIXED)
      lots = NormalizeVolume(InpFixedLot * scale);
   else
      lots = NormalizeVolume(equity * InpRiskPercent * scale / 100.0 / lossPerLot);
   if(lots <= 0) lots = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);   // smallest tradable size
   double riskPct = lots * lossPerLot / equity * 100.0;
   if(InpMaxRiskCapPct > 0 && riskPct > InpMaxRiskCapPct)
   {
      PrintFormat("Trade skipped: %.2f lot would risk %.1f%% of equity (cap %.1f%%). Cent account or tighter stop helps.", lots, riskPct, InpMaxRiskCapPct);
      return 0;
   }
   return lots;
}

bool GoalOrHardStop()   // true = no new trades (target reached or max drawdown hit)
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEquity) { g_peakEquity = eq; GlobalVariableSet(PeakKey(), eq); }
   if(g_halted) return true;
   if(InpEquityTarget > 0 && eq >= InpEquityTarget)
   {
      g_halted = true; CloseMine();
      PrintFormat("Equity target %.2f reached: positions closed, trading stopped. Lock/withdraw profit, then restart with InpResetPeak=true.", InpEquityTarget);
      return true;
   }
   if(InpMaxDrawdownPct > 0 && g_peakEquity > 0 && eq <= g_peakEquity * (1.0 - InpMaxDrawdownPct / 100.0))
   {
      g_halted = true; CloseMine();
      PrintFormat("Max drawdown %.1f%% from peak %.2f hit: positions closed, trading stopped for review.", InpMaxDrawdownPct, g_peakEquity);
      return true;
   }
   return false;
}

string PeakKey() { return StringFormat("mql5ea_peak_%I64u_%s", InpMagic, _Symbol); }

bool SpreadOK() { return SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= InpMaxSpreadPts; }

bool InWindow()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if(InpStartHour <= InpEndHour) return dt.hour >= InpStartHour && dt.hour < InpEndHour;
   return dt.hour >= InpStartHour || dt.hour < InpEndHour;   // window across midnight
}

bool DailyLossHit()   // baseline = equity at the first tick of the server day (resets if the EA restarts)
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_year != g_day) { g_day = dt.day_of_year; g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY); }
   if(InpMaxDailyLossPct <= 0 || g_dayStartEquity <= 0) return false;
   return AccountInfoDouble(ACCOUNT_EQUITY) <= g_dayStartEquity * (1.0 - InpMaxDailyLossPct / 100.0);
}

//--- strategies (one block per strategy; only the selected one runs) --
${strategy_funcs}
//--- dispatch ------------------------------------------------------
int InitStrategy()
{
   switch(InpStrategy)
   {
${init_cases}
   }
   return INIT_PARAMETERS_INCORRECT;
}

void DeinitStrategies()
{
${deinit_calls}
}

int EntrySignal()   // +1 buy, -1 sell, 0 none — evaluated on closed bars only
{
   switch(InpStrategy)
   {
${entry_cases}
   }
   return 0;
}

bool ExitSignal(const int dir)   // true = close the open position of direction dir
{
   switch(InpStrategy)
   {
${exit_cases}
   }
   return false;
}

//--- execution -----------------------------------------------------
bool Open(const int dir, const double atr)
{
   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double slDist = MathMax(InpSL_ATR * atr, stopsLevel + _Point);
   double price  = dir > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl     = NormalizeDouble(dir > 0 ? price - slDist : price + slDist, _Digits);
   double tp     = 0;
   if(InpTP_ATR > 0)
   {
      double tpDist = MathMax(InpTP_ATR * atr, stopsLevel + _Point);
      tp = NormalizeDouble(dir > 0 ? price + tpDist : price - tpDist, _Digits);
   }
   double lots = LotsForTrade(slDist);
   if(lots <= 0) return false;   // reason already printed
   double margin = 0;
   ENUM_ORDER_TYPE type = dir > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(type, _Symbol, lots, price, margin) || margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
   { Print("Not enough free margin; trade skipped"); return false; }
   bool sent = dir > 0 ? trade.Buy(lots, _Symbol, 0.0, sl, tp, "${name}")
                       : trade.Sell(lots, _Symbol, 0.0, sl, tp, "${name}");
   uint rc = trade.ResultRetcode();
   if(!sent || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
   { PrintFormat("Order failed: retcode=%u %s", rc, trade.ResultRetcodeDescription()); return false; }
   return true;
}

void CloseMine()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !IsMine()) continue;
      if(!trade.PositionClose(ticket))
         PrintFormat("Close failed #%I64u: retcode=%u", ticket, trade.ResultRetcode());
   }
}

void Trail(const double atr)
{
   if(InpTrail_ATR <= 0) return;
   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double dist = InpTrail_ATR * atr;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !IsMine()) continue;
      double sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double nsl = NormalizeDouble(bid - dist, _Digits);
         if(nsl > sl + _Point && bid - nsl >= stopsLevel) trade.PositionModify(ticket, nsl, tp);
      }
      else
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double nsl = NormalizeDouble(ask + dist, _Digits);
         if((sl == 0 || nsl < sl - _Point) && nsl - ask >= stopsLevel) trade.PositionModify(ticket, nsl, tp);
      }
   }
}

//--- events --------------------------------------------------------
int OnInit()
{
   if(InpLotMode == LOT_RISK_PERCENT && (InpRiskPercent <= 0 || InpRiskPercent > 20)) { Print("Risk per trade must be > 0 and <= 20%"); return INIT_PARAMETERS_INCORRECT; }
   if(InpLotMode == LOT_FIXED && InpFixedLot <= 0) { Print("Fixed lot must be > 0"); return INIT_PARAMETERS_INCORRECT; }
   if(InpResetPeak) GlobalVariableDel(PeakKey());
   g_peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(GlobalVariableCheck(PeakKey())) g_peakEquity = MathMax(g_peakEquity, GlobalVariableGet(PeakKey()));
   g_halted = false;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);
   hATR = iATR(_Symbol, _Period, InpATRPeriod);
   if(hATR == INVALID_HANDLE) { Print("ATR handle failed: ", GetLastError()); return INIT_FAILED; }
   int rc = InitStrategy();   // creates handles for the selected strategy only
   if(rc != INIT_SUCCEEDED) return rc;
   PrintFormat("%s started: strategy=%s, sizing=%s, peak equity=%.2f, min lot=%.2f", MQLInfoString(MQL_PROGRAM_NAME),
               EnumToString(InpStrategy), EnumToString(InpLotMode), g_peakEquity, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ReleaseHandle(hATR);
   DeinitStrategies();
}

void OnTick()
{
   bool lossHit = DailyLossHit();           // tracks the day baseline every tick
   bool stopNew = GoalOrHardStop();         // goal reached / max drawdown → no new trades
   double atr = Buf(hATR, 0, 1);
   if(atr == EMPTY_VALUE || atr <= 0) return;
   Trail(atr);                               // stop management every tick
   if(!IsNewBar()) return;                   // signals only once per closed bar
   int pos = PositionDir();
   if(pos != 0 && ExitSignal(pos)) { CloseMine(); pos = PositionDir(); }
   if(pos != 0 || lossHit || stopNew || !SpreadOK() || !InWindow()) return;
   int sig = EntrySignal();
   if(sig != 0) Open(sig, atr);
}
//+------------------------------------------------------------------+
""")


def build(name, default, magic, author):
    keys = list(STRATEGIES)
    enum = lambda k: "STRAT_" + k.upper()  # noqa: E731
    enum_values, inputs, funcs, inits, deinits, entries, exits, listing = [], [], [], [], [], [], [], []
    for i, k in enumerate(keys):
        s = STRATEGIES[k]
        sep = "," if i < len(keys) - 1 else ""
        enum_values.append(f"   {enum(k)} = {i}{sep}   // {s['label']}")
        inputs.append(f'input group "{s["label"]}"\n{s["inputs"]}')
        listing.append(f"//|   {enum(k):<24} {s['desc']}\n")
        init_body = s["init"] + "\n" if s["init"] else ""
        deinit_body = s["deinit"] + "\n" if s["deinit"] else ""
        funcs.append(
            f"//--- {s['label']}\n"
            f"int Init_{k}()\n{{\n{init_body}   return INIT_SUCCEEDED;\n}}\n\n"
            f"void Deinit_{k}()\n{{\n{deinit_body}}}\n\n"
            f"int Entry_{k}()\n{{\n{s['entry']}\n}}\n\n"
            f"bool Exit_{k}(const int dir)\n{{\n{s['exit']}\n}}\n")
        inits.append(f"      case {enum(k)}: return Init_{k}();")
        deinits.append(f"   Deinit_{k}();")
        entries.append(f"      case {enum(k)}: return Entry_{k}();")
        exits.append(f"      case {enum(k)}: return Exit_{k}(dir);")
    globals_ = "\n".join(STRATEGIES[k]["globals"] for k in keys if STRATEGIES[k]["globals"])
    return CORE.substitute(
        name=name, author=author, magic=magic, count=len(keys), default_enum=enum(default),
        strategy_list="".join(listing), enum_values="\n".join(enum_values), inputs="\n".join(inputs),
        globals=globals_, strategy_funcs="\n".join(funcs), init_cases="\n".join(inits),
        deinit_calls="\n".join(deinits), entry_cases="\n".join(entries), exit_cases="\n".join(exits))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("--default", default="ma_cross", choices=sorted(STRATEGIES), help="strategy preselected in inputs")
    p.add_argument("--magic", type=int, default=240001)
    p.add_argument("--author", default="")
    p.add_argument("--out", default=".")
    a = p.parse_args()
    if not a.name.replace("_", "").isalnum():
        sys.exit("NAME: letters, digits and _ only")
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, a.name + ".mq5")
    if os.path.exists(path):
        sys.exit(f"{path} exists — this skill keeps ONE EA: edit that file instead of creating another")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build(a.name, a.default, a.magic, a.author))
    print(path)


if __name__ == "__main__":
    main()
