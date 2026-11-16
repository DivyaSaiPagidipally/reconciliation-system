"""Integration tests for reconciliation runs (pytest-django)."""
import pytest

from reconciliation.models import File, ReconciliationRun

pytestmark = pytest.mark.django_db


@pytest.fixture
def file_ids():
    internal = File.objects.create(filename="internal.csv", source="INTERNAL", sha256="a" * 64)
    external = File.objects.create(filename="external.csv", source="EXTERNAL", sha256="b" * 64)
    return {"internal_file_id": internal.id, "external_file_id": external.id}


def test_run_label_field_defaults():
    field = ReconciliationRun._meta.get_field("label")
    assert field.max_length == 100
    assert field.blank
    assert field.default == ""
    assert ReconciliationRun.objects.create().label == ""


class TestStartRun:
    @pytest.mark.parametrize("label", ["March month-end", "x" * 100, ""])
    def test_create_with_label(self, client, file_ids, label):
        response = client.post("/api/reconciliation-runs", {**file_ids, "label": label})
        assert response.status_code == 201
        assert ReconciliationRun.objects.get(pk=response.json()["id"]).label == label

    def test_create_without_label(self, client, file_ids):
        response = client.post("/api/reconciliation-runs", file_ids)
        assert response.status_code == 201
        assert ReconciliationRun.objects.get(pk=response.json()["id"]).label == ""

    @pytest.mark.parametrize("label", ["x" * 101, " " * 101, None, []])
    def test_invalid_label_is_rejected(self, client, file_ids, label):
        response = client.post("/api/reconciliation-runs", {**file_ids, "label": label}, content_type="application/json")
        assert response.status_code == 400
        assert "label" in response.json()
        assert not ReconciliationRun.objects.exists()


class TestRunResponses:
    def test_list_and_detail_return_labels(self, client, file_ids):
        labelled = client.post("/api/reconciliation-runs", {**file_ids, "label": "March month-end"}).json()
        unlabelled = client.post("/api/reconciliation-runs", file_ids).json()
        assert labelled["label"] == "March month-end"
        assert unlabelled["label"] == ""

        listing = client.get("/api/reconciliation-runs/list")
        assert listing.status_code == 200
        assert {run["id"]: run["label"] for run in listing.json()} == {
            labelled["id"]: "March month-end", unlabelled["id"]: "",
        }
        for run in (labelled, unlabelled):
            detail = client.get(f"/api/reconciliation-runs/{run['id']}")
            assert detail.status_code == 200
            assert detail.json() == run
