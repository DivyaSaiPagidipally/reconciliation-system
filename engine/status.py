"""Result types and match methods.

The reconciliation engine returns results carrying one of these statuses.
The enum values are serialized as strings and stored in the database.
"""
from enum import Enum


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY"
    UNMATCHED_INTERNAL = "UNMATCHED_INTERNAL"
    UNMATCHED_EXTERNAL = "UNMATCHED_EXTERNAL"
    MANUALLY_MATCHED = "MANUALLY_MATCHED"
    ACCEPTED_UNMATCHED = "ACCEPTED_UNMATCHED"
    # Internal bookkeeping only, never returned as a reconciliation result.
    CANCELLED = "CANCELLED"
    IGNORED = "IGNORED"


class MatchMethod(str, Enum):
    ID = "ID"
    FUZZY = "FUZZY"
    MANUAL = "MANUAL"
    NONE = "NONE"