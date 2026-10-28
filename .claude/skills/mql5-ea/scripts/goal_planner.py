#!/usr/bin/env python3
"""Goal planner for small accounts: how likely is START -> TARGET within a period, at each risk level?
Monte Carlo of compounding trades, including the broker minimum-lot constraint.

Usage:
  goal_planner.py --capital 15 --target 1015 --months 12 --trades-per-month 20 \
                  --winrate 0.45 --rr 2.0 [--cost-r 0.05] [--trades trades.csv --risk-usd 100]
                  --min-risk-usd 2.0 [--max-risk-at-min 2] [--risks 0.5,1,2,3,5,10,20] [--runs 5000]

--min-risk-usd    money lost at the minimum lot with your typical stop (e.g. 0.01 lot, 20-pip SL on EURUSD
                  standard ≈ 2.0; on a cent account ≈ 0.02)
--max-risk-at-min same rule as the EA input InpMaxRiskAtMinLot: if min lot would risk more than this %
                  of equity the trade is skipped (0 = never allow forced min lot)
--trades CSV      bootstrap real results instead of winrate/rr (profits ÷ --risk-usd = R-multiples)
The EA stops at the target (InpEquityTarget); "lost half" = equity fell to 50% of start at any point.
"""
import argparse
import csv
import random
import statistics as st
import sys


def r_from_csv(path, risk_usd):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    keys = {k.lower().strip(): k for k in rows[0]}
    pc = next((keys[c] for c in ("profit", "p&l", "pnl", "net") if c in keys), None)
    if not pc:
        sys.exit("no profit column")
    out = []
    for r in rows:
        if any(w in " ".join(str(v).lower() for v in r.values()) for w in ("balance", "deposit", "withdraw")):
            continue
        try:
            out.append(float(str(r[pc]).replace(",", "")) / risk_usd)
        except ValueError:
            pass
    return out


def simulate(a, risk_pct, rnd, sample_r):
    eq = peak = a.capital
    mdd = 0.0
    skipped = 0
    hit = lost_half = False
    n = a.months * a.trades_per_month
    for _ in range(n):
        risk = eq * risk_pct / 100
        if risk < a.min_risk_usd:                       # broker minimum lot is bigger than our risk budget
            if a.max_risk_at_min > 0 and a.min_risk_usd / eq * 100 <= a.max_risk_at_min:
                risk = a.min_risk_usd
            else:
                skipped += 1
                continue
        r = sample_r(rnd)
        eq += risk * r
        if eq <= 0:
            eq = 0
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak if peak else 1)
        if eq <= a.capital * 0.5:
            lost_half = True
        if eq >= a.target:
            hit = True
            break
        if eq < a.min_risk_usd:                        # cannot open even the minimum lot any more
            break
    can_trade = eq * risk_pct / 100 >= a.min_risk_usd or (
        a.max_risk_at_min > 0 and eq > 0 and a.min_risk_usd / eq * 100 <= a.max_risk_at_min)
    stuck = not hit and eq < a.capital and not can_trade   # account can no longer open a trade
    return hit, lost_half, eq, mdd, skipped / n, stuck


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--capital", type=float, required=True)
    p.add_argument("--target", type=float, required=True)
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--trades-per-month", type=int, default=20)
    p.add_argument("--winrate", type=float, default=0.45)
    p.add_argument("--rr", type=float, default=2.0)
    p.add_argument("--cost-r", type=float, default=0.05, help="spread+commission per trade, in R")
    p.add_argument("--trades", default=None)
    p.add_argument("--risk-usd", type=float, default=0)
    p.add_argument("--min-risk-usd", type=float, required=True)
    p.add_argument("--max-risk-at-min", type=float, default=2.0)
    p.add_argument("--risks", default="0.5,1,2,3,5,10,20")
    p.add_argument("--runs", type=int, default=5000)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()

    if a.trades:
        if a.risk_usd <= 0:
            sys.exit("--risk-usd (money per 1R in that CSV) is required with --trades")
        rs = r_from_csv(a.trades, a.risk_usd)
        sample_r = lambda rnd: rnd.choice(rs)  # noqa: E731
        exp_r = st.mean(rs)
        src = f"bootstrap of {len(rs)} real trades"
    else:
        sample_r = lambda rnd: (a.rr if rnd.random() < a.winrate else -1.0) - a.cost_r  # noqa: E731
        exp_r = a.winrate * a.rr - (1 - a.winrate) - a.cost_r
        src = f"win rate {a.winrate:.0%}, reward:risk {a.rr:g}, cost {a.cost_r:g}R"
    n = a.months * a.trades_per_month
    mult = a.target / a.capital
    need_trade = mult ** (1 / n) - 1
    need_month = mult ** (1 / a.months) - 1
    print(f"Goal: {a.capital:,.2f} -> {a.target:,.2f} (x{mult:,.1f}) in {a.months} months, {n} trades")
    print(f"Needs +{need_month:.1%} per month compounded, +{need_trade:.2%} per trade")
    print(f"Edge model: {src} -> expectancy {exp_r:+.3f}R per trade")
    if exp_r <= 0:
        print("FLAG expectancy <= 0: no risk level can reach the goal except by luck; fix the strategy first")
    else:
        print(f"Rough risk needed: ~{need_trade / exp_r * 100:.1f}% of equity per trade (before drawdown effects)")
    first_risk = a.min_risk_usd / a.capital * 100
    print(f"Min lot risk at start: {a.min_risk_usd:g} = {first_risk:.1f}% of capital"
          + ("  <-- above limit, trades are skipped until equity grows" if a.max_risk_at_min and first_risk > a.max_risk_at_min else ""))
    print()
    print(f"{'Risk/trade':>10} {'P(goal)':>8} {'P(lost half)':>12} {'P(stuck)':>9} {'Median end':>11} {'Median maxDD':>12} {'Skipped':>8}")
    rnd = random.Random(a.seed)
    best = None
    for rp in [float(x) for x in a.risks.split(",")]:
        res = [simulate(a, rp, rnd, sample_r) for _ in range(a.runs)]
        pg = sum(r[0] for r in res) / a.runs
        pl = sum(r[1] for r in res) / a.runs
        med_end = st.median(r[2] for r in res)
        med_dd = st.median(r[3] for r in res)
        sk = st.mean(r[4] for r in res)
        ps = sum(r[5] for r in res) / a.runs
        ruin = sum(r[1] or r[5] for r in res) / a.runs
        print(f"{rp:>9g}% {pg:>8.1%} {pl:>12.1%} {ps:>9.1%} {med_end:>11,.2f} {med_dd:>12.1%} {sk:>8.0%}")
        if ruin <= 0.10 and (best is None or pg > best[1]):
            best = (rp, pg)
    print()
    if best and best[1] > 0:
        print(f"Best risk with <=10% chance of losing half or getting stuck: {best[0]:g}% -> P(goal) {best[1]:.1%}")
    else:
        print("No tested risk level reaches the goal with <=10% chance of losing half or getting stuck.")
    print("Options: longer horizon, smaller target, cent account (min-lot risk / 100), better edge "
          "(validated expectancy), or a funded/prop account. Never martingale.")


if __name__ == "__main__":
    main()
