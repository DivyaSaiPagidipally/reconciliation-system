"""Unit tests for field-level comparison and tolerance logic."""
from datetime import datetime, timezone
from decimal import Decimal

from engine import compare_transactions
from engine.normalization import Transaction
from engine.rules import Rules


def _t(tx_id, time, side="BUY", amount="1000", quantity="1", price="1000"):
    return Transaction(
        source="INTERNAL",
        source_transaction_id=tx_id,
        transaction_time=datetime.fromisoformat(time).replace(tzinfo=timezone.utc),
        instrument="BTC-USD",
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        amount=Decimal(amount),
        status="SETTLED",
    )


class TestComparison:
    def test_identical_transactions_no_differences(self):
        a = _t("A", "2026-09-07 09:15:00")
        b = _t("B", "2026-09-07 09:15:00")
        cmp = compare_transactions(a, b, Rules())
        assert cmp.all_match is True
        assert all(d.within_tolerance for d in cmp.differences)

    def test_amount_within_tolerance_matches(self):
        a = _t("A", "2026-09-07 09:15:00", amount="1000.00")
        b = _t("B", "2026-09-07 09:15:00", amount="1000.01")
        assert compare_transactions(a, b, Rules()).all_match is True

    def test_amount_over_tolerance_fails(self):
        a = _t("A", "2026-09-07 09:15:00", amount="1000")
        b = _t("B", "2026-09-07 09:15:00", amount="1000.5")
        assert compare_transactions(a, b, Rules()).all_match is False

    def test_time_within_tolerance_matches(self):
        a = _t("A", "2026-09-07 09:15:00")
        b = _t("B", "2026-09-07 09:19:59")
        assert compare_transactions(a, b, Rules()).all_match is True

    def test_time_over_tolerance_fails(self):
        a = _t("A", "2026-09-07 09:15:00")
        b = _t("B", "2026-09-07 09:21:00")
        assert compare_transactions(a, b, Rules()).all_match is False

    def test_side_mismatch_fails(self):
        a = _t("A", "2026-09-07 09:15:00", side="BUY")
        b = _t("B", "2026-09-07 09:15:01", side="SELL")
        assert compare_transactions(a, b, Rules()).all_match is False

    def test_quantity_exact_matching(self):
        a = _t("A", "2026-09-07 09:15:00", quantity="0.5")
        b = _t("B", "2026-09-07 09:15:01", quantity="0.6")
        cmp = compare_transactions(a, b, Rules())
        qty = next(d for d in cmp.differences if d.field_name == "quantity")
        assert qty.within_tolerance is False

    def test_custom_time_tolerance(self):
        rules = Rules(time_tolerance=__import__("datetime").timedelta(minutes=1))
        a = _t("A", "2026-09-07 09:15:00")
        b = _t("B", "2026-09-07 09:15:30")
        assert compare_transactions(a, b, rules).all_match is True
        c = _t("C", "2026-09-07 09:17:00")
        assert compare_transactions(a, c, rules).all_match is False

    def test_differences_sort_stable(self):
        a = _t("A", "2026-09-07 09:15:00")
        b = _t("B", "2026-09-07 09:20:00", amount="2000")
        cmp = compare_transactions(a, b, Rules())
        # Compared in a canonical, deterministic order.
        expected = ["instrument", "side", "quantity", "price", "amount", "transaction_time"]
        assert [d.field_name for d in cmp.differences] == expected