"""Reconciliation engine — pure business logic, framework-independent.

The engine has ZERO knowledge of Django, the HTTP layer, or the UI. It takes
canonical `Transaction` objects (produced by parsers/normalizers) and returns
reconciliation results. Persistence, the database schema, and the REST API
live exclusively in the Django app, which calls into this engine.

    CSVs -> Parsers -> CanonicalTransaction[] -> ReconcileEngine -> Results[]
                                                     ^
                                         (framework-independent)
"""
from .comparison import ComparisonResult, FieldDifference, compare_transactions
from .matching import (
    ManualResolution,
    MatchingResult,
    ReconciliationResult,
    TransactionMatchEngine,
)
from .normalization import (
    NormalizationError,
    Transaction,
    canonical_id,
    normalize_amount,
    normalize_datetime,
    normalize_decimal,
    normalize_price,
    normalize_quantity,
    normalize_side,
)
from .rules import Rules, default_rules
from .status import MatchMethod, ReconciliationStatus


def reconcile(
    internal_transactions: list,
    external_transactions: list,
    rules: Rules = None,
    manual_results: list = None,
) -> MatchingResult:
    """Convenience wrapper around the engine (PRD section 26)."""
    engine = TransactionMatchEngine(rules)
    return engine.reconcile(
        internal_transactions,
        external_transactions,
        manual_results=manual_results or [],
    )


__all__ = [
    "ComparisonResult",
    "FieldDifference",
    "ManualResolution",
    "MatchMethod",
    "MatchingResult",
    "NormalizationError",
    "ReconciliationResult",
    "ReconciliationStatus",
    "Rules",
    "Transaction",
    "TransactionMatchEngine",
    "compare_transactions",
    "canonical_id",
    "default_rules",
    "normalize_amount",
    "normalize_datetime",
    "normalize_decimal",
    "normalize_price",
    "normalize_quantity",
    "normalize_side",
    "reconcile",
]