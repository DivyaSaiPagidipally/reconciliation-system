"""Check existing runs survive the label migration on PostgreSQL."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_existing_run_gets_empty_label(client):
    migrate_from = [("reconciliation", "0003_alter_file_sha256")]
    migrate_to = [("reconciliation", "0004_reconciliationrun_label")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(migrate_from)
        old_apps = executor.loader.project_state(migrate_from).apps
        old_run = old_apps.get_model("reconciliation", "ReconciliationRun").objects.create(
            status="COMPLETED", summary={"matched": 3}
        )
        executor = MigrationExecutor(connection)
        executor.migrate(migrate_to)
        new_apps = executor.loader.project_state(migrate_to).apps
        migrated = new_apps.get_model("reconciliation", "ReconciliationRun").objects.get(pk=old_run.pk)
        assert migrated.label == ""
        assert migrated.status == "COMPLETED"
        assert migrated.summary == {"matched": 3}
        response = client.get(f"/api/reconciliation-runs/{old_run.pk}")
        assert response.status_code == 200
        assert response.json()["label"] == ""
        assert response.json()["summary"] == {"matched": 3}
    finally:
        MigrationExecutor(connection).migrate(migrate_to)
