"""Integration tests for reconciliation run endpoints (pytest-django)."""
import pytest
from django.utils import timezone

from reconciliation.models import (
    File,
    ManualResolution,
    ReconciliationDifference,
    ReconciliationResult,
    ReconciliationRun,
    Transaction,
)

pytestmark = pytest.mark.django_db


class TestDeleteRun:
    def test_delete_run_and_results(self, client):
        file = File.objects.create(filename="internal.csv", source="INTERNAL", sha256="a" * 64)
        transaction = Transaction.objects.create(
            source="INTERNAL", source_transaction_id="L-1", latest_for_source_id="L-1",
            transaction_time=timezone.now(), instrument="BTC-USD", side="BUY",
            quantity=1, price=2, amount=2, status="SETTLED", file=file,
        )
        resolution = ManualResolution.objects.create(
            internal_transaction=transaction, resolution_type="ACCEPT_UNMATCHED_INTERNAL"
        )
        run = ReconciliationRun.objects.create(internal_file=file)
        result = ReconciliationResult.objects.create(
            run=run, internal_transaction=transaction, status="UNMATCHED_INTERNAL"
        )
        difference = ReconciliationDifference.objects.create(result=result, field_name="amount")
        other_run = ReconciliationRun.objects.create(internal_file=file)
        other_result = ReconciliationResult.objects.create(
            run=other_run, internal_transaction=transaction, status="UNMATCHED_INTERNAL"
        )

        assert client.get(f"/api/reconciliation-runs/{run.id}").status_code == 200
        response = client.delete(f"/api/reconciliation-runs/{run.id}")

        assert response.status_code == 204
        assert response.content == b""
        assert not ReconciliationRun.objects.filter(pk=run.id).exists()
        assert not ReconciliationResult.objects.filter(pk=result.id).exists()
        assert not ReconciliationDifference.objects.filter(pk=difference.id).exists()
        assert ReconciliationRun.objects.filter(pk=other_run.id).exists()
        assert ReconciliationResult.objects.filter(pk=other_result.id).exists()
        assert File.objects.filter(pk=file.id).exists()
        assert Transaction.objects.filter(pk=transaction.id).exists()
        assert ManualResolution.objects.filter(pk=resolution.id).exists()

    def test_delete_missing_run_returns_404(self, client):
        response = client.delete("/api/reconciliation-runs/999999")
        assert response.status_code == 404
        assert response.json() == {"detail": "run not found"}
