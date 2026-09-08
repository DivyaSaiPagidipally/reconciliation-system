"""API endpoints for reconciliation runs and results (PRD 25.2-25.5)."""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import (
    ReconciliationResult,
    ReconciliationRun,
    Transaction,
)
from ..serializers import (
    ReconciliationResultDetailSerializer,
    ReconciliationResultSerializer,
    ReconciliationRunSerializer,
)
from ..services.resolution_service import ResolutionError, accept_unmatched, match_transactions
from ..services.run_service import RunServiceError, create_run


@api_view(["POST"])
def start_reconciliation(request):
    """Start a reconciliation run.

    Request body: ``{"internal_file_id": <id>, "external_file_id": <id>}``.
    """
    int_id = request.data.get("internal_file_id")
    ext_id = request.data.get("external_file_id")
    if not int_id or not ext_id:
        return Response(
            {"detail": "internal_file_id and external_file_id are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        run = create_run(internal_file_id=int_id, external_file_id=ext_id)
    except RunServiceError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(ReconciliationRunSerializer(run).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def list_runs(request):
    runs = ReconciliationRun.objects.order_by("-id")
    return Response(ReconciliationRunSerializer(runs, many=True).data)


@api_view(["GET"])
def get_run(request, run_id):
    run = ReconciliationRun.objects.filter(pk=run_id).first()
    if run is None:
        return Response({"detail": "run not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(ReconciliationRunSerializer(run).data)


@api_view(["GET"])
def get_run_results(request, run_id):
    run = ReconciliationRun.objects.filter(pk=run_id).first()
    if run is None:
        return Response({"detail": "run not found"}, status=status.HTTP_404_NOT_FOUND)
    status_filter = request.query_params.get("status")
    qs = ReconciliationResult.objects.filter(run=run).select_related(
        "internal_transaction", "external_transaction"
    )
    if status_filter:
        qs = qs.filter(status__iexact=status_filter)
    qs = qs.order_by("id")
    return Response(ReconciliationResultSerializer(qs, many=True).data)


@api_view(["GET"])
def get_reconciliation_result(request, result_id):
    result = (
        ReconciliationResult.objects.filter(pk=result_id)
        .select_related("internal_transaction", "external_transaction")
        .first()
    )
    if result is None:
        return Response({"detail": "result not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(ReconciliationResultDetailSerializer(result).data)


@api_view(["POST"])
def manually_match(request, result_id):
    """Manually pair the record with another.

    Request body: ``{"external_transaction_id": <id>}`` (or
    ``internal_transaction_id`` when resolving an external-only record).
    """
    result = ReconciliationResult.objects.filter(pk=result_id).first()
    if result is None:
        return Response({"detail": "result not found"}, status=status.HTTP_404_NOT_FOUND)

    int_tx = result.internal_transaction
    ext_tx = result.external_transaction
    body_ext_id = request.data.get("external_transaction_id")
    body_int_id = request.data.get("internal_transaction_id")
    reason = request.data.get("reason", "")

    # Determine which side is unmatched and which counterpart to attach.
    if body_ext_id:
        counterpart = Transaction.objects.filter(source="EXTERNAL", pk=body_ext_id).first()
        if counterpart is None:
            return Response({"detail": "external transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        resolved_int = int_tx
        resolved_ext = counterpart
    elif body_int_id:
        counterpart = Transaction.objects.filter(source="INTERNAL", pk=body_int_id).first()
        if counterpart is None:
            return Response({"detail": "internal transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        resolved_int = counterpart
        resolved_ext = ext_tx
    else:
        return Response(
            {"detail": "external_transaction_id or internal_transaction_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if resolved_int is None or resolved_ext is None:
        return Response(
            {"detail": "cannot match: this result already has both sides attached or neither side is resolveable"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        updated = match_transactions(
            internal_tx_id=resolved_int.id,
            external_tx_id=resolved_ext.id,
            reason=reason,
        )
    except ResolutionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(ReconciliationResultDetailSerializer(updated).data)


@api_view(["POST"])
def accept_unmatched_view(request, result_id):
    """Mark the record as legitimately unmatched.

    Request body: ``{"reason": "Late settlement"}``.
    """
    result = ReconciliationResult.objects.filter(pk=result_id).first()
    if result is None:
        return Response({"detail": "result not found"}, status=status.HTTP_404_NOT_FOUND)

    reason = request.data.get("reason", "")
    tx = result.internal_transaction or result.external_transaction
    if tx is None:
        return Response({"detail": "this result has no transaction to accept"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        updated = accept_unmatched(transaction_id=tx.id, source=tx.source, reason=reason)
    except ResolutionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(ReconciliationResultDetailSerializer(updated).data)


@api_view(["GET"])
def dashboard(request):
    """Dashboard summary: latest run + unresolved counts (PRD 20)."""
    latest = (
        ReconciliationRun.objects.filter(status=ReconciliationRun.Status.COMPLETED)
        .order_by("-id")
        .first()
    )
    data = {"latest_run": None, "unresolved": []}
    if latest is None:
        return Response(data)

    data["latest_run"] = ReconciliationRunSerializer(latest).data
    unresolved = ReconciliationResult.objects.filter(
        run=latest,
        status__in=[
            ReconciliationResult.Status.DISCREPANCY,
            ReconciliationResult.Status.UNMATCHED_INTERNAL,
            ReconciliationResult.Status.UNMATCHED_EXTERNAL,
        ],
    ).select_related("internal_transaction", "external_transaction").order_by("id")[:50]
    data["unresolved"] = ReconciliationResultSerializer(unresolved, many=True).data
    return Response(data)