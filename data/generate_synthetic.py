"""Generate a realistic day of interval-level call-center data.

Produces 30-minute intervals across an operating day with a typical inbound
arrival pattern: a morning ramp, a mid-morning peak, a lunch dip, an
early-afternoon peak, and an evening wind-down. Seeded for reproducibility.

Output columns: interval_start, calls, aht_seconds

Usage:
    python3 data/generate_synthetic.py            # writes data/sample_intervals.csv
    python3 data/generate_synthetic.py out.csv    # writes to a custom path
"""

import csv
import os
import random
import sys

SEED = 42
INTERVAL_MINUTES = 30
DAY_START_HOUR = 8
DAY_END_HOUR = 20  # exclusive

# Relative arrival weights per 30-min interval from 08:00 to 19:30.
# Shape: ramp up, mid-morning peak, lunch dip, afternoon peak, wind down.
SHAPE = [
    0.35, 0.55,   # 08:00, 08:30
    0.80, 0.95,   # 09:00, 09:30
    1.00, 0.95,   # 10:00, 10:30  (morning peak)
    0.85, 0.70,   # 11:00, 11:30
    0.55, 0.50,   # 12:00, 12:30  (lunch dip)
    0.65, 0.80,   # 13:00, 13:30
    0.92, 0.98,   # 14:00, 14:30  (afternoon peak)
    0.88, 0.75,   # 15:00, 15:30
    0.62, 0.50,   # 16:00, 16:30
    0.40, 0.30,   # 17:00, 17:30
    0.22, 0.16,   # 18:00, 18:30
    0.12, 0.09,   # 19:00, 19:30
]

PEAK_CALLS = 240          # calls in the busiest 30-min interval (before noise)
BASE_AHT = 240            # baseline average handle time, seconds
AHT_JITTER = 40           # +/- random variation in AHT by interval


def generate(path: str) -> None:
    rng = random.Random(SEED)
    n_intervals = (DAY_END_HOUR - DAY_START_HOUR) * (60 // INTERVAL_MINUTES)
    assert len(SHAPE) == n_intervals, (
        f"SHAPE has {len(SHAPE)} entries but day needs {n_intervals}"
    )

    rows = []
    for i in range(n_intervals):
        minutes = DAY_START_HOUR * 60 + i * INTERVAL_MINUTES
        hh, mm = divmod(minutes, 60)
        label = f"{hh:02d}:{mm:02d}"
        # Poisson-like volume with multiplicative noise around the shape.
        expected = SHAPE[i] * PEAK_CALLS
        noise = rng.uniform(0.88, 1.12)
        calls = max(0, int(round(expected * noise)))
        aht = max(60, int(round(BASE_AHT + rng.uniform(-AHT_JITTER, AHT_JITTER))))
        rows.append((label, calls, aht))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["interval_start", "calls", "aht_seconds"])
        w.writerows(rows)

    total = sum(r[1] for r in rows)
    print(f"Wrote {len(rows)} intervals ({total} total calls) to {path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sample_intervals.csv"
    )
    generate(out)
