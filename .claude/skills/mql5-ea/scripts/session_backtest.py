#!/usr/bin/env python3
"""Backtest the EA's session-breakout rules on real bar data to measure the win rate
(per year, out-of-sample friendly) before compiling/testing in MT5.

Usage:
  session_backtest.py BARS.csv --data-gmt 2 [--tf 15] [--local-gmt 7] [--range 7-14] [--trade 14-22]
                      [--close 23] [--atr 14] [--sl-atr 1.5] [--tp-atr 3.0] [--spread 0.30]
                      [--max-spread 0.60] [--trades-out trades.csv] [--risk-usd 2.5]

BARS.csv: MT5 export (Ctrl+U → Bars → Export: <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> ... <SPREAD>)
          or any CSV with time/open/high/low/close columns (BID prices). M1 data is resampled to --tf.
--data-gmt  time zone of the file's timestamps (MT5 export = broker server time, e.g. 2 or 3; Dukascopy = 0)
--spread    price units added for buys / exits of sells when the file has no spread column

Mirrors the EA: range = bars opening in [range start, range end) local time; decisions at each new bar
inside the trading window using the previous closed bar; one trade per local day; entry at the bar open
(+spread for buys); SL = sl-atr × ATR, TP = tp-atr × ATR (MT5 ATR = simple average of true range,
from the previous closed bar); if SL and TP fall in the same bar, SL is assumed first (conservative);
open trade is closed at the first bar at/after --close. Results in R (1R = stop distance).
"""
import argparse
import csv
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta


def parse_time(d, t=None):
    s = (d + " " + t) if t else d
    s = s.strip().replace("/", ".").replace("-", ".").replace("T", " ")
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y.%m.%d %H:%M:%S.%f", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(f"unknown time format: {s}")


def load(path, point):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        rows = list(csv.reader(f, dialect))
    hdr = [h.strip().strip("<>").lower() for h in rows[0]]
    idx = {h: i for i, h in enumerate(hdr)}
    need = ("open", "high", "low", "close")
    if not all(k in idx for k in need):
        sys.exit(f"need open/high/low/close columns; got {hdr}")
    bars = []
    for r in rows[1:]:
        if not r or len(r) < len(hdr):
            continue
        if "date" in idx and "time" in idx:
            t = parse_time(r[idx["date"]], r[idx["time"]])
        else:
            t = parse_time(r[idx.get("time", idx.get("datetime", 0))])
        o, h, l, c = (float(r[idx[k]]) for k in need)
        sp = float(r[idx["spread"]]) * point if "spread" in idx and r[idx["spread"]] != "" else None
        bars.append([t, o, h, l, c, sp])
    bars.sort(key=lambda b: b[0])
    return bars


