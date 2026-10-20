#!/usr/bin/env python3
"""Evaluate an EA's closed trades: core metrics, R-multiple stats, SQN and a Monte Carlo
of trade order (bootstrap) for drawdown and outcome ranges.

Usage: analyze_trades.py TRADES.csv [--initial 10000] [--runs 2000] [--ruin-dd 30] [--risk 100] [--xlsx out.xlsx]
CSV: any export with a profit column (profit/Profit/P&L/net). Optional commission/swap columns are
added to profit. Rows whose type/comment is balance/deposit/withdrawal are ignored.
--risk = money risked per trade (1R) for R-multiples; default = average loss.
"""
import argparse
import csv
import math
import random
import statistics as st
import sys

PROFIT_COLS = ("profit", "p&l", "pnl", "net", "net profit")
EXTRA_COLS = ("commission", "swap", "fee")
SKIP_WORDS = ("balance", "deposit", "withdraw", "credit")


def num(v):
    try:
        return float(str(v).replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        rows = list(csv.DictReader(f, dialect=dialect))
    if not rows:
        sys.exit("no rows")
    keys = {k.lower().strip(): k for k in rows[0]}
    pc = next((keys[c] for c in PROFIT_COLS if c in keys), None)
    if not pc:
        sys.exit(f"no profit column; columns: {list(rows[0])}")
    extras = [keys[c] for c in EXTRA_COLS if c in keys]
    out = []
    for r in rows:
        text = " ".join(str(r.get(keys.get(k, ""), "")).lower() for k in ("type", "comment"))
        if any(w in text for w in SKIP_WORDS):
            continue
        p = num(r.get(pc, ""))
        if p is None:
            continue
        out.append(p + sum(num(r.get(e, "")) or 0 for e in extras))
    return out


def max_dd(pnls, initial):
    eq = peak = initial
    mdd = mdd_pct = 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
        mdd_pct = max(mdd_pct, (peak - eq) / peak * 100 if peak > 0 else 100)
    return mdd, mdd_pct


def streak(pnls):
    best = cur = 0
    for p in pnls:
        cur = cur + 1 if p < 0 else 0
        best = max(best, cur)
    return best


def pct(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, max(0, int(round(q / 100 * (len(sorted_vals) - 1)))))]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("csv")
    a.add_argument("--initial", type=float, default=10000)
    a.add_argument("--runs", type=int, default=2000)
    a.add_argument("--ruin-dd", type=float, default=30, help="drawdown %% counted as ruin")
    a.add_argument("--risk", type=float, default=0, help="money per 1R; default = average loss")
    a.add_argument("--seed", type=int, default=7)
    a.add_argument("--xlsx", default=None)
    o = a.parse_args()
    pnl = load(o.csv)
    n = len(pnl)
    if n < 2:
        sys.exit("need at least 2 trades")
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    gp, gl = sum(wins), -sum(losses)
    net = gp - gl
    mdd, mdd_pct = max_dd(pnl, o.initial)
    one_r = o.risk or (gl / len(losses) if losses else 0)
    r = [p / one_r for p in pnl] if one_r else []
    sd_r = st.pstdev(r) if r else 0
    sqn = math.sqrt(min(n, 100)) * st.mean(r) / sd_r if sd_r else 0
    metrics = [
        ("Trades", n),
        ("Net profit", round(net, 2)),
        ("Return on initial %", round(net / o.initial * 100, 2)),
        ("Profit factor", round(gp / gl, 2) if gl else float("inf")),
        ("Win rate %", round(len(wins) / n * 100, 1)),
        ("Average win", round(st.mean(wins), 2) if wins else 0),
        ("Average loss", round(-st.mean(losses), 2) if losses else 0),
        ("Payoff ratio", round(st.mean(wins) / -st.mean(losses), 2) if wins and losses else 0),
        ("Expectancy / trade", round(net / n, 2)),
        ("Expectancy (R)", round(st.mean(r), 3) if r else 0),
        ("SQN (n capped at 100)", round(sqn, 2)),
        ("Max drawdown", round(mdd, 2)),
        ("Max drawdown %", round(mdd_pct, 2)),
        ("Recovery factor", round(net / mdd, 2) if mdd else float("inf")),
        ("Max consecutive losses", streak(pnl)),
    ]
    rnd = random.Random(o.seed)
    mc_dd, mc_net, ruin = [], [], 0
    for _ in range(o.runs):
        sample = [rnd.choice(pnl) for _ in range(n)]
        d = max_dd(sample, o.initial)[1]
        mc_dd.append(d)
        mc_net.append(sum(sample))
        ruin += d >= o.ruin_dd
    mc_dd.sort()
    mc_net.sort()
    mc = [
        ("MC runs (bootstrap)", o.runs),
        ("MC max DD % — median", round(pct(mc_dd, 50), 2)),
        ("MC max DD % — 95th pct", round(pct(mc_dd, 95), 2)),
        ("MC net profit — 5th pct", round(pct(mc_net, 5), 2)),
        ("MC net profit — median", round(pct(mc_net, 50), 2)),
        (f"MC P(DD >= {o.ruin_dd:g}%)", f"{ruin / o.runs * 100:.1f}%"),
    ]
    flags = []
    if n < 100:
        flags.append(f"only {n} trades — statistics are weak (aim for 100+ out-of-sample)")
    pf = gp / gl if gl else float("inf")
    if pf < 1.2:
        flags.append("profit factor < 1.2 — edge may vanish after costs/slippage")
    if pct(mc_dd, 95) >= o.ruin_dd:
        flags.append(f"95th-percentile MC drawdown >= {o.ruin_dd:g}% — reduce risk per trade")
    if pct(mc_net, 5) < 0:
        flags.append("5th-percentile MC net profit < 0 — result depends on trade order luck")
    width = max(len(k) for k, _ in metrics + mc)
    for k, v in metrics + mc:
        print(f"{k:<{width}}  {v}")
    for f_ in flags:
        print("FLAG", f_)
    if not flags:
        print("No red flags (still validate out-of-sample and forward test)")
    if o.xlsx:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Metrics"
        for row in [("Metric", "Value")] + metrics + [("", "")] + mc + [("", "")] + [("FLAG", f_) for f_ in flags]:
            ws.append(list(row))
        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 70
        eq = wb.create_sheet("Equity")
        eq.append(["Trade", "PnL", "Equity"])
        e = o.initial
        for i, p in enumerate(pnl, 1):
            e += p
            eq.append([i, round(p, 2), round(e, 2)])
        wb.save(o.xlsx)
        print(o.xlsx)


if __name__ == "__main__":
    main()
