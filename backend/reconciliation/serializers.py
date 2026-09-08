"""DRF serializers for the reconciliation API."""
from rest_framework import serializers

from .models import (
    File,
    ManualResolution,
    ReconciliationDifference,
    ReconciliationResult,
    ReconciliationRun,
    Transaction,
    TransactionVersion,
)


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ["id", "filename", "source", "sha256", "uploaded_at", "record_count"]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "source",
            "source_transaction_id",
            "transaction_time",
            "instrument",
            "side",
            "quantity",
            "price",
            "amount",
            "status",
            "current_version",
        ]


class TransactionVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionVersion
        fields = ["id", "version", "quantity", "price", "amount", "transaction_time", "status", "created_at"]


class ReconciliationRunSerializer(serializers.ModelSerializer):
    internal_file = FileSerializer(read_only=True)
    external_file = FileSerializer(read_only=True)

    class Meta:
        model = ReconciliationRun
        fields = [
            "id",
            "started_at",
            "completed_at",
            "status",
            "internal_file",
            "external_file",
            "summary",
            "rules",
        ]


class ReconciliationResultSerializer(serializers.ModelSerializer):
    internal_transaction = TransactionSerializer(read_only=True)
    external_transaction = TransactionSerializer(read_only=True)

    class Meta:
        model = ReconciliationResult
        fields = [
            "id",
            "status",
            "match_method",
            "reason",
            "internal_transaction",
            "external_transaction",
        ]


class ReconciliationResultDetailSerializer(ReconciliationResultSerializer):
    differences = serializers.SerializerMethodField()

    class Meta(ReconciliationResultSerializer.Meta):
        fields = ReconciliationResultSerializer.Meta.fields + ["differences"]

    def get_differences(self, obj):
        return [
            {
                "field_name": d.field_name,
                "internal_value": d.internal_value,
                "external_value": d.external_value,
                "difference": d.difference,
                "within_tolerance": d.within_tolerance,
            }
            for d in obj.differences.all()
        ]


class ManualResolutionSerializer(serializers.ModelSerializer):
    internal_transaction = TransactionSerializer(read_only=True)
    external_transaction = TransactionSerializer(read_only=True)

    class Meta:
        model = ManualResolution
        fields = [
            "id",
            "resolution_type",
            "reason",
            "created_at",
            "internal_transaction",
            "external_transaction",
        ]