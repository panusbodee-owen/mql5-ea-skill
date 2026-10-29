#!/usr/bin/env python3
"""Download Dukascopy 1-minute BID candles (UTC) into one CSV for session_backtest.py.

Usage: fetch_dukascopy.py XAUUSD 2022-01-01 2025-01-01 --out xauusd_m1.csv [--sleep 0.2]
Then:  session_backtest.py xauusd_m1.csv --data-gmt 0 --tf 15

Needs network access to datafeed.dukascopy.com. Day files are LZMA ("alone") compressed records of
24 bytes: time offset (s), four prices as integers, volume (float). The price order and scale are
auto-detected per file (high must be the max, low the min) so a format surprise fails loudly.
"""
import argparse
import lzma
import struct
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"
ORDERS = {"OCLH": (0, 1, 2, 3), "OHLC": (0, 3, 2, 1)}   # index of open, close, low, high in the record
SCALES = (1000, 100000, 100, 10)


def decode(raw, day):
    if not raw:
        return []
    data = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
    recs = [struct.unpack(">5if", data[i:i + 24]) for i in range(0, len(data) - 23, 24)]
    best = None
    for name, (io, ic, il, ih) in ORDERS.items():
        ok = all(r[1 + ih] >= max(r[1 + io], r[1 + ic], r[1 + il]) and r[1 + il] <= min(r[1 + io], r[1 + ic]) for r in recs)
        if ok:
            best = (io, ic, il, ih)
            break
    if best is None:
        raise ValueError(f"{day}: unknown record layout")
    io, ic, il, ih = best
    mid = sorted(r[1 + ic] for r in recs)[len(recs) // 2]
    scale = next((s for s in SCALES if 100 <= mid / s <= 20000), None)   # plausible price range
    if scale is None:
        raise ValueError(f"{day}: cannot infer price scale from {mid}")
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return [(base + timedelta(seconds=r[0]), r[1 + io] / scale, r[1 + ih] / scale, r[1 + il] / scale, r[1 + ic] / scale)
            for r in recs]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("symbol")
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("--out", required=True)
    p.add_argument("--sleep", type=float, default=0.2)
    a = p.parse_args()
    d, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    n_days = n_bars = 0
    with open(a.out, "w") as f:
        f.write("time,open,high,low,close\n")
        while d < end:
            if d.weekday() != 5:   # no Saturday trading
                url = URL.format(sym=a.symbol.upper(), y=d.year, m=d.month - 1, d=d.day)   # month is 0-based
                for attempt in range(4):
                    try:
                        with urllib.request.urlopen(url, timeout=30) as r:
                            raw = r.read()
                        break
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            raw = b""
                            break
                        time.sleep(2 ** attempt)
                    except urllib.error.URLError as e:
                        if attempt == 3:
                            sys.exit(f"network error for {url}: {e.reason} — is datafeed.dukascopy.com allowed?")
                        time.sleep(2 ** attempt)
                for t, o, h, l, c in decode(raw, d):
                    f.write(f"{t:%Y-%m-%d %H:%M},{o},{h},{l},{c}\n")
                    n_bars += 1
                n_days += 1
                if n_days % 50 == 0:
                    print(f"{d} … {n_bars} bars", flush=True)
                time.sleep(a.sleep)
            d += timedelta(days=1)
    print(f"{a.out}: {n_bars} one-minute bars, {n_days} days, UTC (use --data-gmt 0)")


if __name__ == "__main__":
    main()
