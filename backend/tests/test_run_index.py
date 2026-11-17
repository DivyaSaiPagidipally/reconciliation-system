"""Tests for the reconciliation run start-time index."""
import pytest
from django.db import connection

from reconciliation.models import ReconciliationRun


def test_run_declares_started_at_index():
    assert any(index.fields == ["started_at"] for index in ReconciliationRun._meta.indexes)


@pytest.mark.django_db
def test_started_at_index_exists_in_database():
    index = next(index for index in ReconciliationRun._meta.indexes if index.fields == ["started_at"])
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, ReconciliationRun._meta.db_table)
    assert constraints[index.name]["index"]
    assert constraints[index.name]["columns"] == ["started_at"]
