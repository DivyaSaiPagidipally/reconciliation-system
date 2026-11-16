"""Integration tests for reconciliation runs (pytest-django)."""
import pytest

from reconciliation.models import File, ReconciliationRun

pytestmark = pytest.mark.django_db


@pytest.fixture
def files():
    internal = File.objects.create(filename="internal.csv", source="INTERNAL", sha256="a" * 64)
    external = File.objects.create(filename="external.csv", source="EXTERNAL", sha256="b" * 64)
    return {"internal_file_id": internal.id, "external_file_id": external.id}


class TestRunListing:
    def test_list_and_detail_return_label(self, client):
        labeled = ReconciliationRun.objects.create(label="March month-end")
        unlabeled = ReconciliationRun.objects.create()
        listing = client.get("/api/reconciliation-runs/list")
        assert listing.status_code == 200
        assert {run["id"]: run["label"] for run in listing.json()} == {
            labeled.id: "March month-end", unlabeled.id: "",
        }
        for run in (labeled, unlabeled):
            response = client.get(f"/api/reconciliation-runs/{run.id}")
            assert response.status_code == 200
            assert response.json()["label"] == run.label


class TestRunCreation:
    @pytest.mark.parametrize("label", ["March month-end", "x" * 100])
    def test_create_with_label(self, client, files, label):
        response = client.post("/api/reconciliation-runs", {**files, "label": label}, content_type="application/json")
        assert response.status_code == 201
        assert response.json()["label"] == label
        assert ReconciliationRun.objects.get(pk=response.json()["id"]).label == label

    def test_create_without_label(self, client, files):
        response = client.post("/api/reconciliation-runs", files, content_type="application/json")
        assert response.status_code == 201
        assert response.json()["label"] == ""
        assert ReconciliationRun.objects.get(pk=response.json()["id"]).label == ""

    def test_label_too_long(self, client, files):
        response = client.post("/api/reconciliation-runs", {**files, "label": "x" * 101}, content_type="application/json")
        assert response.status_code == 400
        assert "label" in response.json()
        assert not ReconciliationRun.objects.exists()

    @pytest.mark.parametrize("label", [None, [], {}])
    def test_invalid_label(self, client, files, label):
        response = client.post("/api/reconciliation-runs", {**files, "label": label}, content_type="application/json")
        assert response.status_code == 400
        assert "label" in response.json()
        assert not ReconciliationRun.objects.exists()
