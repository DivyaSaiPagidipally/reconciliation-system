"""Field-level comparison for matched transaction pairs.

The result object produced here is what powers the "Differences" table on the
transaction detail screen (PRD section 13). Every compared field is always
emitted — fields that agree simply carry ``within_tolerance=True`` — so the
UI can render the full comparison table.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from .normalization import normalize_side

# Compared in this canonical order (deterministic).
_COMPARED_FIELDS = (
    "instrument",
    "side",
    "quantity",
    "price",
    "amount",
    "transaction_time",
)


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
    """Output of comparing two matched transactions field-by-field."""

    differences: list = field(default_factory=list)

    @property
    def all_match(self) -> bool:
        return all(d.within_tolerance for d in self.differences)

    def to_dict(self) -> list:
        return [d.to_dict() for d in self.differences]


def _money(v: Decimal) -> str:
    return f"{v:,.6f}".rstrip("0").rstrip(".")


def _signed(value: str) -> str:
    if value.startswith("-"):
        return value
    return f"+{value}"


def _seconds_to_human(seconds) -> str:
    """Format a whole-seconds delta as e.g. '3m', '1h5m' (rounds toward zero)."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{sign}{hours}h{minutes}m"
    if minutes:
        return f"{sign}{minutes}m"
    return f"{sign}{secs}s"


def _format_time(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def compare_transactions(int_tx, ext_tx, rules) -> ComparisonResult:
    """Compare two canonical transactions field-by-field.

    A field is 'within tolerance' when identical, or when its numeric/time
    delta falls inside the configured tolerance. Sides are normalized before
    comparison so BUY vs B counts as equal (PRD section 8).
    """
    diffs = []

    # Instrument (case-insensitive exact).
    inst_i = str(int_tx.instrument).strip().lower() if int_tx.instrument else ""
    inst_e = str(ext_tx.instrument).strip().lower() if ext_tx.instrument else ""
    diffs.append(
        FieldDifference(
            "instrument",
            str(int_tx.instrument),
            str(ext_tx.instrument),
            "",
            inst_i == inst_e,
        )
    )

    # Side (normalized — BUY/B/PURCHASE all become BUY).
    diff_side = False
    try:
        diff_side = normalize_side(int_tx.side) != normalize_side(ext_tx.side)
    except Exception:
        diff_side = str(int_tx.side) != str(ext_tx.side)
    diffs.append(
        FieldDifference("side", str(int_tx.side), str(ext_tx.side), "", not diff_side)
    )

    # Quantity (exact per MVP tolerance).
    try:
        qty_delta = abs(int_tx.quantity - ext_tx.quantity)
        qty_ok = qty_delta <= abs(rules.quantity_tolerance)
        qty_str = str(qty_delta.quantize(Decimal("1e-6")).normalize())
    except Exception:
        qty_str = "—"
        qty_ok = False
    diffs.append(
        FieldDifference(
            "quantity",
            _money(int_tx.quantity),
            _money(ext_tx.quantity),
            qty_str,
            qty_ok,
        )
    )

    # Price.
    try:
        price_delta = ext_tx.price - int_tx.price
        price_ok = abs(price_delta) <= abs(rules.amount_tolerance)
        price_str = _signed(_money(abs(price_delta)))
    except Exception:
        price_str = "—"
        price_ok = False
    diffs.append(
        FieldDifference("price", _money(int_tx.price), _money(ext_tx.price), price_str, price_ok)
    )

    # Amount.
    try:
        amount_delta = ext_tx.amount - int_tx.amount
        amount_ok = abs(amount_delta) <= abs(rules.amount_tolerance)
        amount_str = _signed(_money(abs(amount_delta)))
    except Exception:
        amount_str = "—"
        amount_ok = False
    diffs.append(
        FieldDifference(
            "amount", _money(int_tx.amount), _money(ext_tx.amount), amount_str, amount_ok
        )
    )

    # Time.
    try:
        time_delta = (ext_tx.transaction_time - int_tx.transaction_time).total_seconds()
        time_ok = abs(time_delta) <= rules.time_tolerance.total_seconds()
        time_str = _seconds_to_human(time_delta)
    except Exception:
        time_str = "—"
        time_ok = False
    diffs.append(
        FieldDifference(
            "transaction_time",
            _format_time(int_tx.transaction_time),
            _format_time(ext_tx.transaction_time),
            time_str,
            time_ok,
        )
    )

    # Stable canonical order.
    order = {name: i for i, name in enumerate(_COMPARED_FIELDS)}
    diffs.sort(key=lambda d: order.get(d.field_name, 99))
    return ComparisonResult(differences=diffs)