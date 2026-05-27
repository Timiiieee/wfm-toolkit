"""Validation suite for the Erlang-C engine.

Runs with plain stdlib (no pytest required):  python3 tests/test_erlang.py

Strategy:
1. Exact analytic anchors for Erlang-B.
2. An INDEPENDENT Erlang-C implementation (direct Poisson summation) used to
   cross-check the engine's recursive result. Two independent derivations
   agreeing is the strongest correctness evidence.
3. Structural properties (monotonicity, required-agents minimality).
4. Edge cases (zero load, understaffed, ceil behavior).
"""

import math
import os
import sys

# Make the package root importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import erlang  # noqa: E402


# --- Independent reference implementation (do NOT reuse engine internals) ---

def erlang_c_direct(n: int, a: float) -> float:
    """Erlang-C via the direct Poisson-summation formula.

        C = ( a^n / n! * (n / (n - a)) )
            / ( sum_{k=0}^{n-1} a^k/k!  +  a^n/n! * (n/(n-a)) )

    Independent of the recursive erlang_b used in the engine.
    """
    if n <= 0:
        return 1.0 if a > 0 else 0.0
    if a == 0:
        return 0.0
    if a / n >= 1.0:
        return 1.0
    # Sum of Poisson terms a^k / k! for k = 0..n-1
    term = 1.0  # a^0 / 0!
    series = 1.0
    for k in range(1, n):
        term *= a / k
        series += term
    # a^n / n!  (continue the term recurrence one more step)
    top = term * (a / n)
    numerator = top * (n / (n - a))
    return numerator / (series + numerator)


# --- Tiny assertion harness ---

_failures = []


def check(name, cond):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}")
        _failures.append(name)


def approx(x, y, tol=1e-9):
    return abs(x - y) <= tol


def main():
    print("Erlang-B analytic anchors:")
    check("B(0, 5) == 1", approx(erlang.erlang_b(0, 5), 1.0))
    check("B(1, 1) == 0.5", approx(erlang.erlang_b(1, 1), 0.5))
    check("B(2, 1) == 0.2", approx(erlang.erlang_b(2, 1), 0.2))
    check("B(2, 2) == 0.4", approx(erlang.erlang_b(2, 2), 0.4))

    print("\nErlang-C engine vs independent direct formula:")
    cases = [
        (14, 10.0), (20, 15.0), (5, 3.0), (50, 42.0), (8, 7.5), (100, 80.0),
    ]
    for n, a in cases:
        engine_val = erlang.erlang_c(n, a)
        ref_val = erlang_c_direct(n, a)
        check(f"C({n}, {a}) engine≈direct ({engine_val:.6f} vs {ref_val:.6f})",
              approx(engine_val, ref_val, tol=1e-9))

    print("\nStructural properties:")
    a = 20.0
    sls = [erlang.service_level(n, a, 20, 240) for n in range(21, 40)]
    check("service level strictly increases with agents",
          all(sls[i] < sls[i + 1] for i in range(len(sls) - 1)))
    occs = [erlang.occupancy(n, a) for n in range(21, 40)]
    check("occupancy strictly decreases with agents",
          all(occs[i] > occs[i + 1] for i in range(len(occs) - 1)))

    # Behaviour right at the stability boundary (rho = 1) and just above it.
    sat = 30.0
    check("SL is 0 when understaffed (n == load, rho=1)",
          approx(erlang.service_level(30, sat, 20, 240), 0.0))
    check("SL becomes positive at first feasible staffing (n == load+1)",
          erlang.service_level(31, sat, 20, 240) > 0.0)

    print("\nrequired_agents minimality:")
    a = 10.0
    n_req = erlang.required_agents(a, 0.80, 20, 180)
    sl_at = erlang.service_level(n_req, a, 20, 180)
    sl_below = erlang.service_level(n_req - 1, a, 20, 180)
    check(f"required_agents={n_req} meets target (SL={sl_at:.4f} >= 0.80)", sl_at >= 0.80)
    check(f"one fewer agent fails target (SL={sl_below:.4f} < 0.80)", sl_below < 0.80)

    print("\nmax-occupancy cap (matches the public Erlang calculator):")
    # 240 calls, 240s AHT, 30-min interval => 32 Erlangs. Pure SL answer is 37
    # (occupancy 86.5%); an 85% cap must raise it to 38 (occupancy 84.2%).
    a32 = erlang.traffic_intensity(240, 240, 30 * 60)
    check("offered load is 32 Erlangs", approx(a32, 32.0))
    n_pure = erlang.required_agents(a32, 0.80, 20, 240)
    check(f"pure Erlang-C answer is 37 (got {n_pure})", n_pure == 37)
    check("pure answer occupancy exceeds 85%", erlang.occupancy(37, a32) > 0.85)
    n_capped = erlang.required_agents(a32, 0.80, 20, 240, max_occupancy=0.85)
    check(f"85% occupancy cap raises answer to 38 (got {n_capped})", n_capped == 38)
    check("capped answer occupancy is at or below 85%",
          erlang.occupancy(n_capped, a32) <= 0.85)
    # The capped staffing reproduces the public calculator's figures.
    check("capped SL ~ 86.4%", approx(erlang.service_level(38, a32, 20, 240), 0.864, tol=2e-3))
    check("capped occupancy ~ 84.2%", approx(erlang.occupancy(38, a32), 0.842, tol=2e-3))
    check("capped ASA ~ 8.9s", approx(erlang.asa(38, a32, 240), 8.9, tol=0.1))
    check("max_occupancy=1.0 leaves the pure answer unchanged",
          erlang.required_agents(a32, 0.80, 20, 240, max_occupancy=1.0) == 37)

    print("\nshrinkage (scheduled headcount):")
    check("38 on phone at 30% shrinkage => ~54.3 scheduled",
          approx(erlang.scheduled_headcount(38, 0.30), 38 / 0.7, tol=1e-9))
    check("0% shrinkage is a no-op", approx(erlang.scheduled_headcount(38, 0.0), 38.0))
    try:
        erlang.scheduled_headcount(10, 1.0)
        check("shrinkage=1.0 rejected", False)
    except ValueError:
        check("shrinkage=1.0 rejected", True)

    print("\nEdge cases:")
    check("A=0 => erlang_c 0", approx(erlang.erlang_c(5, 0), 0.0))
    check("A=0 => service_level 1.0", approx(erlang.service_level(5, 0, 20, 180), 1.0))
    check("A=0 => required_agents 1", erlang.required_agents(0, 0.8, 20, 180) == 1)
    check("rho>=1 => erlang_c 1.0", approx(erlang.erlang_c(10, 10.0), 1.0))
    check("rho>=1 => service_level 0.0", approx(erlang.service_level(10, 12.0, 20, 180), 0.0))
    check("rho>=1 => asa inf", math.isinf(erlang.asa(10, 12.0, 180)))
    check("traffic_intensity(100,180,1800)=10", approx(erlang.traffic_intensity(100, 180, 1800), 10.0))

    print()
    if _failures:
        print(f"FAILED: {len(_failures)} check(s): {_failures}")
        sys.exit(1)
    print("All checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
