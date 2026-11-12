"""penny_alloc: exact proportional allocation with a quota audit."""

from .core import AllocationError, allocate, audit, describe, quotas, verify_largest_remainder

__all__ = ["AllocationError", "allocate", "audit", "describe", "quotas", "verify_largest_remainder"]
__version__ = "0.2.0"
