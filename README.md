# WFM Staffing Toolkit

A call-center staffing calculator built from first principles on the **Erlang-C**
queueing model. Given call volume and average handle time, it computes the
minimum number of agents needed to hit a target service level, and packages the
whole model as an **interactive Excel workbook** anyone can use without code.

I built this to work through workforce-management capacity planning from the
math up rather than treating a commercial tool as a black box.

## What it does

- Computes offered load, required agents, service level, occupancy, and average
  speed of answer (ASA) for any interval of call data.
- Produces a full-day staffing plan from interval-level call data.
- Exports an interactive `.xlsx` where the Erlang-C model lives as Excel
  formulas: change the inputs, and the recommended staffing and charts
  recalculate instantly.
- Ships with a validated engine (recursive Erlang-B/C cross-checked against an
  independent direct-formula implementation).

## WFM concepts (the math)

**Offered load (Erlangs):** `A = (calls in interval * average handle time) / interval length`. One Erlang is one agent-hour of work per hour.

**Erlang-B** gives the probability a call is blocked in a no-queue system; it is the numerically stable building block (computed iteratively) for Erlang-C.

**Erlang-C** gives the probability an arriving call has to wait (all agents busy). It is the standard inbound-staffing model and is only valid when occupancy `rho = A / agents < 1`.

**Service level:** the fraction of calls answered within a target time `t`:
`SL = 1 - C * exp(-(agents - A) * (t / AHT))`. "80/20" means 80% of calls answered within 20 seconds.

**Occupancy:** `rho = A / agents`. The share of time agents are busy. High occupancy looks efficient but burns agents out and is fragile to volume spikes.

**ASA:** average speed of answer, the mean wait across all calls.

The core trade-off this tool makes visible: adding agents raises service level but lowers occupancy. Staffing is choosing the right point on that curve.

## Install

```bash
pip install -r requirements.txt   # only dependency: openpyxl
```

Requires Python 3.8+.

## Usage

```bash
# 1. Generate a realistic day of synthetic interval data
python3 data/generate_synthetic.py

# 2. Build a staffing plan (defaults: 80% SL within 20s, 30-min intervals)
python3 staffing.py --data data/sample_intervals.csv

# tune the target:
python3 staffing.py --data data/sample_intervals.csv --sl 0.90 --target-sec 30

# 3. Build the interactive Excel workbook
python3 excel_export.py
# -> open output/staffing_model.xlsx, edit the yellow input cells
```

## The interactive workbook (no code required)

`output/staffing_model.xlsx` is the model as live Excel formulas. Open it and
edit the highlighted input cells (calls per interval, average handle time,
target service level, answer-within time). The **recommended agent count**,
service level, occupancy, ASA, and both charts recalculate automatically. It is
meant to be usable by anyone, no Python needed.

## Sample output

```
Interval  Calls   AHT  Load(E)  Agents      SL    Occ  ASA(s)
   14:00    245   227    30.90      36   82.0%    86%    12.5
   15:00    229   248    31.55      37   83.3%    85%    11.8
   ...
Peak staffing: 37 agents at 15:00 (229 calls, 31.6 Erlangs)
```

## Data

- **Synthetic generator** (`data/generate_synthetic.py`, default): a realistic
  inbound day (morning and early-afternoon peaks, lunch dip), seeded for
  reproducibility. No network needed.
- **Technion "Anonymous Bank" data** (`data/load_technion.py`, optional): the
  real call-center dataset from the Technion Service Engineering group
  (~1.2M calls over 1999), used in foundational Erlang-A/C queueing research.
  The loader aggregates raw per-call records to interval-level volume and mean
  handle time. The public source has been intermittently offline; if it is
  unreachable the toolkit defaults to the synthetic generator. To use a file
  downloaded manually: `python3 data/load_technion.py --file <path>`.

## Testing

```bash
python3 tests/test_erlang.py
```

The suite validates the engine three ways: exact analytic anchors for Erlang-B,
an **independent direct-formula Erlang-C** cross-check (two derivations must
agree to 1e-9), and structural properties (service level rises and occupancy
falls as agents increase). It also covers edge cases: zero load, understaffing
(`rho >= 1`), and minimal-staffing search.

## Project structure

```
erlang.py                  core engine (pure math, no I/O)
staffing.py                CLI: interval data -> staffing plan
excel_export.py            builds the interactive workbook
data/generate_synthetic.py synthetic interval generator
data/load_technion.py      real-dataset loader (optional)
tests/test_erlang.py       validation suite
DESIGN.md                  design contract + formulas
```

## Attribution

Technion "Anonymous Bank" call-center data: Mandelbaum, A., et al., Technion
Service Engineering / SEELab. Used for educational, non-commercial analysis.
