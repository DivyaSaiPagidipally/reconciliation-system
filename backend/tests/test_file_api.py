"""Integration tests for uploaded file details (pytest-django)."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


class TestFileDetail:
    def test_get_uploaded_file_matches_list(self, client):
        csv = (
            b"trade_id,traded_at,instrument,side,quantity,price,gross_amount,state\n"
            b"L-1001,2026-09-07T09:15:00Z,BTC-USD,BUY,0.50,62000,31000,SETTLED\n"
        )
        upload = client.post(
            "/api/files",
            {"file": SimpleUploadedFile("internal.csv", csv), "source": "INTERNAL"},
        )
        assert upload.status_code == 201
        uploaded = upload.json()["file"]

        response = client.get(f"/api/files/{uploaded['id']}")
        listing = client.get("/api/files/list")
        assert response.status_code == 200
        assert listing.status_code == 200
        assert response.json() == listing.json()[0] == uploaded
        assert set(response.json()) == {"id", "filename", "source", "sha256", "uploaded_at", "record_count"}
        assert response.json()["filename"] == "internal.csv"
        assert response.json()["record_count"] == 1

    def test_get_missing_file_returns_404(self, client):
        response = client.get("/api/files/999999")
        assert response.status_code == 404
        assert response.json() == {"detail": "file not found"}
