from __future__ import annotations

import json
import random
import subprocess
import sys
import unittest
from decimal import Decimal
from fractions import Fraction

from penny_alloc import AllocationError, allocate, audit, describe, quotas


def exact_quota(total: int, weights: list) -> list[Fraction]:
    """Independent quota computation used by the assertions below."""
    w = [Fraction(x) for x in weights]
    denom = sum(w, Fraction(0))
    return [Fraction(total) * x / denom for x in w]


class Properties(unittest.TestCase):
    def test_three_way_tie_is_deterministic(self) -> None:
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(10, [1, 1, 1]), [4, 3, 3])

    def test_two_way_rounding(self) -> None:
        self.assertEqual(allocate(100, [1, 2]), [33, 67])
        self.assertEqual(allocate(1, [1, 1]), [1, 0])
        self.assertEqual(allocate(0, [1, 2]), [0, 0])

    def test_fraction_weights(self) -> None:
        self.assertEqual(allocate(100, [Fraction(1, 3), Fraction(2, 3)]), [33, 67])
        self.assertEqual(allocate(1, [Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)]), [1, 0, 0])

    def test_decimal_weights_are_exact(self) -> None:
        # 0.1 + 0.2 is exactly 3/10 here, not a float artefact.
        self.assertEqual(allocate(3, [Decimal("0.1"), Decimal("0.2")]), [1, 2])

    def test_zero_weight_never_receives_a_unit(self) -> None:
        for total in (0, 1, 7, 1000):
            shares = allocate(total, [0, 5, 0, 5])
            self.assertEqual(shares[0], 0)
            self.assertEqual(shares[2], 0)

    def test_huge_values_stay_exact(self) -> None:
        shares = allocate(10**18, [10**18, 1])
        self.assertEqual(sum(shares), 10**18)
        # The small weight's exact quota is 0.999... so largest-remainder
        # gives it the one leftover unit; the big share is 10**18 - 1.
        self.assertEqual(shares, [10**18 - 1, 1])
        self.assertEqual(audit(10**18, [10**18, 1], shares), [])

    def test_random_3000_splits(self) -> None:
        rng = random.Random(20261112)
        checked = 0
        for _ in range(3000):
            n = rng.randint(1, 20)
            total = rng.randint(0, 100_000)
            weights = [rng.randint(0, 1000) for _ in range(n)]
            if not any(weights):
                weights[rng.randrange(n)] = 1
            shares = allocate(total, weights)
            qs = exact_quota(total, weights)

            self.assertEqual(sum(shares), total)
            self.assertTrue(all(isinstance(s, int) and s >= 0 for s in shares))
            for share, q in zip(shares, qs):
                low = q.numerator // q.denominator
                high = low if q.denominator == 1 else low + 1
                self.assertGreaterEqual(share, low)
                self.assertLessEqual(share, high)
            self.assertEqual(audit(total, weights, shares), [])
            self.assertEqual(shares, allocate(total, weights))
            checked += 1
        self.assertEqual(checked, 3000)

    def test_describe_reports_evidence(self) -> None:
        rows = describe(100, [1, 2])
        self.assertEqual([r["allocated"] for r in rows], [33, 67])
        self.assertEqual(rows[0]["exact"], "100/3")
        self.assertEqual(rows[0]["floor"], 33)
        self.assertEqual(rows[0]["remainder"], "1/3")


class Auditing(unittest.TestCase):
    def test_audit_catches_sum_drift(self) -> None:
        self.assertTrue(audit(100, [1, 1, 1], [34, 33, 32]))

    def test_audit_catches_quota_violation_even_when_sum_matches(self) -> None:
        # Sum is correct but 60 is outside [33, 34] for the first quota.
        violations = audit(100, [1, 1, 1], [60, 20, 20])
        self.assertTrue(any("outside quota" in v for v in violations))

    def test_audit_catches_negative_and_bad_length(self) -> None:
        self.assertTrue(audit(100, [1, 1], [-1, 101]))
        self.assertTrue(audit(100, [1, 1], [100]))
        self.assertTrue(audit(100, [1, 1], [100, 0, 0]))

    def test_audit_is_independent_of_allocate(self) -> None:
        shares = allocate(7, [1, 2, 3])
        self.assertEqual(audit(7, [1, 2, 3], shares), [])
        tampered = list(shares)
        tampered[0] += 1
        self.assertNotEqual(audit(7, [1, 2, 3], tampered), [])

    def test_audit_reports_invalid_input(self) -> None:
        self.assertTrue(audit(-1, [1], [0]))
        self.assertTrue(audit(1, [], []))


class Rejections(unittest.TestCase):
    def test_bad_totals(self) -> None:
        for total in (-1, 1.5, True, "10"):
            with self.assertRaises(AllocationError):
                allocate(total, [1])  # type: ignore[arg-type]

    def test_bad_weights(self) -> None:
        for weights in ([], [0, 0], [-1, 2], [1.5], [True, 1], [Fraction(1, 2), -1]):
            with self.assertRaises(AllocationError):
                allocate(10, weights)  # type: ignore[arg-type]

    def test_non_finite_decimal(self) -> None:
        with self.assertRaises(AllocationError):
            allocate(10, [Decimal("NaN")])


class CLI(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "penny_alloc", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_allocate_exit_zero(self) -> None:
        proc = self.run_cli("100", "1", "1", "1", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["shares"], [34, 33, 33])
        self.assertEqual(payload["audit"], [])

    def test_audit_tampered_exit_one(self) -> None:
        proc = self.run_cli("100", "1", "1", "1", "--shares", "34", "33", "32", "--json")
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(json.loads(proc.stdout)["audit"])

    def test_fraction_weight_and_bad_input(self) -> None:
        ok = self.run_cli("100", "1/3", "2/3", "--json")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["shares"], [33, 67])
        self.assertEqual(self.run_cli("100", "-1").returncode, 2)
        self.assertEqual(self.run_cli("not-a-total", "1").returncode, 2)


if __name__ == "__main__":
    unittest.main()
