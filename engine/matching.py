"""Automatic matching of internal and external transactions.

Implements PRD section 10 (matching priority) and section 27 (algorithm):

1. Remove CANCELLED transactions.
2. Build indexes over the external transactions.
3. Try exact transaction-ID match.
4. For remaining transactions, score candidates by instrument/side/quantity/
   time/amount against configurable weights.
5. Select the best candidate above the minimum score.
6. Compare fields and classify the result.
7. Apply persisted manual resolutions (overrides).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import comparison as comparison_mod
from . import rules as rules_mod
from .normalization import Transaction, canonical_id
from .status import MatchMethod, ReconciliationStatus


# ---------------------------------------------------------------------------
# Result dataclasses — plain, persist-friendly views of one reconciled pair.
# ---------------------------------------------------------------------------
@dataclass
class ReconciliationResult:
    internal_tx: Optional[Transaction]
    external_tx: Optional[Transaction]
    status: ReconciliationStatus
    match_method: MatchMethod
    field_differences: list = field(default_factory=list)
    reason: Optional[str] = None
    match_score: Optional[int] = None

    @property
    def internal_id(self) -> Optional[str]:
        return self.internal_tx.source_transaction_id if self.internal_tx else None

    @property
    def external_id(self) -> Optional[str]:
        return self.external_tx.source_transaction_id if self.external_tx else None


@dataclass
class ManualResolution:
    """Persisted manual decision."""

    internal_id: Optional[str]
    external_id: Optional[str]
    resolution_type: str  # MATCH | ACCEPT_UNMATCHED_INTERNAL | ACCEPT_UNMATCHED_EXTERNAL
    reason: Optional[str] = None


@dataclass
class MatchingResult:
    """Full output of the reconciliation engine for one run."""

    results: List[ReconciliationResult] = field(default_factory=list)
    cancelled: List[Transaction] = field(default_factory=list)
    internal_count: int = 0
    external_count: int = 0

    def _counts(self) -> Dict[ReconciliationStatus, int]:
        counts: Dict[ReconciliationStatus, int] = {}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    @property
    def matched_count(self) -> int:
        return self._counts()[ReconciliationStatus.MATCHED]

    @property
    def discrepancy_count(self) -> int:
        return self._counts()[ReconciliationStatus.DISCREPANCY]

    @property
    def unmatched_internal_count(self) -> int:
        return self._counts()[ReconciliationStatus.UNMATCHED_INTERNAL]

    @property
    def unmatched_external_count(self) -> int:
        return self._counts()[ReconciliationStatus.UNMATCHED_EXTERNAL]

    @property
    def cancelled_count(self) -> int:
        return len(self.cancelled)

    def summary(self) -> dict:
        counts = self._counts()
        return {
            "internal_count": self.internal_count,
            "external_count": self.external_count,
            "matched": counts[ReconciliationStatus.MATCHED],
            "discrepancies": counts[ReconciliationStatus.DISCREPANCY],
            "unmatched_internal": counts[ReconciliationStatus.UNMATCHED_INTERNAL],
            "unmatched_external": counts[ReconciliationStatus.UNMATCHED_EXTERNAL],
            "cancelled": self.cancelled_count,
            "manually_matched": counts[ReconciliationStatus.MANUALLY_MATCHED],
            "accepted_unmatched": counts[ReconciliationStatus.ACCEPTED_UNMATCHED],
        }


def _key(transaction_id: str) -> str:
    return canonical_id(transaction_id)


def _weigh_score(int_tx: Transaction, ext_tx: Transaction, rules: rules_mod.Rules):
    """Deterministic candidate score for one (internal, external) pair.

    Higher is better. Returns 0 for pairs that cannot match at all (wrong
    instrument, side or quantity — per PRD 11 those are exact matches).
    """
    score = 0
    if str(int_tx.instrument).strip().lower() == str(ext_tx.instrument).strip().lower():
        score += rules.score_instrument
    else:
        return 0

    if str(int_tx.side).strip().upper() == str(ext_tx.side).strip().upper():
        score += rules.score_side
    else:
        return 0

    try:
        if abs(int_tx.quantity - ext_tx.quantity) <= abs(rules.quantity_tolerance):
            score += rules.score_quantity
        elif abs(rules.quantity_tolerance) == 0:
            return 0
        else:
            return 0
    except (TypeError, ValueError):
        return 0

    try:
        time_delta = abs((int_tx.transaction_time - ext_tx.transaction_time).total_seconds())
        if time_delta <= rules.time_tolerance.total_seconds():
            score += rules.score_time
    except (TypeError, ValueError):
        pass

    try:
        if abs(int_tx.amount - ext_tx.amount) <= abs(rules.amount_tolerance):
            score += rules.score_amount
    except (TypeError, ValueError):
        pass

    return score


@dataclass(frozen=True)
class _Candidate:
    ext_tx: Transaction
    score: int


class TransactionMatchEngine:
    """Deterministic reconciliation engine. Stateless given its rules."""

    def __init__(self, rules: rules_mod.Rules = None):
        self.rules = rules or rules_mod.default_rules()

    def reconcile(
        self,
        internal_txs: List[Transaction],
        external_txs: List[Transaction],
        manual_results: Optional[List[ManualResolution]] = None,
    ) -> MatchingResult:
        """Run the full reconciliation pipeline (PRD section 27)."""
        internal_active = [t for t in internal_txs if not rules_mod.is_cancelled(t.status)]
        external_active = [t for t in external_txs if not rules_mod.is_cancelled(t.status)]
        cancelled = [t for t in (internal_txs + external_txs) if rules_mod.is_cancelled(t.status)]

        internal_by_id = {_key(t.source_transaction_id): t for t in internal_active}
        ext_by_id = {_key(t.source_transaction_id): t for t in external_active}

        # Transactions with a persisted manual decision are excluded from
        # automatic matching; the manual override is applied at the end.
        manual_internal_keys = set()
        manual_external_keys = set()
        if manual_results:
            for mr in manual_results:
                if mr.internal_id:
                    manual_internal_keys.add(_key(mr.internal_id))
                if mr.external_id:
                    manual_external_keys.add(_key(mr.external_id))

        used_int_keys: set = set()
        used_ext_keys: set = set()
        results: List[ReconciliationResult] = []

        # --- Rule 1: exact transaction-ID match ---
        if self.rules.id_exact_match:
            for int_key, int_tx in internal_by_id.items():
                if int_key in manual_internal_keys:
                    continue
                if int_key in used_int_keys:
                    continue
                ext_tx = ext_by_id.get(int_key)
                if ext_tx is None or _key(ext_tx.source_transaction_id) in manual_external_keys:
                    continue
                results.append(self._classify_pair(int_tx, ext_tx, MatchMethod.ID))
                used_int_keys.add(int_key)
                used_ext_keys.add(_key(ext_tx.source_transaction_id))

        # --- Rule 2: fuzzy match for remaining transactions ---
        if self.rules.fuzzy_matching:
            # Index remaining external transactions by (instrument, side).
            ext_idx: Dict[Tuple[str, str], List[Transaction]] = {}
            for tx in external_active:
                if _key(tx.source_transaction_id) in used_ext_keys:
                    continue
                if _key(tx.source_transaction_id) in manual_external_keys:
                    continue
                key = (str(tx.instrument).strip().lower(), str(tx.side).strip().upper())
                ext_idx.setdefault(key, []).append(tx)

            remaining_internal = [
                t for t in internal_active if _key(t.source_transaction_id) not in used_int_keys
            ]
            remaining_internal.sort(key=lambda t: t.source_transaction_id)

            for int_tx in remaining_internal:
                if _key(int_tx.source_transaction_id) in manual_internal_keys:
                    continue
                key = (str(int_tx.instrument).strip().lower(), str(int_tx.side).strip().upper())
                pool = ext_idx.get(key, [])
                candidates: List[_Candidate] = []
                for ext_tx in pool:
                    sc = self._weigh_score(int_tx, ext_tx)
                    if sc >= self.rules.min_fuzzy_score:
                        candidates.append(_Candidate(ext_tx=ext_tx, score=sc))
                candidates.sort(key=lambda c: (-c.score, c.ext_tx.source_transaction_id))
                if candidates:
                    best = candidates[0]
                    results.append(self._classify_pair(int_tx, best.ext_tx, MatchMethod.FUZZY, score=best.score))
                    used_int_keys.add(_key(int_tx.source_transaction_id))
                    used_ext_keys.add(_key(best.ext_tx.source_transaction_id))
                    # Remove the chosen external from the pool.
                    pool[:] = [tx for tx in pool if tx is not best.ext_tx]

        # --- Unmatched ---
        for tx in internal_active:
            if _key(tx.source_transaction_id) not in used_int_keys and _key(tx.source_transaction_id) not in manual_internal_keys:
                results.append(self._make_unmatched(tx, ReconciliationStatus.UNMATCHED_INTERNAL))
        for ext_tx in external_active:
            if _key(ext_tx.source_transaction_id) not in used_ext_keys and _key(ext_tx.source_transaction_id) not in manual_external_keys:
                results.append(self._make_unmatched(ext_tx, ReconciliationStatus.UNMATCHED_EXTERNAL))

        # --- Apply persisted manual resolutions (override auto results) ---
        if manual_results:
            results = self._apply_manual(results, manual_results)

        return MatchingResult(
            results=results,
            cancelled=cancelled,
            internal_count=len(internal_txs),
            external_count=len(external_txs),
        )

    # -- internal helpers ----------------------------------------------------

    def _weigh_score(self, int_tx: Transaction, ext_tx: Transaction):
        return _weigh_score(int_tx, ext_tx, self.rules)

    @staticmethod
    def _classify_pair(
        int_tx: Transaction,
        ext_tx: Transaction,
        method: MatchMethod,
        score: Optional[int] = None,
    ) -> ReconciliationResult:
        comparison = comparison_mod.compare_transactions(int_tx, ext_tx, rules_mod.default_rules())
        status = ReconciliationStatus.MATCHED if comparison.all_match else ReconciliationStatus.DISCREPANCY
        return ReconciliationResult(
            internal_tx=int_tx,
            external_tx=ext_tx,
            status=status,
            match_method=method,
            field_differences=comparison.differences,
            match_score=score,
        )

    @staticmethod
    def _make_unmatched(tx: Transaction, status: ReconciliationStatus) -> ReconciliationResult:
        if status == ReconciliationStatus.UNMATCHED_INTERNAL:
            return ReconciliationResult(internal_tx=tx, external_tx=None, status=status, match_method=MatchMethod.NONE)
        return ReconciliationResult(internal_tx=None, external_tx=tx, status=status, match_method=MatchMethod.NONE)

    def _apply_manual(
        self,
        results: List[ReconciliationResult],
        manual_results: List[ManualResolution],
    ) -> List[ReconciliationResult]:
        """Build the final results from auto results plus persisted decisions.

        For every transaction that has a pending manual decision, we drop its
        auto-generated result and emit the manual one instead.
        """
        # Index auto results by canonical internal/external id.
        by_int_id: Dict[str, ReconciliationResult] = {}
        by_ext_id: Dict[str, ReconciliationResult] = {}
        for r in results:
            if r.internal_id:
                by_int_id.setdefault(_key(r.internal_id), r)
            if r.external_id:
                by_ext_id.setdefault(_key(r.external_id), r)

        override_keys: set = set()  # ids of results we replace
        final: List[ReconciliationResult] = []

        for mr in manual_results:
            if mr.resolution_type == "MATCH":
                int_tx = by_int_id.get(_key(mr.internal_id)) if mr.internal_id else None
                ext_tx = by_ext_id.get(_key(mr.external_id)) if mr.external_id else None
                if int_tx is None or ext_tx is None:
                    continue
                # Field comparison is recomputed for the manual pair.
                comparison = comparison_mod.compare_transactions(
                    int_tx.internal_tx if int_tx.internal_tx else int_tx.external_tx,
                    ext_tx.external_tx if ext_tx.external_tx else ext_tx.internal_tx,
                    self.rules,
                )
                final.append(
                    ReconciliationResult(
                        internal_tx=int_tx.internal_tx or ext_tx.internal_tx,
                        external_tx=ext_tx.external_tx or int_tx.external_tx,
                        status=ReconciliationStatus.MANUALLY_MATCHED,
                        match_method=MatchMethod.MANUAL,
                        field_differences=comparison.differences,
                        reason=mr.reason,
                    )
                )
                override_keys.add(id(by_int_id[_key(mr.internal_id)]))
                override_keys.add(id(by_ext_id[_key(mr.external_id)]))
            elif mr.resolution_type == "ACCEPT_UNMATCHED_INTERNAL":
                existing = by_int_id.get(_key(mr.internal_id)) if mr.internal_id else None
                if existing is None:
                    continue
                tx = existing.internal_tx or existing.external_tx
                final.append(
                    ReconciliationResult(
                        internal_tx=tx,
                        external_tx=None,
                        status=ReconciliationStatus.ACCEPTED_UNMATCHED,
                        match_method=MatchMethod.NONE,
                        reason=mr.reason,
                    )
                )
                override_keys.add(id(existing))
            elif mr.resolution_type == "ACCEPT_UNMATCHED_EXTERNAL":
                existing = by_ext_id.get(_key(mr.external_id)) if mr.external_id else None
                if existing is None:
                    continue
                tx = existing.external_tx or existing.internal_tx
                final.append(
                    ReconciliationResult(
                        internal_tx=None,
                        external_tx=tx,
                        status=ReconciliationStatus.ACCEPTED_UNMATCHED,
                        match_method=MatchMethod.NONE,
                        reason=mr.reason,
                    )
                )
                override_keys.add(id(existing))

        final.extend(r for r in results if id(r) not in override_keys)
        return final