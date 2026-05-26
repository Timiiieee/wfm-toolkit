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
