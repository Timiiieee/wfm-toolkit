"""Load and aggregate the Technion 'Anonymous Bank' call-center dataset.

The dataset (Mandelbaum et al., Technion Service Engineering) records every
call that arrived at an Israeli bank's call center during 1999, one row per
call. We aggregate it to interval-level call volume + mean handle time, which
is the input the staffing calculator expects.

Source (when reachable):
    https://ie.technion.ac.il/~serveng/course2004/callcenterdata/

Raw record format (tab-separated, no header), documented columns:
    1  vru_line     6-char VRU + line id
    2  call_id
    3  customer_id
    4  priority
    5  type         call type (PS, PE, IN, NE, NW, TT, ...)
    6  date         yymmdd
    7  vru_entry    hh:mm:ss  (when the call entered the system) <- arrival
    8  vru_exit
    9  vru_time
    10 q_start
    11 q_exit
    12 q_time
    13 outcome      AGENT | HANG | PHANTOM
    14 ser_start    hh:mm:ss
    15 ser_exit
    16 ser_time     service duration in seconds  <- handle time (AHT source)
    17 server

Usage:
    # Try the live source, aggregate to 30-min intervals:
    python3 data/load_technion.py

    # Use a file you downloaded manually:
    python3 data/load_technion.py --file path/to/199904.dat --out data/technion_intervals.csv

If the source is unreachable (it has been intermittently offline), this script
exits with a clear message. The toolkit's default dataset is the synthetic
generator (data/generate_synthetic.py), which requires no network access.
"""

import argparse
import csv
import os
import sys
import urllib.request

DEFAULT_URL = "https://ie.technion.ac.il/~serveng/course2004/callcenterdata/199904.dat"
INTERVAL_MINUTES = 30
CONNECT_TIMEOUT = 15


def _interval_label(hhmmss: str) -> str:
    """Map an 'hh:mm:ss' arrival time to its 30-min interval start label."""
    parts = hhmmss.split(":")
    hh, mm = int(parts[0]), int(parts[1])
    bucket = (mm // INTERVAL_MINUTES) * INTERVAL_MINUTES
    return f"{hh:02d}:{bucket:02d}"


def parse_records(lines):
    """Yield (arrival_label, ser_time_seconds, served) per valid record."""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) < 16:
            fields = line.split()  # some mirrors use whitespace
        if len(fields) < 16:
            continue
        vru_entry = fields[6]
        outcome = fields[12].upper()
        try:
            ser_time = float(fields[15])
        except ValueError:
            continue
        served = outcome == "AGENT" and ser_time > 0
        try:
            label = _interval_label(vru_entry)
        except (ValueError, IndexError):
            continue
        yield label, ser_time, served


def aggregate(lines):
    """Aggregate records to interval-level call volume + mean handle time."""
    counts = {}
    ser_sum = {}
    ser_n = {}
    for label, ser_time, served in parse_records(lines):
        counts[label] = counts.get(label, 0) + 1
        if served:
            ser_sum[label] = ser_sum.get(label, 0.0) + ser_time
            ser_n[label] = ser_n.get(label, 0) + 1

    rows = []
    for label in sorted(counts):
        calls = counts[label]
        aht = round(ser_sum[label] / ser_n[label]) if ser_n.get(label) else 0
        if aht <= 0:
            continue  # skip intervals with no served calls (no AHT signal)
        rows.append((label, calls, aht))
    return rows


def write_csv(rows, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["interval_start", "calls", "aht_seconds"])
        w.writerows(rows)
    total = sum(r[1] for r in rows)
    print(f"Wrote {len(rows)} intervals ({total} total calls) to {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="local raw Technion data file (skip download)")
    ap.add_argument("--url", default=DEFAULT_URL, help="source URL to download")
    ap.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "technion_intervals.csv"),
        help="output CSV path",
    )
    args = ap.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"ERROR: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", errors="ignore") as f:
            lines = f.readlines()
    else:
        print(f"Attempting download: {args.url}")
        try:
            with urllib.request.urlopen(args.url, timeout=CONNECT_TIMEOUT) as resp:
                lines = resp.read().decode("latin-1", errors="ignore").splitlines()
        except Exception as exc:  # network/HTTP/timeout
            print(
                "ERROR: could not reach the Technion dataset "
                f"({type(exc).__name__}: {exc}).\n"
                "The source is intermittently offline. Either download a monthly\n"
                "file manually and pass --file, or use the synthetic generator:\n"
                "    python3 data/generate_synthetic.py\n",
                file=sys.stderr,
            )
            sys.exit(2)

    rows = aggregate(lines)
    if not rows:
        print("ERROR: no valid records parsed (unexpected format).", file=sys.stderr)
        sys.exit(3)
    write_csv(rows, args.out)


if __name__ == "__main__":
    main()
