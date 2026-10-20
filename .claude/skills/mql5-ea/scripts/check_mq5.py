#!/usr/bin/env python3
"""Static checks for MQL5 EA source: MQL4 leftovers, handle misuse, unchecked trades,
and risk anti-patterns. Not a compiler — always compile in MetaEditor too.

Usage: check_mq5.py FILE_OR_DIR [...]
Output: `file:line  LEVEL  rule  hint`, then a count. Exit 1 if any ERROR.
"""
import os
import re
import sys

# MQL5 signature arg counts (MQL4 versions take one more: shift)
IND_ARGS = {"iMA": 6, "iRSI": 4, "iATR": 3, "iADX": 3, "iBands": 6, "iCCI": 4, "iMomentum": 4,
            "iMACD": 6, "iStochastic": 8, "iStdDev": 6, "iSAR": 4}

LINE_RULES = [  # (level, rule, regex, hint)
    ("ERROR", "mql4-entry", r"\b(int|void)\s+(start|init|deinit)\s*\(\s*\)", "use OnTick/OnInit/OnDeinit"),
    ("ERROR", "mql4-orders", r"\bOrderSelect\s*\([^)]*SELECT_BY_POS|\bMODE_TRADES\b|\bMODE_HISTORY\b", "positions: PositionGetTicket(i) / history: HistorySelect"),
    ("ERROR", "mql4-orderclose", r"(?<![.\w])OrderClose\s*\(|(?<![.\w])OrderModify\s*\(", "use CTrade.PositionClose / PositionModify"),
    ("ERROR", "mql4-marketinfo", r"\bMarketInfo\s*\(", "use SymbolInfoDouble/SymbolInfoInteger"),
    ("ERROR", "mql4-account", r"\bAccount(Balance|Equity|FreeMargin)\s*\(\s*\)", "use AccountInfoDouble(ACCOUNT_...)"),
    ("ERROR", "mql4-series", r"(?<![\w.])(Close|Open|High|Low|Time|Volume)\s*\[", "use iClose/CopyRates or CopyClose"),
    ("WARN", "mql4-askbid", r"(?<![\w.])(Ask|Bid)(?![\w(])", "use SymbolInfoDouble(_Symbol, SYMBOL_ASK/BID)"),
    ("WARN", "mql4-point", r"(?<![\w.])(Digits|Point)(?![\w(])", "use _Digits / _Point"),
    ("INFO", "property-strict", r"#property\s+strict", "MQL4 leftover; not needed in MQL5"),
    ("WARN", "sleep", r"\bSleep\s*\(", "avoid Sleep in EAs (blocks the tick flow; ignored in tester)"),
    ("WARN", "fixed-lot", r"\.(Buy|Sell)\s*\(\s*\d+(\.\d+)?\s*,", "fixed lot — size by risk % and stop distance"),
    ("ERROR", "no-stoploss", r"\.(Buy|Sell)\s*\(\s*[^,()]+,\s*[^,()]+,\s*[^,()]+,\s*0(\.0*)?\s*,", "order without stop loss"),
    ("ERROR", "martingale", r"\b\w*(lot|vol)\w*\s*\*=\s*(1\.[5-9]|[2-9])|\b\w*(lot|vol)\w*\s*=\s*\w*(lot|vol)\w*\s*\*\s*(1\.[5-9]|[2-9])", "martingale lot multiplication — unbounded risk"),
    ("WARN", "copybuffer-unchecked", r"^\s*CopyBuffer\s*\(", "check CopyBuffer return count"),
    ("WARN", "raw-ordersend", r"(?<![.\w])OrderSend\s*\(", "prefer CTrade; if raw, check result.retcode"),
]


def strip(code):
    """Remove comments and string literals, keep line breaks."""
    out, i, n = [], 0, len(code)
    while i < n:
        if code.startswith("//", i):
            j = code.find("\n", i)
            i = n if j < 0 else j
        elif code.startswith("/*", i):
            j = code.find("*/", i + 2)
            seg = code[i:(n if j < 0 else j + 2)]
            out.append("\n" * seg.count("\n"))
            i = n if j < 0 else j + 2
        elif code[i] == '"':
            j = i + 1
            while j < n and code[j] != '"':
                j += 2 if code[j] == "\\" else 1
            out.append('""')
            i = j + 1
        else:
            out.append(code[i])
            i += 1
    return "".join(out)


