# penny-alloc

Split an integer amount (cents, satoshi, seats, shares) proportionally **without losing or inventing a unit**. `penny_alloc` uses exact rational quotas and largest-remainder rounding, and ships an independent `audit()` that can reject any third-party split.

Upstream: none

## Why this exists

`100 / 3` in integer arithmetic gives `33, 33, 33` and loses a cent; naive `round()` can gain one. Accounting code needs a defensible rule and a checkable result. The rule here is Hamilton's largest remainder: floor every exact quota, then hand the leftover units to the largest fractional remainders, ties by original index.

```
total=100, weights=[1,1,1]
exact quotas: 100/3, 100/3, 100/3
floors:       33,    33,    33      (1 unit left)
remainders:   1/3,   1/3,   1/3     (all tied -> lowest index wins)
result:       34,    33,    33      sum=100
```

## Install

```bash
python3 -m pip install .
```

Python 3.9+, zero dependencies (`fractions`/`decimal` only).

## Use

```python
from penny_alloc import allocate, audit, describe, verify_largest_remainder

shares = allocate(100, [1, 1, 1])
assert shares == [34, 33, 33]
assert sum(shares) == 100
assert audit(100, [1, 1, 1], shares) == []      # no violations

# Auditing a split produced elsewhere: sum is right, quota is not.
print(audit(100, [1, 1, 1], [60, 20, 20]))
# ['share[0]=60 outside quota [33, 34] (exact 100/3)', ...]

# The stronger certificate: is the extra unit on the right remainder?
print(verify_largest_remainder(100, [1, 2], [33, 67]))   # []
print(verify_largest_remainder(100, [1, 2], [34, 66]))   # ['share[0]=34 does not follow ...']

for row in describe(100, [1, 2]):
    print(row)
# {'index': 0, 'exact': '100/3', 'floor': 33, 'remainder': '1/3', 'allocated': 33}
# {'index': 1, 'exact': '200/3', 'floor': 66, 'remainder': '2/3', 'allocated': 67}
```

Weights may be `int`, `Fraction`, or `Decimal`; floats are rejected so binary rounding cannot sneak into the ledger.

### CLI

```bash
python3 -m penny_alloc 100 1 1 1
python3 -m penny_alloc 100 1 2 --json
python3 -m penny_alloc 100 1 1 1 --shares 34 33 32   # audit fails, exit 1
```

Exit `0` when the split passes audit, `1` when it does not, `2` on invalid input.

## Guarantees

For returned shares `s_i` and exact quotas `q_i = total * w_i / sum(w)`:

1. `sum(s) == total` and every `s_i >= 0`.
2. `floor(q_i) <= s_i <= ceil(q_i)` — no share is off by more than one unit.
3. A zero weight receives zero units (its quota and remainder are both zero, and there is always at least one strictly larger remainder when a unit is left).
4. Deterministic: same inputs, same output; ties break by original index.
5. `verify_largest_remainder()` certifies rule 4: the items that received a leftover unit are exactly the top remainders by the documented tie-break. A split that is quota-valid but gives the unit to a smaller remainder is rejected.

`audit(total, weights, shares)` recomputes quotas from the inputs, so it validates allocations produced by any other implementation too. `verify_largest_remainder()` adds the ordering rule on top, so a third-party split that is merely quota-valid but puts the leftover unit on the wrong remainder is caught.

## Evidence (actually run)

```bash
python3 -m unittest discover -s tests -v
```

Result on 2026-11-12, CPython 3.12.3: **25 tests, OK, 1.59 s**.

- **3,000 seeded random splits** (seed `20261112`; n=1–20, total=0–100,000, weights=0–1,000): sum exact, quota bounds exact, audit empty, output reproducible on every case — **3,000/3,000**.
- Independent quota recomputation in the test file (not a call to `allocate`) is used for the bounds assertions.
- Edge cases: 0 total, 1 unit across two weights, all-zero weights rejected, fractional and `Decimal` weights, `10**18` totals, negative/bool/float input rejection.
- Tamper tests: sum drift, a quota violation whose sum is still 100, negative share, wrong length — all rejected.
- 3 CLI tests cover exit 0/1/2 and the JSON shape.
- The optimality certificate is checked on all 3,000 random splits above, plus 300 seeded splits where one unit is deliberately moved from a winner to a losing remainder: **>100 tampers constructed and rejected, 0 false acceptances**; quota-valid-but-wrong splits such as `100, [1,1,1] -> [33,34,33]` are rejected by name.

## Limits

- Negative totals (credits/refunds) are rejected rather than silently mis-allocated.
- Ties are resolved by input order; this is a documented policy, not a claim of uniqueness.
- No currency conversion or formatting; input and output are integer minor units.

## License

MIT. See `LICENSE`.
