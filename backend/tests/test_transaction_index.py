"""Tests for the transaction instrument index."""
import pytest
from django.db import connection

from reconciliation.models import Transaction


def test_transaction_meta_declares_instrument_index():
    assert any(index.fields == ["instrument"] for index in Transaction._meta.indexes)


@pytest.mark.django_db
def test_transaction_instrument_index_exists_in_database():
    index = next(index for index in Transaction._meta.indexes if index.fields == ["instrument"])
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, Transaction._meta.db_table)
    assert constraints[index.name]["index"]
    assert constraints[index.name]["columns"] == ["instrument"]
