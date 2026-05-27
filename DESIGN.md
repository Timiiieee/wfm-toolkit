# DESIGN: WFM Staffing Toolkit (Erlang-C Calculator)

This is the locked design contract. The independent reviewer checks the implementation against this document.

## Purpose

Compute the number of call-center agents required to hit a target service level for a given call volume and average handle time (AHT), using the Erlang-C queueing model. Demonstrate WFM capacity-planning fundamentals from first principles.

## Module boundaries

| Module | Responsibility | Depends on |
|---|---|---|
| `erlang.py` | Pure math engine. No I/O. | stdlib `math` only |
| `staffing.py` | CLI + reads interval CSV, calls engine, prints staffing table | `erlang`, stdlib `csv`, `argparse` |
| `excel_export.py` | Builds interactive `.xlsx` with live formulas + native charts | `openpyxl` |
| `data/generate_synthetic.py` | Writes realistic interval CSV (seeded) | stdlib `csv`, `random` |
| `data/load_technion.py` | Downloads + aggregates Technion call data to intervals; falls back gracefully | stdlib `urllib`, `csv` |
| `tests/test_erlang.py` | Validates engine; includes an INDEPENDENT direct-formula Erlang-C as cross-check | `erlang`, stdlib only |

## Core math (the contract)

Traffic intensity in Erlangs: `A = (calls_per_interval * AHT_seconds) / interval_seconds`

- **Erlang-B** (recursive, numerically stable):
  `B(0, A) = 1.0`
  `B(n, A) = (A * B(n-1, A)) / (n + A * B(n-1, A))`
- **Erlang-C** (probability an arriving call must wait), valid only when `rho = A/N < 1`:
  `C(N, A) = B(N, A) / (1 - rho * (1 - B(N, A)))`
- **Service level** (fraction answered within target time `t` seconds):
  `SL = 1 - C(N, A) * exp(-(N - A) * (t / AHT))`
- **Average speed of answer** (seconds): `ASA = C(N, A) * AHT / (N - A)`
- **Occupancy**: `rho = A / N`

Two planning levers WFM teams layer on top of raw Erlang-C:

- **Max-occupancy cap**: after the service-level target is met, raise N until `A/N <= max_occupancy` (commonly 0.85). Prevents the model recommending agents at burnout-level occupancy; also pushes achieved SL above target.
- **Shrinkage**: Erlang-C yields *on-phone* agents. Scheduled headcount nets up for paid-but-off-phone time: `scheduled = on_phone / (1 - shrinkage)`.

## Function signatures (`erlang.py`)

```
traffic_intensity(calls: float, aht_seconds: float, interval_seconds: float) -> float
erlang_b(n: int, a: float) -> float
erlang_c(n: int, a: float) -> float          # returns 1.0 when rho >= 1 (always waits)
service_level(n, a, target_seconds, aht_seconds) -> float   # 0.0..1.0
occupancy(n: int, a: float) -> float
asa(n, a, aht_seconds) -> float              # float('inf') when rho >= 1
required_agents(a, target_sl, target_seconds, aht_seconds, max_agents=1000,
                max_occupancy=None) -> int   # raises N to honor occupancy cap if given
scheduled_headcount(on_phone_agents: float, shrinkage: float) -> float
```

## Edge cases (must handle)

- `A == 0` (no calls): `erlang_c = 0`, `SL = 1.0`, `required_agents = 1` (you still staff a minimum of 1).
- `rho >= 1` (N <= A, understaffed): infinite wait. `erlang_c = 1.0`, `SL = 0.0`, `asa = inf`. `required_agents` search must START at `floor(A) + 1`.
- Fractional required agents: always round UP (ceil); you can't staff a fraction.
- Large N: recursion is iterative (loop), so no stack issues.

## Test plan (`tests/test_erlang.py`)

1. **Analytic anchors (exact):** `B(1,1)=0.5`, `B(2,1)=0.2`, `B(2,2)=0.4`, `B(0,A)=1`.
2. **Independent cross-check:** implement Erlang-C a SECOND way in the test via the direct Poisson-summation formula and assert the engine's recursive result matches to 1e-9 across several (N, A) pairs. Two independent implementations agreeing is the strongest correctness signal.
3. **Structural properties:** SL strictly increases with N; occupancy strictly decreases with N; `required_agents` returns the minimum N meeting target.
4. **Edge cases:** A=0; rho>=1 returns infeasible markers; ceil behavior.

## Interactive Excel design (`output/staffing_model.xlsx`)

- **Inputs** (editable cells): calls/interval, AHT sec, interval min, target SL %, target answer sec, max occupancy %, shrinkage %.
- **Staffing table**: agent counts down rows; Erlang-B computed iteratively row-over-row via live formulas; then Erlang-C, SL, occupancy per row.
- **Recommended on-phone agents** = `MAX(MINIFS(...SL>=target...), CEILING(load/max_occupancy))` so the result honors both the service-level target and the occupancy cap.
- **Scheduled headcount** = `recommended / (1 - shrinkage)`.
- **Charts**: SL-vs-agents line; occupancy-vs-agents line (openpyxl native).
- Changing any input recalculates everything (this is the non-technical interface + the JD "Advanced Excel" evidence).

## Out of scope

No pandas, no matplotlib (use native Excel charts), no web app, no commercial-WFM-tool claims anywhere.
