"""Field-level comparison for matched transaction pairs.

The result object produced here is what powers the "Differences" table on the
transaction detail screen (PRD section 13).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class FieldDifference:
    field_name: str
    internal_value: str
    external_value: str
    difference: str
    within_tolerance: bool

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "internal_value": self.internal_value,
            "external_value": self.external_value,
            "difference": self.difference,
            "within_tolerance": self.within_tolerance,
        }


@dataclass(frozen=True)
class ComparisonResult:
    """Output of comparing two matched transactions field-by-field.

    The engine decides whether the pair is MATCHED or DISCREPANCY based on
    ``all_match``.
    """

    differences: list = field(default_factory=list)

    @property
    def all_match(self) -> bool:
        return all(d.within_tolerance for d in self.differences)

    def to_dict(self) -> dict:
        return [d.to_dict() for d in self.differences]


# Fields that are compared; anything carrying a timestamp or numeric value is
# compared against its tolerance. Within-tolerance differences count as
# "matching" per PRD section 11.
_COMPARED_FIELDS = (
    "instrument",
    "side",
    "quantity",
    "price",
    "amount",
    "transaction_time",
)


def _money(v: Decimal) -> str:
    return f"{v:,.6f}".rstrip("0").rstrip(".")


def _signed(value: str) -> str:
    if value.startswith("-"):
        return value
    return f"+{value}"


def _seconds_to_human(seconds: float) -> str:
    """Format a whole-seconds delta as e.g. '3m', '1h5m' (rounds toward zero)."""
    seconds = int(seconds)
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{sign}{hours}h{minutes}m"
    if minutes:
        return f"{sign}{minutes}m"
    return f"{sign}{secs}s"


def _format_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def compare_transactions(int_tx, ext_tx, rules) -> ComparisonResult:
    """Compare two matched canonical transactions field-by-field.

    Returns a sorted list of FieldDifference objects. A field is 'within
    tolerance' when either identical, or when its numeric-array/time delta
    falls within the configured tolerance.
    """
    str_int = str(ext_tx.instrument).strip().lower() if ext_tx.instrument else ""
    str_e = str(int_tx.instrument).strip().lower() if int_tx.instrument else ""
    diffs = []

    if str_int != str_e:
        diffs.append(FieldDifference("instrument", str(int_tx.instrument), str(ext_tx.instrument), "", False))

    if str(int_tx.side).strip().upper() != str(ext_tx.side).strip().upper():
        diffs.append(FieldDifference("side", str(int_tx.side), str(ext_tx.side), "", False))

    # Quantity: exact per MVP tolerance (default 0).
    try:
        qty_delta = abs(int_tx.quantity - ext_tx.quantity)
        qty_ok = qty_delta <= abs(rules.quantity_tolerance)
        diffs.append(
            FieldDifference(
                "quantity",
                _money(int_tx.quantity),
                _money(ext_tx.quantity),
                str(qty_delta.quantize(Decimal("1e-6")).normalize()),
                qty_ok,
            )
        )
    except (TypeError, ValueError):
        diffs.append(FieldDifference("quantity", str(int_tx.quantity), str(ext_tx.quantity), "—", False))

    # Price
    try:
        price_delta = ext_tx.price - int_tx.price
        price_ok = abs(price_delta) <= abs(rules.amount_tolerance)
        diffs.append(
            FieldDifference("price", _money(int_tx.price), _money(ext_tx.price), _signed(_money(abs(price_delta))), price_ok)
        )
    except (TypeError, ValueError):
        diffs.append(FieldDifference("price", str(int_tx.price), str(ext_tx.price), "—", False))

    # Amount
    try:
        amount_delta = ext_tx.amount - int_tx.amount
        amount_ok = abs(amount_delta) <= abs(rules.amount_tolerance)
        diffs.append(
            FieldDifference(
                "amount", _money(int_tx.amount), _money(ext_tx.amount), _signed(_money(abs(amount_delta))), amount_ok
            )
        )
    except (TypeError, ValueError):
        diffs.append(FieldDifference("amount", str(int_tx.amount), str(ext_tx.amount), "—", False))

    # Time
    try:
        time_delta = (ext_tx.transaction_time - int_tx.transaction_time).total_seconds()
        time_ok = abs(time_delta) <= rules.time_tolerance.total_seconds()
        diffs.append(
            FieldDifference(
                "transaction_time",
                _format_time(int_tx.transaction_time),
                _format_time(ext_tx.transaction_time),
                _seconds_to_human(time_delta),
                time_ok,
            )
        )
    except (TypeError, ValueError):
        diffs.append(FieldDifference("transaction_time", str(int_tx.transaction_time), str(ext_tx.transaction_time), "—", False))

    # Sort alphabetically by field name for a stable, deterministic order.
    order = {name: i for i, name in enumerate(_COMPARED_FIELDS)}
    diffs.sort(key=lambda d: order.get(d.field_name, 0))
    return ComparisonResult(differences=diffs)