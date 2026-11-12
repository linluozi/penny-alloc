"""penny_alloc: exact proportional allocation with a quota audit."""

from .core import AllocationError, allocate, audit, describe, quotas

__all__ = ["AllocationError", "allocate", "audit", "describe", "quotas"]
__version__ = "0.1.0"