def args_count(code, start):
    depth, count, i = 0, 1, start
    while i < len(code):
        ch = code[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                inner = code[start + 1:i].strip()
                return 0 if not inner else count
        elif ch == "," and depth == 1:
            count += 1
        i += 1
    return -1


def func_body(code, name):
    m = re.search(r"\b" + name + r"\s*\([^)]*\)\s*\{", code)
    if not m:
        return None, 0
    i, depth = m.end() - 1, 0
    for j in range(i, len(code)):
        depth += code[j] == "{"
        depth -= code[j] == "}"
        if depth == 0:
            return code[i:j + 1], code.count("\n", 0, i)
    return code[i:], code.count("\n", 0, i)


def check(path):
    raw = open(path, encoding="utf-8", errors="ignore").read()
    code = strip(raw)
    hits = []
    lines = code.split("\n")
    for ln, text in enumerate(lines, 1):
        for level, rule, rx, hint in LINE_RULES:
            if re.search(rx, text, re.I if rule == "martingale" else 0):
                hits.append((ln, level, rule, hint))
    for m in re.finditer(r"\b(" + "|".join(IND_ARGS) + r")\s*\(", code):
        n = args_count(code, m.end() - 1)
        if n == IND_ARGS[m.group(1)] + 1:
            hits.append((code.count("\n", 0, m.start()) + 1, "ERROR", "mql4-indicator",
                         f"{m.group(1)} called with MQL4 signature (shift); MQL5 returns a handle — create in OnInit, read with CopyBuffer"))
    body, off = func_body(code, "OnTick")
    if body:
        for m in re.finditer(r"\b(" + "|".join(IND_ARGS) + r")\s*\(", body):
            hits.append((off + body.count("\n", 0, m.start()) + 1, "ERROR", "handle-in-ontick",
                         f"{m.group(1)} handle created on every tick — create once in OnInit"))
    uses_handles = re.search(r"\b(" + "|".join(IND_ARGS) + r")\s*\(", code)
    if uses_handles and "IndicatorRelease" not in code:
        hits.append((0, "WARN", "no-release", "release indicator handles in OnDeinit (IndicatorRelease)"))
    if re.search(r"\.(Buy|Sell|PositionOpen|BuyLimit|SellLimit|BuyStop|SellStop)\s*\(", code) and "ResultRetcode" not in code:
        hits.append((0, "WARN", "retcode-unchecked", "check trade.ResultRetcode() after sending orders"))
    if re.search(r"\bCTrade\b", code) and "SetExpertMagicNumber" not in code:
        hits.append((0, "WARN", "no-magic", "trade.SetExpertMagicNumber(...) to isolate this EA's positions"))
    if re.search(r"\.(Buy|Sell)\s*\(", code) and not re.search(r"OrderCalcMargin|ACCOUNT_MARGIN_FREE", code):
        hits.append((0, "INFO", "no-margin-check", "check free margin before trading (required for Market products)"))
    if "OnTick" in code and not re.search(r"iTime\s*\(|IsNewBar|SERIES_LASTBAR_DATE", code):
        hits.append((0, "INFO", "every-tick-logic", "no new-bar detection: signals run on every tick (intended?)"))
    return sorted(hits)


def main():
    paths = []
    for p in sys.argv[1:] or ["."]:
        if os.path.isdir(p):
            for d, _, fs in os.walk(p):
                paths += [os.path.join(d, f) for f in fs if f.endswith((".mq5", ".mqh"))]
        else:
            paths.append(p)
    errors = total = 0
    for p in paths:
        for ln, level, rule, hint in check(p):
            print(f"{p}:{ln}  {level}  {rule}  {hint}")
            total += 1
            errors += level == "ERROR"
    print(f"{len(paths)} file(s): {errors} error(s), {total - errors} warning/info")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
