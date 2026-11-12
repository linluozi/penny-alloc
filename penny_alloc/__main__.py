"""CLI: python -m penny_alloc TOTAL WEIGHT... [--shares ...] [--json]."""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction

from .core import AllocationError, allocate, audit, describe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="penny_alloc",
        description="Allocate integer minor units proportionally (largest remainder).",
    )
    parser.add_argument("total", type=int, help="total minor units, e.g. 100 for $1.00")
    parser.add_argument("weights", nargs="+", help="non-negative ints or fractions a/b")
    parser.add_argument("--shares", nargs="+", type=int, help="audit these shares instead of allocating")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        weights = [Fraction(w) for w in args.weights]
        if args.shares is None:
            shares = allocate(args.total, weights)
        else:
            shares = args.shares
        violations = audit(args.total, weights, shares)
    except (AllocationError, ValueError, ZeroDivisionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        payload = {
            "total": args.total,
            "shares": list(shares),
            "exact": [str(q) for q in describe(args.total, weights)] if args.shares is None else None,
            "audit": violations,
        }
        print(json.dumps(payload, indent=2))
    else:
        print("shares: " + " ".join(str(s) for s in shares))
        if args.shares is None:
            for row in describe(args.total, weights):
                print(f"  [{row['index']}] exact={row['exact']} -> {row['allocated']}")
        if violations:
            for violation in violations:
                print(f"AUDIT FAIL: {violation}", file=sys.stderr)
        else:
            print("audit: OK")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
