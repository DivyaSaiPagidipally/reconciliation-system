"""Unit tests for the reconciliation matching engine.

Covers the PRD section 29 scenario table and the matching rules
(exact ID, fuzzy score, cancelled exclusion, manual resolution overrides).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from engine import reconcile
from engine.matching import ManualResolution
from engine.normalization import Transaction
from engine.rules import Rules
from engine.status import MatchMethod, ReconciliationStatus


def _tx(
    source,
    tx_id,
    time="2026-09-07 09:15:00",
    instrument="BTC-USD",
    side="BUY",
    quantity="0.5",
    price="62000",
    amount="31000",
    status="SETTLED",
):
    return Transaction(
        source=source,
        source_transaction_id=tx_id,
        transaction_time=datetime.fromisoformat(time).replace(tzinfo=timezone.utc),
        instrument=instrument,
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        amount=Decimal(amount),
        status=status,
    )


def _statuses(result):
    return [r.status for r in result.results]


class TestExactIDMatch:
    def test_same_id_is_matched(self):
        internal = [_tx("INTERNAL", "T-1001")]
        external = [_tx("EXTERNAL", "T-1001")]
        out = reconcile(internal, external)
        r = out.results[0]
        assert r.status == ReconciliationStatus.MATCHED
        assert r.match_method == MatchMethod.ID
        assert out.matched_count == 1

    def test_id_match_case_insensitive(self):
        internal = [_tx("INTERNAL", "AB-1")]
        external = [_tx("EXTERNAL", "ab-1")]
        out = reconcile(internal, external)
        assert out.results[0].status == ReconciliationStatus.MATCHED


class TestDiscrepancy:
    def test_amount_difference_is_discrepancy(self):
        internal = [_tx("INTERNAL", "T-1002", amount="34000", time="2026-09-07 10:00:00")]
        external = [_tx("EXTERNAL", "T-1002", amount="34170", time="2026-09-07 10:03:00")]
        out = reconcile(internal, external)
        assert out.results[0].status == ReconciliationStatus.DISCREPANCY
        assert out.discrepancy_count == 1
        # Field-level differences recorded.
        diffs = out.results[0].field_differences
        amount_diff = next(d for d in diffs if d.field_name == "amount")
        assert amount_diff.within_tolerance is False

    def test_timestamp_drift_within_tolerance_is_matched(self):
        internal = [_tx("INTERNAL", "T-1003", time="2026-09-07 10:00:00")]
        external = [_tx("EXTERNAL", "T-1003", time="2026-09-07 10:03:00")]
        out = reconcile(internal, external)
        assert out.results[0].status == ReconciliationStatus.MATCHED


class TestLargeTimestampDifference:
    def test_over_tolerance_is_discrepancy(self):
        internal = [_tx("INTERNAL", "T-1004", time="2026-09-07 10:00:00")]
        external = [_tx("EXTERNAL", "T-1004", time="2026-09-07 10:30:00")]
        out = reconcile(internal, external)
        assert out.results[0].status == ReconciliationStatus.DISCREPANCY
        time_diff = next(d for d in out.results[0].field_differences if d.field_name == "transaction_time")
        assert time_diff.within_tolerance is False


class TestUnmatched:
    def test_internal_only(self):
        internal = [_tx("INTERNAL", "T-1010")]
        out = reconcile(internal, [])
        assert out.results[0].status == ReconciliationStatus.UNMATCHED_INTERNAL
        assert out.unmatched_internal_count == 1

    def test_external_only(self):
        external = [_tx("EXTERNAL", "X-9001")]
        out = reconcile([], external)
        assert out.results[0].status == ReconciliationStatus.UNMATCHED_EXTERNAL
        assert out.unmatched_external_count == 1


class TestCancelled:
    def test_cancelled_are_excluded(self):
        internal = [_tx("INTERNAL", "T-1015", status="CANCELLED")]
        external = [_tx("EXTERNAL", "T-1015", status="CANCELLED")]
        out = reconcile(internal, external)
        assert out.results == []
        assert out.cancelled_count == 2
        assert out.summary()["cancelled"] == 2


class TestDifferentRepresentations:
    def test_buy_b_and_amount_tolerance(self):
        internal = [_tx("INTERNAL", "T-1020", side="BUY", amount="31000.00")]
        external = [_tx("EXTERNAL", "T-1020", side="B", amount="31000.01")]
        out = reconcile(internal, external)
        assert out.results[0].status == ReconciliationStatus.MATCHED


class TestFuzzyMatch:
    def test_ids_differ_but_transactions_match(self):
        internal = [
            _tx(
                "INTERNAL",
                "L-2001",
                time="2026-09-07 09:15:00",
                instrument="BTC-USD",
                side="BUY",
                quantity="0.5",
                amount="31000",
            )
        ]
        external = [
            _tx(
                "EXTERNAL",
                "EXT-7812",
                time="2026-09-07 09:15:03",
                instrument="BTC-USD",
                side="BUY",
                quantity="0.5",
                amount="31000",
            )
        ]
        out = reconcile(internal, external)
        assert out.results[0].status == ReconciliationStatus.MATCHED
        assert out.results[0].match_method == MatchMethod.FUZZY

    def test_fuzzy_ignores_outside_tolerance_candidates(self):
        # 3-hour time gap exceeds the 5-minute tolerance and different amount.
        internal = [_tx("INTERNAL", "L-3001", time="2026-09-07 09:00:00", amount="1000")]
        external = [_tx("EXTERNAL", "EXT-9000", time="2026-09-07 12:00:00", amount="9999")]
        out = reconcile(internal, external)
        assert out.results[0].status == ReconciliationStatus.UNMATCHED_INTERNAL
        assert out.unmatched_internal_count == 1


class TestDeterminism:
    def test_same_input_same_output(self):
        internal = [_tx("INTERNAL", "L-2001", amount="31000")]
        external = [
            _tx("EXTERNAL", "EXT-7812", amount="31000"),
            _tx("EXTERNAL", "EXT-7813", amount="31000"),
        ]
        first = reconcile(internal, external)
        second = reconcile(internal, external)
        ids1 = [(r.internal_id, r.external_id) for r in first.results]
        ids2 = [(r.internal_id, r.external_id) for r in second.results]
        assert ids1 == ids2


class TestManualResolution:
    def test_manual_match_overrides_unmatched(self):
        internal = [_tx("INTERNAL", "L-1010", amount="15500", time="2026-09-07 09:30:00")]
        external = [
            _tx("EXTERNAL", "X-5012", amount="15500", time="2026-09-07 09:32:00", side="BUY")
        ]
        manual = [
            ManualResolution(
                internal_id="L-1010",
                external_id="X-5012",
                resolution_type="MATCH",
                reason="manual",
            )
        ]
        out = reconcile(internal, external, manual_results=manual)
        assert out.results[0].status == ReconciliationStatus.MANUALLY_MATCHED
        assert out.results[0].match_method == MatchMethod.MANUAL

    def test_accepted_unmatched(self):
        external = [_tx("EXTERNAL", "X-9008", amount="1234")]
        manual = [
            ManualResolution(
                internal_id=None,
                external_id="X-9008",
                resolution_type="ACCEPT_UNMATCHED_EXTERNAL",
                reason="Late settlement",
            )
        ]
        out = reconcile([], external, manual_results=manual)
        assert out.results[0].status == ReconciliationStatus.ACCEPTED_UNMATCHED
        assert out.summary()["accepted_unmatched"] == 1


class TestSummary:
    def test_summary_counts(self):
        internal = [_tx("INTERNAL", "T-1001"), _tx("INTERNAL", "T-1002", amount="34000", time="2026-09-07 10:00:00")]
        external = [
            _tx("EXTERNAL", "T-1001"),
            _tx("EXTERNAL", "T-1002", amount="34170", time="2026-09-07 10:03:00"),
        ]
        out = reconcile(internal, external)
        s = out.summary()
        assert s["matched"] == 1
        assert s["discrepancies"] == 1
        assert s["internal_count"] == 2
        assert s["external_count"] == 2