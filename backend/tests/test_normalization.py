"""Unit tests for the reconciliation engine's normalization layer."""
import pytest
from datetime import datetime, timezone

from engine.normalization import (
    NormalizationError,
    Transaction,
    canonical_id,
    is_cancelled,
    normalize_amount,
    normalize_datetime,
    normalize_decimal,
    normalize_quantity,
    normalize_side,
)


class TestNormalizeSide:
    def test_buy_variants(self):
        for v in ("BUY", "buy", " B ", "PURCHASE", "LONG"):
            assert normalize_side(v) == "BUY"

    def test_sell_variants(self):
        for v in ("SELL", "sell", " S ", "SALE", "SHORT"):
            assert normalize_side(v) == "SELL"

    def test_unknown_side_raises(self):
        with pytest.raises(NormalizationError):
            normalize_side("HOLD")

    def test_missing_side_raises(self):
        with pytest.raises(NormalizationError):
            normalize_side(None)


class TestNormalizeDecimal:
    def test_string_int(self):
        assert normalize_decimal("1000") == 1000

    def test_float_string_with_commas(self):
        assert normalize_decimal("1,000.50") == 1000.50

    def test_decimal_passthrough(self):
        from decimal import Decimal

        assert normalize_decimal(Decimal("3.14")) == Decimal("3.14")

    def test_float_input(self):
        from decimal import Decimal

        assert normalize_decimal(3.14) == Decimal("3.14")

    def test_invalid_raises(self):
        with pytest.raises(NormalizationError):
            normalize_decimal("abc")

    def test_empty_raises(self):
        with pytest.raises(NormalizationError):
            normalize_decimal("")


class TestNormalizeDatetime:
    def test_iso_with_z(self):
        dt = normalize_datetime("2026-09-07T09:15:00Z")
        assert dt.tzinfo is not None
        assert dt.astimezone(timezone.utc).hour == 9

    def test_space_separated_no_tz(self):
        dt = normalize_datetime("2026-09-07 09:15:03")
        assert dt.tzinfo is not None  # assumed UTC

    def test_date_only(self):
        dt = normalize_datetime("2026-09-07")
        assert dt.strftime("%H:%M:%S") == "00:00:00"

    def test_already_aware(self):
        aware = datetime(2026, 9, 7, 9, 15, tzinfo=timezone.utc)
        assert normalize_datetime(aware) == aware

    def test_invalid_raises(self):
        with pytest.raises(NormalizationError):
            normalize_datetime("not a date")


class TestCanonicalId:
    def test_case_and_whitespace(self):
        assert canonical_id("  L-1001 ") == "L-1001"
        assert canonical_id("l-1001") == "L-1001"


class TestIsCancelled:
    def test_exact(self):
        assert is_cancelled("CANCELLED")
        assert is_cancelled("cancelled")
        assert not is_cancelled("SETTLED")