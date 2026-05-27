"""Staffing calculator: turn interval call data into a staffing plan.

Reads an interval CSV (interval_start, calls, aht_seconds), and for each
interval computes the minimum agents needed to hit a target service level,
plus the resulting occupancy and average speed of answer (ASA).

Usage:
    python3 staffing.py --data data/sample_intervals.csv
    python3 staffing.py --data data/sample_intervals.csv --sl 0.80 --target-sec 20 --interval-min 30
"""

import argparse
import csv
import sys

import erlang


def load_intervals(path):
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        required = {"interval_start", "calls", "aht_seconds"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"CSV must have columns {sorted(required)}; got {reader.fieldnames}"
            )
        for r in reader:
            rows.append(
                (r["interval_start"], int(r["calls"]), float(r["aht_seconds"]))
            )
    return rows


def build_plan(rows, target_sl, target_seconds, interval_minutes,
               shrinkage=0.0, max_occupancy=None):
    interval_seconds = interval_minutes * 60
    plan = []
    for label, calls, aht in rows:
        a = erlang.traffic_intensity(calls, aht, interval_seconds)
        agents = erlang.required_agents(
            a, target_sl, target_seconds, aht, max_occupancy=max_occupancy)
        sl = erlang.service_level(agents, a, target_seconds, aht)
        occ = erlang.occupancy(agents, a)
        wait = erlang.asa(agents, a, aht)
        scheduled = erlang.scheduled_headcount(agents, shrinkage)
        plan.append({
            "interval": label,
            "calls": calls,
            "aht": aht,
            "load_erlangs": a,
            "agents": agents,
            "service_level": sl,
            "occupancy": occ,
            "asa_seconds": wait,
            "scheduled": scheduled,
        })
    return plan


def print_plan(plan, target_sl, shrinkage, max_occupancy):
    header = (
        f"{'Interval':>8}  {'Calls':>5}  {'AHT':>4}  {'Load(E)':>7}  "
        f"{'OnPhone':>7}  {'SL':>6}  {'Occ':>5}  {'ASA(s)':>6}  {'Sched':>6}"
    )
    print(header)
    print("-" * len(header))
    peak = max(plan, key=lambda p: p["agents"]) if plan else None
    total_agent_intervals = 0
    total_scheduled = 0.0
    for p in plan:
        total_agent_intervals += p["agents"]
        total_scheduled += p["scheduled"]
        print(
            f"{p['interval']:>8}  {p['calls']:>5}  {p['aht']:>4.0f}  "
            f"{p['load_erlangs']:>7.2f}  {p['agents']:>7}  "
            f"{p['service_level']*100:>5.1f}%  {p['occupancy']*100:>4.0f}%  "
            f"{p['asa_seconds']:>6.1f}  {p['scheduled']:>6.1f}"
        )
    print("-" * len(header))
    print(f"Target service level: {target_sl*100:.0f}% within target time")
    occ_note = (f"{max_occupancy*100:.0f}% max-occupancy cap applied"
                if max_occupancy is not None else "no occupancy cap")
    print(f"OnPhone = agents required on the phone ({occ_note}).")
    print(f"Sched   = scheduled headcount after {shrinkage*100:.0f}% shrinkage "
          f"(OnPhone / (1 - shrinkage)).")
    if peak:
        print(f"Peak staffing: {peak['agents']} on phone at {peak['interval']} "
              f"({peak['calls']} calls, {peak['load_erlangs']:.1f} Erlangs)")
    print(f"Sum of on-phone agent-intervals across the day: {total_agent_intervals}")
    print(f"Sum of scheduled agent-intervals across the day: {total_scheduled:.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="interval CSV path")
    ap.add_argument("--sl", type=float, default=0.80, help="target service level (0-1)")
    ap.add_argument("--target-sec", type=float, default=20.0,
                    help="answer-within target time, seconds")
    ap.add_argument("--interval-min", type=float, default=30.0,
                    help="interval length in minutes")
    ap.add_argument("--shrinkage", type=float, default=0.30,
                    help="fraction of paid time off the phone (breaks, training, "
                         "absence); scheduled = on-phone / (1 - shrinkage)")
    ap.add_argument("--max-occupancy", type=float, default=0.85,
                    help="occupancy ceiling; staffing is raised until a/n is at "
                         "or below this. Use 1.0 to disable the cap.")
    args = ap.parse_args()

    try:
        rows = load_intervals(args.data)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    max_occ = None if args.max_occupancy >= 1.0 else args.max_occupancy
    plan = build_plan(rows, args.sl, args.target_sec, args.interval_min,
                      shrinkage=args.shrinkage, max_occupancy=max_occ)
    print_plan(plan, args.sl, args.shrinkage, max_occ)


if __name__ == "__main__":
    main()
