"""Verify existing runs survive the label migration on PostgreSQL."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_existing_run_gets_empty_label_after_migration(client):
    before = [("reconciliation", "0003_alter_file_sha256")]
    after = [("reconciliation", "0004_reconciliationrun_label")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        old_run = old_apps.get_model("reconciliation", "ReconciliationRun").objects.create(
            status="COMPLETED", summary={"matched": 3}, rules={"version": 1}
        )
        run_id = old_run.pk

        executor = MigrationExecutor(connection)
        executor.migrate(after)
        new_apps = executor.loader.project_state(after).apps
        run = new_apps.get_model("reconciliation", "ReconciliationRun").objects.get(pk=run_id)
        assert run.label == ""
        assert run.status == "COMPLETED"
        assert run.summary == {"matched": 3}
        assert run.rules == {"version": 1}
        detail = client.get(f"/api/reconciliation-runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["label"] == ""
        assert detail.json()["summary"] == {"matched": 3}
        listing = client.get("/api/reconciliation-runs/list")
        assert listing.status_code == 200
        assert listing.json()[0]["label"] == ""
    finally:
        MigrationExecutor(connection).migrate(after)