def resample(bars, minutes):
    if len(bars) < 2:
        return bars
    step = min((bars[i + 1][0] - bars[i][0]).total_seconds() for i in range(min(500, len(bars) - 1)))
    if step >= minutes * 60:
        return bars
    out, cur = [], None
    for t, o, h, l, c, sp in bars:
        key = t - timedelta(minutes=t.minute % minutes, seconds=t.second, microseconds=t.microsecond)
        if cur is None or cur[0] != key:
            if cur:
                out.append(cur)
            cur = [key, o, h, l, c, sp]
        else:
            cur[2], cur[3], cur[4] = max(cur[2], h), min(cur[3], l), c
            if sp is not None:
                cur[5] = max(cur[5] or 0, sp)
    out.append(cur)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("bars")
    p.add_argument("--data-gmt", type=float, required=True)
    p.add_argument("--local-gmt", type=float, default=7)
    p.add_argument("--tf", type=int, default=15, help="bar minutes")
    p.add_argument("--range", default="7-14")
    p.add_argument("--trade", default="14-22")
    p.add_argument("--close", type=int, default=23)
    p.add_argument("--atr", type=int, default=14)
    p.add_argument("--sl-atr", type=float, default=1.5)
    p.add_argument("--tp-atr", type=float, default=3.0)
    p.add_argument("--point", type=float, default=0.01, help="price per point (2-digit gold = 0.01)")
    p.add_argument("--spread", type=float, default=0.30)
    p.add_argument("--max-spread", type=float, default=0.60)
    p.add_argument("--trades-out", default=None)
    p.add_argument("--risk-usd", type=float, default=2.5, help="money per 1R for --trades-out (e.g. 2.5%% of $100)")
    a = p.parse_args()
    rs, re_ = (int(x) for x in a.range.split("-"))
    ts, te = (int(x) for x in a.trade.split("-"))
    shift = timedelta(hours=a.local_gmt - a.data_gmt)

    bars = resample(load(a.bars, a.point), a.tf)
    if len(bars) < a.atr + 10:
        sys.exit("not enough bars")
    loc = [b[0] + shift for b in bars]
    tr = [bars[0][2] - bars[0][3]] + [max(b[2], pb[4]) - min(b[3], pb[4]) for pb, b in zip(bars, bars[1:])]
    atr = [None] * len(bars)
    for i in range(a.atr - 1, len(bars)):
        atr[i] = sum(tr[i - a.atr + 1:i + 1]) / a.atr

    trades, traded_day, rng = [], set(), {}
    pos = None  # dict(dir, entry, sl, tp, day, t)
    for i in range(1, len(bars)):
        t, o, h, l, c, sp = bars[i]
        lt = loc[i]
        spread = sp if sp is not None else a.spread
        day = lt.date()
        # range accumulation (bars opening inside the range window)
        if rs <= lt.hour < re_:
            r = rng.setdefault(day, [o, h, l])
            r[1], r[2] = max(r[1], h), min(r[2], l)
        # manage open position inside this bar
        if pos:
            if lt.hour >= a.close or lt.date() != pos["day"]:
                px = o if pos["dir"] > 0 else o + spread
                res = (px - pos["entry"]) * pos["dir"] / pos["risk"]
                trades.append((pos["t"], pos["dir"], res, "time"))
                pos = None
            else:
                if pos["dir"] > 0:
                    hit_sl, hit_tp = l <= pos["sl"], h >= pos["tp"]
                else:
                    hit_sl, hit_tp = h + spread >= pos["sl"], l + spread <= pos["tp"]
                if hit_sl or hit_tp:
                    px = pos["sl"] if hit_sl else pos["tp"]
                    res = (px - pos["entry"]) * pos["dir"] / pos["risk"]
                    trades.append((pos["t"], pos["dir"], res, "sl" if hit_sl else "tp"))
                    pos = None
                continue
        # entry decision at the open of bar i using closed bar i-1
        if pos or day in traded_day or not (ts <= lt.hour < te) or lt.hour < re_ or lt.hour >= a.close:
            continue
        if day not in rng or atr[i - 1] is None or spread > a.max_spread:
            continue
        hi, lo = rng[day][1], rng[day][2]
        pc = bars[i - 1][4]
        d = 1 if pc > hi else (-1 if pc < lo else 0)
        if not d:
            continue
        traded_day.add(day)
        risk = a.sl_atr * atr[i - 1]
        entry = o + spread if d > 0 else o
        pos = {"dir": d, "entry": entry, "risk": risk, "day": day, "t": lt,
               "sl": entry - d * risk, "tp": entry + d * a.tp_atr * atr[i - 1]}
        # same-bar check after entry
        if d > 0:
            hit_sl, hit_tp = l <= pos["sl"], h >= pos["tp"]
        else:
            hit_sl, hit_tp = h + spread >= pos["sl"], l + spread <= pos["tp"]
        if hit_sl or hit_tp:
            px = pos["sl"] if hit_sl else pos["tp"]
            trades.append((lt, d, (px - entry) * d / risk, "sl" if hit_sl else "tp"))
            pos = None

    if not trades:
        sys.exit("no trades — check --data-gmt and hours")
    by_year = defaultdict(list)
    for tr_ in trades:
        by_year[tr_[0].year].append(tr_[2])

    def row(label, rs_):
        wins = [x for x in rs_ if x > 0]
        gl = -sum(x for x in rs_ if x < 0)
        pf = sum(wins) / gl if gl else float("inf")
        return f"{label:<8} {len(rs_):>6} {len(wins) / len(rs_):>8.1%} {st.mean(rs_):>+9.3f} {pf:>6.2f} {sum(rs_):>+9.1f}"

    print(f"Bars {bars[0][0]:%Y-%m-%d} → {bars[-1][0]:%Y-%m-%d} ({len(bars)} × M{a.tf}), range {a.range}, trade {a.trade}, "
          f"close {a.close} (GMT{a.local_gmt:+g}), SL {a.sl_atr}×ATR, TP {a.tp_atr}×ATR")
    print(f"{'Year':<8} {'Trades':>6} {'Win %':>8} {'Avg R':>9} {'PF':>6} {'Total R':>9}")
    for y in sorted(by_year):
        print(row(str(y), by_year[y]))
    allr = [x[2] for x in trades]
    print(row("ALL", allr))
    reasons = defaultdict(int)
    for x in trades:
        reasons[x[3]] += 1
    print("Exits:", ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())))
    be = 1 / (1 + a.tp_atr / a.sl_atr)
    print(f"Break-even win rate for {a.tp_atr / a.sl_atr:g}:1 before costs: {be:.1%}")
    if len(trades) < 100:
        print("FLAG fewer than 100 trades — win rate is not reliable yet")
    if a.trades_out:
        with open(a.trades_out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "type", "profit", "r", "exit"])
            for t, d, r, why in trades:
                w.writerow([t.strftime("%Y-%m-%d %H:%M"), "buy" if d > 0 else "sell", round(r * a.risk_usd, 2), round(r, 3), why])
        print(a.trades_out)


if __name__ == "__main__":
    main()
