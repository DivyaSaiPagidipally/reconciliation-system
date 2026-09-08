from django.urls import path

from .api import files, reconciliation

urlpatterns = [
    # Files
    path("files", files.upload_file),
    path("files/list", files.list_files),
    # Reconciliation runs
    path("reconciliation-runs", reconciliation.start_reconciliation),
    path("reconciliation-runs/list", reconciliation.list_runs),
    path("reconciliation-runs/dashboard", reconciliation.dashboard),
    path("reconciliation-runs/<int:run_id>", reconciliation.get_run),
    path("reconciliation-runs/<int:run_id>/results", reconciliation.get_run_results),
    # Results
    path("reconciliation-results/<int:result_id>", reconciliation.get_reconciliation_result),
    path("reconciliation-results/<int:result_id>/match", reconciliation.manually_match),
    path("reconciliation-results/<int:result_id>/accept", reconciliation.accept_unmatched_view),
]