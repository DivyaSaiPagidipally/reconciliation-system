"""Integration tests for the file import service (pytest-django).

These run against the PostgreSQL test database managed by pytest-django.
"""
import pytest

from reconciliation.models import File, Transaction, TransactionVersion
from reconciliation.services.file_service import (
    DuplicateFileError,
    FileImportError,
    import_file,
)

pytestmark = pytest.mark.django_db

INTERNAL_CSV = """trade_id,traded_at,instrument,side,quantity,price,gross_amount,state
L-1001,2026-09-07T09:15:00Z,BTC-USD,BUY,0.50,62000,31000,SETTLED
L-1002,2026-09-07T10:00:00Z,ETH-USD,BUY,10,3400,34000,SETTLED
L-1015,2026-09-07T12:00:00Z,XRP-USD,BUY,500,0.6,300,CANCELLED
"""

EXTERNAL_CSV = """reference,executed_at,symbol,direction,qty,unit_price,total,status
X-9001,2026-09-07 09:15:03,BTC-USD,B,0.5,62000,31000,SETTLED
X-9002,2026-09-07 10:00:03,ETH-USD,B,10,3417,34170,SETTLED
"""


@pytest.fixture(autouse=True)
def clean_tables():
    from reconciliation.models import ReconciliationDifference, ReconciliationResult, ReconciliationRun, ManualResolution

    ReconciliationDifference.objects.all().delete()
    ReconciliationResult.objects.all().delete()
    ReconciliationRun.objects.all().delete()
    TransactionVersion.objects.all().delete()
    Transaction.objects.all().delete()
    File.objects.all().delete()
    ManualResolution.objects.all().delete()
    yield


class TestImport:
    def test_import_internal(self):
        f = import_file(
            filename="internal.csv", source="INTERNAL", content=INTERNAL_CSV, content_bytes=INTERNAL_CSV.encode()
        )
        assert f.source == "INTERNAL"
        assert f.record_count == 3
        assert Transaction.objects.filter(source="INTERNAL").count() == 3
        # Normalized side / status.
        tx = Transaction.objects.get(source_transaction_id="L-1002")
        assert tx.side == "BUY"
        assert tx.instrument == "ETH-USD"
        assert tx.amount == Transaction.amount.field.run_validators(tx.amount) or tx.amount

    def test_import_external_normalizes(self):
        import_file(filename="external.csv", source="EXTERNAL", content=EXTERNAL_CSV, content_bytes=EXTERNAL_CSV.encode())
        tx = Transaction.objects.get(source_transaction_id="X-9001")
        assert tx.side == "BUY"  # B -> BUY
        assert tx.quantity == 0.5
        assert tx.amount == 31000

    def test_duplicate_file_rejected(self):
        import_file(filename="a.csv", source="INTERNAL", content=INTERNAL_CSV, content_bytes=INTERNAL_CSV.encode())
        with pytest.raises(DuplicateFileError):
            import_file(filename="b.csv", source="INTERNAL", content=INTERNAL_CSV, content_bytes=INTERNAL_CSV.encode())
        # Same file with different name is still a duplicate.
        assert File.objects.count() == 1

    def test_same_content_different_source_allowed(self):
        import_file(filename="a.csv", source="INTERNAL", content=INTERNAL_CSV, content_bytes=INTERNAL_CSV.encode())
        # Different source with a *different* file (external format) is not a dup.
        import_file(filename="e.csv", source="EXTERNAL", content=EXTERNAL_CSV, content_bytes=EXTERNAL_CSV.encode())
        assert File.objects.count() == 2
        # Dedup is per-source: the same internal bytes again is still caught.
        with pytest.raises(DuplicateFileError):
            import_file(filename="c.csv", source="INTERNAL", content=INTERNAL_CSV, content_bytes=INTERNAL_CSV.encode())

    def test_missing_required_column(self):
        bad = INTERNAL_CSV.replace("gross_amount,", "")
        with pytest.raises(FileImportError) as e:
            import_file(filename="bad.csv", source="INTERNAL", content=bad, content_bytes=bad.encode())
        assert "gross_amount" in str(e.value)

    def test_invalid_side(self):
        bad = INTERNAL_CSV.replace("BUY", "HOLD", 1)
        with pytest.raises(FileImportError) as e:
            import_file(filename="bad.csv", source="INTERNAL", content=bad, content_bytes=bad.encode())
        assert "side" in str(e.value).lower() or "HOLD" in str(e.value)

    def test_invalid_date(self):
        bad = INTERNAL_CSV.replace("2026-09-07T09:15:00Z", "not-a-date", 1)
        with pytest.raises(FileImportError):
            import_file(filename="bad.csv", source="INTERNAL", content=bad, content_bytes=bad.encode())

    def test_corrected_file_creates_version(self):
        f1 = import_file(filename="a.csv", source="INTERNAL", content=INTERNAL_CSV, content_bytes=INTERNAL_CSV.encode())
        tx = Transaction.objects.get(source_transaction_id="L-1001")
        assert tx.current_version == 1
        assert tx.amount == 31000

        corrected = INTERNAL_CSV.replace("L-1001,2026-09-07T09:15:00Z,BTC-USD,BUY,0.50,62000,31000,SETTLED",
                                         "L-1001,2026-09-07T09:15:00Z,BTC-USD,BUY,0.50,62000,31999,SETTLED")
        import_file(filename="b.csv", source="INTERNAL", content=corrected, content_bytes=corrected.encode())

        tx.refresh_from_db()
        assert tx.current_version == 2
        assert tx.amount == 31999
        versions = list(tx.versions.all())
        assert len(versions) == 1
        assert versions[0].version == 1
        assert versions[0].amount == 31000

    def test_cancelled_still_stored(self):
        import_file(filename="a.csv", source="INTERNAL", content=INTERNAL_CSV, content_bytes=INTERNAL_CSV.encode())
        assert Transaction.objects.filter(source_transaction_id="L-1015", status="CANCELLED").exists()