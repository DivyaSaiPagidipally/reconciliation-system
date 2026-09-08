"""Manual resolution service (PRD sections 14-16).

Persists manual decisions so they remain effective on future runs, and
recomputes the current run's result for the affected records.
"""
from django.db import transaction as db_transaction
from django.db.models import Q

from engine.rules import default_rules

from ..models import (
    ManualResolution,
    ReconciliationResult,
    ReconciliationRun,
    Transaction,
)


class ResolutionError(ValueError):
    pass


def _current_run() -> ReconciliationRun:
    run = (
        ReconciliationRun.objects.filter(status=ReconciliationRun.Status.COMPLETED)
        .order_by("-id")
        .first()
    )
    if run is None:
        raise ResolutionError("no completed reconciliation run exists")
    return run


@db_transaction.atomic
def match_transactions(*, internal_tx_id: int, external_tx_id: int, reason: str = "") -> ReconciliationResult:
    """Manually pair an internal and an external transaction.

    Creates the persistent mapping, then marks the two records in the latest
    completed run as MANUALLY_MATCHED.
    """
    int_tx = Transaction.objects.filter(source="INTERNAL", pk=internal_tx_id).first()
    ext_tx = Transaction.objects.filter(source="EXTERNAL", pk=external_tx_id).first()
    if int_tx is None or ext_tx is None:
        raise ResolutionError("both an internal and an external transaction are required")

    mr, created = ManualResolution.objects.get_or_create(
        internal_transaction=int_tx,
        external_transaction=ext_tx,
        defaults={
            "resolution_type": ManualResolution.ResolutionType.MATCH,
            "reason": reason,
        },
    )
    if not created:
        mr.resolution_type = ManualResolution.ResolutionType.MATCH
        if reason:
            mr.reason = reason
        mr.save()

    run = _current_run()
    results = list(
        ReconciliationResult.objects.filter(
            Q(internal_transaction=int_tx) | Q(external_transaction=ext_tx),
            run=run,
        )
    )
    updated = []
    for rr in results:
        rr.status = ReconciliationResult.Status.MANUALLY_MATCHED
        rr.match_method = ReconciliationResult.MatchMethod.MANUAL
        rr.reason = reason
        rr.save()
        updated.append(rr)

    if updated:
        return updated[0]
    # No row yet (records blocked from auto-matching); create one.
    return ReconciliationResult.objects.create(
        run=run,
        internal_transaction=int_tx,
        external_transaction=ext_tx,
        status=ReconciliationResult.Status.MANUALLY_MATCHED,
        match_method=ReconciliationResult.MatchMethod.MANUAL,
        reason=reason,
    )


@db_transaction.atomic
def accept_unmatched(*, transaction_id: int, source: str, reason: str = "") -> ReconciliationResult:
    """Mark a transaction as legitimately having no counterpart (PRD 15)."""
    tx = Transaction.objects.filter(source=source, pk=transaction_id).first()
    if tx is None:
        raise ResolutionError(f"no {source} transaction with id {transaction_id}")

    int_tx = tx if source == "INTERNAL" else None
    ext_tx = tx if source == "EXTERNAL" else None
    resolution_type = (
        ManualResolution.ResolutionType.ACCEPT_UNMATCHED_INTERNAL
        if source == "INTERNAL"
        else ManualResolution.ResolutionType.ACCEPT_UNMATCHED_EXTERNAL
    )

    mr, _ = ManualResolution.objects.get_or_create(
        internal_transaction=int_tx,
        external_transaction=ext_tx,
        defaults={"resolution_type": resolution_type, "reason": reason},
    )

    run = _current_run()
    results = list(
        ReconciliationResult.objects.filter(run=run)
        .filter(Q(internal_transaction=tx) | Q(external_transaction=tx))
    )
    updated = []
    for rr in results:
        rr.status = ReconciliationResult.Status.ACCEPTED_UNMATCHED
        rr.match_method = ReconciliationResult.MatchMethod.NONE
        rr.reason = reason
        rr.save()
        updated.append(rr)

    if updated:
        return updated[0]
    return ReconciliationResult.objects.create(
        run=run,
        internal_transaction=int_tx,
        external_transaction=ext_tx,
        status=ReconciliationResult.Status.ACCEPTED_UNMATCHED,
        match_method=ReconciliationResult.MatchMethod.NONE,
        reason=reason,
    )