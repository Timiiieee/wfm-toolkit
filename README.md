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
- Applies the two real-world planning levers WFM teams add on top of raw
  Erlang-C: a **max-occupancy cap** and a **shrinkage** uplift to scheduled
  headcount (see below).
- Produces a full-day staffing plan from interval-level call data.
- Exports an interactive `.xlsx` where the Erlang-C model lives as Excel
  formulas: change the inputs, and the recommended staffing and charts
  recalculate instantly.
- Ships with a validated engine (recursive Erlang-B/C cross-checked against an
  independent direct-formula implementation), and reconciles to the decimal with
  the public Call Centre Helper Erlang calculator.

## WFM concepts (the math)

**Offered load (Erlangs):** `A = (calls in interval * average handle time) / interval length`. One Erlang is one agent-hour of work per hour.

**Erlang-B** gives the probability a call is blocked in a no-queue system; it is the numerically stable building block (computed iteratively) for Erlang-C.

**Erlang-C** gives the probability an arriving call has to wait (all agents busy). It is the standard inbound-staffing model and is only valid when occupancy `rho = A / agents < 1`.

**Service level:** the fraction of calls answered within a target time `t`:
`SL = 1 - C * exp(-(agents - A) * (t / AHT))`. "80/20" means 80% of calls answered within 20 seconds.

**Occupancy:** `rho = A / agents`. The share of time agents are busy. High occupancy looks efficient but burns agents out and is fragile to volume spikes.

**ASA:** average speed of answer, the mean wait across all calls.

The core trade-off this tool makes visible: adding agents raises service level but lowers occupancy. Staffing is choosing the right point on that curve.

**Max-occupancy cap:** raw Erlang-C will happily run agents at 90%+ occupancy, which burns people out and degrades handle time. WFM teams cap occupancy (commonly ~85%) and add agents until the cap is respected. That uplift is *why* the achieved service level often sits above the stated target.

**Shrinkage:** Erlang-C gives agents that must be *on the phone*; people are not on the phone 100% of paid time (breaks, lunch, training, meetings, sick time, unplanned aux). Shrinkage is that lost fraction, and scheduled headcount is `on-phone / (1 - shrinkage)`. At 30% shrinkage, 38 on-phone agents means ~54 scheduled.

Erlang-C itself assumes callers never abandon (no hang-ups while queued); modeling abandonment is the job of **Erlang-A**, the natural extension of this engine.

## Install

```bash
pip install -r requirements.txt   # only dependency: openpyxl
```

Requires Python 3.8+.

## Usage

```bash
# 1. Generate a realistic day of synthetic interval data
python3 data/generate_synthetic.py

# 2. Build a staffing plan
#    defaults: 80% SL within 20s, 30-min intervals, 85% max occupancy, 30% shrinkage
python3 staffing.py --data data/sample_intervals.csv

# tune the target and the planning levers:
python3 staffing.py --data data/sample_intervals.csv --sl 0.90 --target-sec 30
python3 staffing.py --data data/sample_intervals.csv --shrinkage 0.35 --max-occupancy 0.90
python3 staffing.py --data data/sample_intervals.csv --max-occupancy 1.0  # disable the cap

# 3. Build the interactive Excel workbook
python3 excel_export.py
# -> open output/staffing_model.xlsx, edit the yellow input cells
```

## The interactive workbook (no code required)

`output/staffing_model.xlsx` is the model as live Excel formulas. Open it and
edit the highlighted input cells (calls per interval, average handle time,
target service level, answer-within time, max occupancy, shrinkage). The
**recommended on-phone agents**, service level, occupancy, ASA, **scheduled
headcount**, and both charts recalculate automatically. It is meant to be usable
by anyone, no Python needed.

## Sample output

```
Interval  Calls   AHT  Load(E)  OnPhone      SL    Occ  ASA(s)   Sched
   14:00    245   227    30.90       37   87.7%    84%     7.8    52.9
   15:00    229   248    31.55       38   88.5%    83%     7.4    54.3
   ...
OnPhone = agents required on the phone (85% max-occupancy cap applied).
Sched   = scheduled headcount after 30% shrinkage (OnPhone / (1 - shrinkage)).
Peak staffing: 38 on phone at 15:00 (229 calls, 31.6 Erlangs)
```

### Reconciliation with the industry calculator

For 240 calls, 240s AHT, a 30-min interval, an 80%/20s target, an 85% occupancy
cap, and 30% shrinkage, this toolkit returns **38 on-phone agents** (86.4%
service level, 84.2% occupancy, 8.9s ASA) and **~54 scheduled**, matching the
public [Call Centre Helper Erlang calculator](https://www.callcentrehelper.com/tools/erlang-calculator/)
to the decimal.

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
