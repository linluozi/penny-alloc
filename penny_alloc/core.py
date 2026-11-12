"""Exact proportional allocation of integer minor units.

Split 100 cents across weights [1, 1, 1] and someone must get the extra cent.
``penny_alloc`` makes the rule explicit (largest remainder, ties by index) and
returns an auditable answer: the sum is exact and every share is within one
minor unit of its exact rational quota.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Sequence, Union

# Union[...] (not int | Fraction) keeps the package importable on Python 3.9.
Number = Union[int, Fraction, Decimal]


class AllocationError(ValueError):
    """Invalid total, weights, or shares."""


def _exact(value: Number, name: str) -> Fraction:
    if isinstance(value, bool):
        raise AllocationError(f"{name} must be a number, not bool")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise AllocationError(f"{name} must be finite")
        return Fraction(value)
    raise AllocationError(f"{name} must be int, Fraction or Decimal, got {type(value).__name__}")


def _validate(total: int, weights: Sequence[Number]) -> tuple[Fraction, list[Fraction]]:
    if isinstance(total, bool) or not isinstance(total, int):
        raise AllocationError("total must be an int (minor units)")
    if total < 0:
        raise AllocationError("total must be non-negative")
    if not weights:
        raise AllocationError("weights must not be empty")
    exact_weights = [_exact(w, f"weights[{i}]") for i, w in enumerate(weights)]
    for i, w in enumerate(exact_weights):
        if w < 0:
            raise AllocationError(f"weights[{i}] must be non-negative")
    denominator = sum(exact_weights, Fraction(0))
    if denominator == 0:
        raise AllocationError("at least one weight must be positive")
    return denominator, exact_weights


def quotas(total: int, weights: Sequence[Number]) -> list[Fraction]:
    """Return the exact rational share for each weight."""
    denominator, exact_weights = _validate(total, weights)
    return [Fraction(total) * w / denominator for w in exact_weights]


def allocate(total: int, weights: Sequence[Number]) -> list[int]:
    """Allocate ``total`` minor units proportionally.

    Guarantees, for every returned share ``s_i`` and exact quota ``q_i``:

    * ``sum(s) == total`` and every ``s_i >= 0``;
    * ``floor(q_i) <= s_i <= ceil(q_i)``;
    * deterministic: largest remainder first, ties by original index.
    """
    exact_shares = quotas(total, weights)
    floors = [q.numerator // q.denominator for q in exact_shares]
    remaining = total - sum(floors)
    if remaining < 0 or remaining > len(exact_shares):
        raise AllocationError("internal invariant violated: remainder out of range")

    order = sorted(
        range(len(exact_shares)),
        key=lambda i: (-(exact_shares[i] - floors[i]), i),
    )
    result = list(floors)
    for i in order[:remaining]:
        result[i] += 1
    return result


def describe(total: int, weights: Sequence[Number]) -> list[dict]:
    """Return per-share evidence: exact quota, floor, remainder, allocation."""
    exact_shares = quotas(total, weights)
    shares = allocate(total, weights)
    return [
        {
            "index": i,
            "exact": str(q),
            "floor": q.numerator // q.denominator,
            "remainder": str(q - (q.numerator // q.denominator)),
            "allocated": shares[i],
        }
        for i, q in enumerate(exact_shares)
    ]


def audit(total: int, weights: Sequence[Number], shares: Sequence[int]) -> list[str]:
    """Return every violated invariant; empty list means the split is valid.

    This is an independent check: it recomputes quotas from the inputs and
    does not call :func:`allocate`.
    """
    violations: list[str] = []
    try:
        exact_shares = quotas(total, weights)
    except AllocationError as exc:
        return [f"invalid input: {exc}"]

    if len(shares) != len(exact_shares):
        return [f"expected {len(exact_shares)} shares, got {len(shares)}"]
    for i, share in enumerate(shares):
        if isinstance(share, bool) or not isinstance(share, int):
            violations.append(f"share[{i}] is not an int")
        elif share < 0:
            violations.append(f"share[{i}] is negative")
    if violations:
        return violations

    if sum(shares) != total:
        violations.append(f"sum is {sum(shares)}, expected {total}")
    for i, (share, q) in enumerate(zip(shares, exact_shares)):
        low = q.numerator // q.denominator
        high = low if q.denominator == 1 else low + 1
        if not (low <= share <= high):
            violations.append(
                f"share[{i}]={share} outside quota [{low}, {high}] (exact {q})"
            )
    return violations
