"""Reconciliation run lifecycle service (PRD sections 19-20).

Pulls the current transactions for the two source files, calls the
framework-independent reconciliation engine, and persists the resulting
statuses, field differences, and run summary.
"""
import time
from datetime import datetime, timezone

from django.db import transaction as db_transaction

from engine import Transaction, TransactionMatchEngine
from engine.matching import ManualResolution
from engine.rules import Rules

from ..models import (
    ManualResolution as ManualResolutionModel,
    ReconciliationDifference,
    ReconciliationResult,
    ReconciliationRun,
    Transaction as TransactionModel,
)
from .file_service import FileImportError


class RunServiceError(ValueError):
    pass


def _tx_to_engine(tx: TransactionModel) -> Transaction:
    """Convert a Django Transaction into the engine's canonical form."""
    return Transaction(
        source=tx.source,
        source_transaction_id=tx.source_transaction_id,
        transaction_time=tx.transaction_time,
        instrument=tx.instrument,
        side=tx.side,
        quantity=tx.quantity,
        price=tx.price,
        amount=tx.amount,
        status=tx.status,
        raw_data=tx.raw_data,
    )


def _engine_to_summary(summary: dict) -> dict:
    return {
        "internal_count": summary.get("internal_count", 0),
        "external_count": summary.get("external_count", 0),
        "matched": summary.get("matched", 0),
        "discrepancies": summary.get("discrepancies", 0),
        "unmatched_internal": summary.get("unmatched_internal", 0),
        "unmatched_external": summary.get("unmatched_external", 0),
        "cancelled": summary.get("cancelled", 0),
        "manually_matched": summary.get("manually_matched", 0),
        "accepted_unmatched": summary.get("accepted_unmatched", 0),
    }


def create_run(*, internal_file_id, external_file_id, rules: Rules = None) -> ReconciliationRun:
    """Create and execute a reconciliation run for two imported files."""
    from ..models import File

    int_file = File.objects.filter(pk=internal_file_id).first()
    ext_file = File.objects.filter(pk=external_file_id).first()
    if int_file is None or ext_file is None:
        raise RunServiceError("internal and external files are required")

    if rules is None:
        rules = Rules()

    run = ReconciliationRun.objects.create(
        status=ReconciliationRun.Status.RUNNING,
        internal_file=int_file,
        external_file=ext_file,
        rules=rules.describe(),
    )

    try:
        internal_txs = list(
            TransactionModel.objects.filter(source="INTERNAL", status__in=["SETTLED", "PENDING", "CANCELLED"])
        )
        external_txs = list(
            TransactionModel.objects.filter(source="EXTERNAL", status__in=["SETTLED", "PENDING", "CANCELLED"])
        )
    except Exception as exc:  # noqa: BLE001
        run.status = ReconciliationRun.Status.FAILED
        run.completed_at = datetime.now(timezone.utc)
        run.save(update_fields=["status", "completed_at"])
        raise RunServiceError(f"could not load transactions: {exc}") from exc

    # Load persisted manual decisions so they remain effective (PRD 16).
    manual_resolutions = _load_manual_resolutions()

    engine = TransactionMatchEngine(rules)
    started = time.perf_counter()
    result = engine.reconcile(
        [_tx_to_engine(t) for t in internal_txs],
        [_tx_to_engine(t) for t in external_txs],
        manual_results=manual_resolutions,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    _persist_results(run, result)

    summary = result.summary()
    summary["elapsed_ms"] = elapsed_ms
    run.summary = summary
    run.status = ReconciliationRun.Status.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.save(update_fields=["summary", "status", "completed_at"])
    return run


def _load_manual_resolutions():
    """Load all persisted manual decisions into engine ManualResolution objects."""
    out = []
    for mr in ManualResolutionModel.objects.select_related(
        "internal_transaction", "external_transaction"
    ).all():
        out.append(
            ManualResolution(
                internal_id=mr.internal_transaction.source_transaction_id if mr.internal_transaction_id else None,
                external_id=mr.external_transaction.source_transaction_id if mr.external_transaction_id else None,
                resolution_type=mr.resolution_type.value if hasattr(mr.resolution_type, "value") else mr.resolution_type,
                reason=mr.reason,
            )
        )
    return out


def _persist_results(run: ReconciliationRun, result) -> None:
    """Persist reconciliation results and field differences for a run."""
    with db_transaction.atomic():
        for r in result.results:
            int_tx_id = None
            ext_tx_id = None
            if r.internal_tx is not None:
                int_tx_id = TransactionModel.objects.filter(
                    source="INTERNAL", source_transaction_id=r.internal_tx.source_transaction_id
                ).values_list("id", flat=True).first()
            if r.external_tx is not None:
                ext_tx_id = TransactionModel.objects.filter(
                    source="EXTERNAL", source_transaction_id=r.external_tx.source_transaction_id
                ).values_list("id", flat=True).first()

            rr = ReconciliationResult.objects.create(
                run=run,
                internal_transaction_id=int_tx_id,
                external_transaction_id=ext_tx_id,
                status=r.status.value if hasattr(r.status, "value") else str(r.status),
                match_method=r.match_method.value if hasattr(r.match_method, "value") else str(r.match_method),
                reason=r.reason or "",
            )
            for d in r.field_differences:
                ReconciliationDifference.objects.create(
                    result=rr,
                    field_name=d.field_name,
                    internal_value=d.internal_value,
                    external_value=d.external_value,
                    difference=d.difference,
                    within_tolerance=d.within_tolerance,
                )


# Imported lazily to avoid a circular import at module load; the engine's
# Transaction type is needed to construct canonical transactions above.
engine_tx_type = Transaction