"""Matching rules and central tolerance configuration.

Tolerances are defined here so they live in one place rather than being
scattered through the matching and comparison code. They are overridable per
run by passing a ``Rules`` instance into the reconciliation engine.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

# Default tolerances (PRD section 11).
MATCH_TIME_TOLERANCE = timedelta(minutes=5)
AMOUNT_TOLERANCE = Decimal("0.01")

# Cancelled transactions never participate in reconciliation (PRD section 9).
CANCELLED = "CANCELLED"

# Canonical sides.
BUY = "BUY"
SELL = "SELL"

# Candidate scoring weights (PRD section 28).
SCORE_INSTRUMENT = 30
SCORE_SIDE = 20
SCORE_QUANTITY = 20
SCORE_TIME = 20
SCORE_AMOUNT = 10
MIN_FUZZY_SCORE = 60


@dataclass(frozen=True)
class Rules:
    """Configuration for one reconciliation run.

    All values have sensible MVP defaults, defined centrally so the engine
    itself never hardcodes a tolerance.
    """

    time_tolerance: timedelta = MATCH_TIME_TOLERANCE
    amount_tolerance: Decimal = AMOUNT_TOLERANCE
    quantity_tolerance: Decimal = Decimal("0")
    id_exact_match: bool = True
    fuzzy_matching: bool = True
    score_instrument: int = SCORE_INSTRUMENT
    score_side: int = SCORE_SIDE
    score_quantity: int = SCORE_QUANTITY
    score_time: int = SCORE_TIME
    score_amount: int = SCORE_AMOUNT
    min_fuzzy_score: int = MIN_FUZZY_SCORE
    # Deterministic tie-break: the external transaction whose ID sorts first
    # wins. Keeps identical inputs producing identical outputs (PRD 30).
    tie_break: str = "id"

    def describe(self) -> dict:
        """Human-readable summary of the rules, for the run record."""
        return {
            "time_tolerance_seconds": int(self.time_tolerance.total_seconds()),
            "amount_tolerance": str(self.amount_tolerance),
            "quantity_tolerance": str(self.quantity_tolerance),
            "id_exact_match": self.id_exact_match,
            "fuzzy_matching": self.fuzzy_matching,
            "min_fuzzy_score": self.min_fuzzy_score,
        }


@dataclass(frozen=True)
class RulesValidationError(ValueError):
    """Raised when a `Rules` instance has an invalid configuration."""

    message: str = ""

    def __str__(self) -> str:
        return self.message


def default_rules() -> Rules:
    return Rules()