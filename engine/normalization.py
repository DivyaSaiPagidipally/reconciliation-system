"""Normalization of provider-specific transaction data into the canonical form.

The engine only ever speaks in canonical `Transaction` objects. Providers
(CSV adapters) are responsible for mapping their own column names and value
formats into this shape — the reconciliation logic never sees provider
formats. See PRD section 8.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


class NormalizationError(ValueError):
    """Raised when a raw value cannot be normalized."""


@dataclass(frozen=True)
class Transaction:
    """Canonical transaction representation."""

    source: str  # "INTERNAL" | "EXTERNAL"
    source_transaction_id: str
    transaction_time: datetime  # timezone-aware (UTC)
    instrument: str
    side: str  # canonical: BUY | SELL
    quantity: Decimal
    price: Decimal
    amount: Decimal
    status: str  # raw status; engine checks == "CANCELLED"

    # Optional raw payload for audit/history.
    raw_data: dict = None

    def __post_init__(self):
        if self.transaction_time.tzinfo is None:
            object.__setattr__(self, "transaction_time", self.transaction_time.replace(tzinfo=timezone.utc))


_SIDE_MAP = {
    "BUY": "BUY",
    "B": "BUY",
    "PURCHASE": "BUY",
    "LONG": "BUY",
    "SELL": "SELL",
    "S": "SELL",
    "SALE": "SELL",
    "SHORT": "SELL",
}


def normalize_side(value) -> str:
    """Map provider side values to the canonical BUY/SELL (PRD section 8)."""
    if value is None:
        raise NormalizationError(f"missing side value: {value!r}")
    key = str(value).strip().upper()
    if key in _SIDE_MAP:
        return _SIDE_MAP[key]
    raise NormalizationError(f"unknown side value: {value!r}")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise NormalizationError(f"invalid numeric value: {value!r}")
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    cleaned = str(value).strip().replace(",", "")
    if cleaned == "":
        raise NormalizationError("empty numeric value")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise NormalizationError(f"invalid numeric value: {value!r}") from None


def normalize_decimal(value) -> Decimal:
    """Parse a numeric value into a Decimal (handles 1,000.50 strings)."""
    return _to_decimal(value)


_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d",
]


def normalize_datetime(value) -> datetime:
    """Parse a provider date string into a timezone-aware UTC datetime.

    Values without an explicit offset are assumed to be in UTC, which is the
    documented MVP assumption for the demo data (PRD section 8).
    """
    if hasattr(value, "strftime"):  # already a datetime/date
        dt = value
    else:
        text = str(value).strip()
        if text == "":
            raise NormalizationError("empty datetime value")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            for fmt in _DATE_FORMATS:
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise NormalizationError(f"invalid datetime value: {value!r}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_amount(value) -> Decimal:
    """Parse an amount into a Decimal (usually from a string)."""
    return _to_decimal(value)


def normalize_quantity(value) -> Decimal:
    return _to_decimal(value)


def normalize_price(value) -> Decimal:
    return _to_decimal(value)


def canonical_id(value) -> str:
    """Normalize a transaction/reference ID for comparison.

    The PRD matches Internal ``trade_id`` against External ``reference`` as-is
    (Rule 1), but files may contain IDs with different casing. We compare using
    an upper-cased, whitespace-trimmed key while still storing the original.
    """
    return str(value).strip().upper()


def is_cancelled(status) -> bool:
    return str(status).strip().upper() == "CANCELLED"