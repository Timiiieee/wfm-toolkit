"""Erlang-C call-center staffing engine.

Pure math, no I/O. Implements the Erlang-B recursion, Erlang-C probability of
wait, service level, occupancy, average speed of answer (ASA), and a
required-agents search.

All formulas are documented in DESIGN.md and cross-checked against an
independent direct-formula implementation in tests/test_erlang.py.

Reference: Erlang-C is the standard M/M/N queueing model used in workforce
management for inbound call staffing.
"""

from __future__ import annotations

import math


def traffic_intensity(calls: float, aht_seconds: float, interval_seconds: float) -> float:
    """Offered load in Erlangs.

    A = (calls in the interval * average handle time) / interval length.
    One Erlang is one hour of work per hour (one continuously busy agent).
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    if calls < 0 or aht_seconds < 0:
        raise ValueError("calls and aht_seconds must be non-negative")
    return (calls * aht_seconds) / interval_seconds


def erlang_b(n: int, a: float) -> float:
    """Erlang-B blocking probability for n servers and offered load a (Erlangs).

    Computed with the numerically stable iterative recursion:
        B(0, a) = 1
        B(k, a) = (a * B(k-1, a)) / (k + a * B(k-1, a))
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    if a < 0:
        raise ValueError("a must be >= 0")
    b = 1.0  # B(0, a)
    for k in range(1, n + 1):
        b = (a * b) / (k + a * b)
    return b


def erlang_c(n: int, a: float) -> float:
    """Erlang-C probability that an arriving call must wait (all servers busy).

    Valid only when occupancy rho = a/n < 1. When the system is offered more
    (or equal) load than it can serve (rho >= 1), every call eventually waits,
    so we return 1.0.
    """
    if n <= 0:
        # No servers: with any positive load, all calls wait. With zero load,
        # there is nothing to wait for, but staffing zero is degenerate; treat
        # as "always wait" to keep required_agents searching upward.
        return 1.0 if a > 0 else 0.0
    rho = a / n
    if rho >= 1.0:
        return 1.0
    if a == 0:
        return 0.0
    b = erlang_b(n, a)
    return b / (1.0 - rho * (1.0 - b))


def occupancy(n: int, a: float) -> float:
    """Agent occupancy rho = a / n (fraction of time agents are busy)."""
    if n <= 0:
        return float("inf") if a > 0 else 0.0
    return a / n


def service_level(n: int, a: float, target_seconds: float, aht_seconds: float) -> float:
    """Fraction of calls answered within target_seconds (0.0..1.0).

    SL = 1 - C(n, a) * exp(-(n - a) * (target_seconds / aht))
    """
    if aht_seconds <= 0:
        raise ValueError("aht_seconds must be positive")
    if a == 0:
        return 1.0  # no calls => every (nonexistent) call is "answered" instantly
    if n <= 0:
        return 0.0
    rho = a / n
    if rho >= 1.0:
        return 0.0  # understaffed: target service level cannot be met
    c = erlang_c(n, a)
    sl = 1.0 - c * math.exp(-(n - a) * (target_seconds / aht_seconds))
    # Clamp for floating-point safety.
    return max(0.0, min(1.0, sl))


def asa(n: int, a: float, aht_seconds: float) -> float:
    """Average speed of answer in seconds. Infinite if understaffed (rho>=1)."""
    if aht_seconds <= 0:
        raise ValueError("aht_seconds must be positive")
    if a == 0:
        return 0.0
    if n <= 0:
        return float("inf")
    rho = a / n
    if rho >= 1.0:
        return float("inf")
    c = erlang_c(n, a)
    return (c * aht_seconds) / (n - a)


def required_agents(
    a: float,
    target_sl: float,
    target_seconds: float,
    aht_seconds: float,
    max_agents: int = 1000,
    max_occupancy: float | None = None,
) -> int:
    """Minimum on-phone agents so service_level >= target_sl.

    Search starts just above the offered load (floor(a) + 1), since any
    staffing at or below the load yields an unstable queue (rho >= 1).
    Returns at least 1 even when there is no load.

    If max_occupancy is given (e.g. 0.85), the result is also raised until
    occupancy (a/n) sits at or below that ceiling. Real WFM teams cap
    occupancy well under 100% because agents running flat-out burn out and
    handle times degrade; the standard ceiling is around 85%. Adding agents
    for this reason also pushes the achieved service level above target.
    """
    if not 0.0 <= target_sl <= 1.0:
        raise ValueError("target_sl must be between 0 and 1")
    if max_occupancy is not None and not 0.0 < max_occupancy <= 1.0:
        raise ValueError("max_occupancy must be in (0, 1]")
    if a == 0:
        return 1
    start = int(math.floor(a)) + 1
    for n in range(max(1, start), max_agents + 1):
        if service_level(n, a, target_seconds, aht_seconds) >= target_sl:
            # Service-level target met; now enforce the occupancy ceiling.
            if max_occupancy is not None:
                while occupancy(n, a) > max_occupancy and n < max_agents:
                    n += 1
            return n
    raise RuntimeError(
        f"Could not meet target service level {target_sl} with up to "
        f"{max_agents} agents for load {a:.2f} Erlangs"
    )


def scheduled_headcount(on_phone_agents: float, shrinkage: float) -> float:
    """Scheduled headcount needed to keep on_phone_agents actually on the phone.

    Erlang-C tells you how many agents must be on the phone in an interval, but
    agents are not on the phone 100% of paid time: breaks, lunches, training,
    meetings, coaching, sick time, and unplanned aux all subtract. That lost
    fraction is "shrinkage". To net the required on-phone count after shrinkage,
    schedule more bodies:

        scheduled = on_phone / (1 - shrinkage)

    shrinkage is a fraction in [0, 1); 0.30 (30%) is a common planning value.
    Returns a float (fractional people); round up when turning it into a roster.
    """
    if not 0.0 <= shrinkage < 1.0:
        raise ValueError("shrinkage must be in [0, 1)")
    if on_phone_agents < 0:
        raise ValueError("on_phone_agents must be >= 0")
    return on_phone_agents / (1.0 - shrinkage)
