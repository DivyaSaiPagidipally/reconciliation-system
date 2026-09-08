"""Django models for the reconciliation app (PRD section 24)."""
from django.db import models


class File(models.Model):
    """An uploaded transaction file (internal or external)."""

    class Source(models.TextChoices):
        INTERNAL = "INTERNAL", "Internal"
        EXTERNAL = "EXTERNAL", "External"

    filename = models.CharField(max_length=255)
    source = models.CharField(max_length=16, choices=Source.choices)
    sha256 = models.CharField(max_length=64, db_collation="case_sensitive")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    record_count = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "files"
        indexes = [
            models.Index(fields=["source", "sha256"]),
        ]

    def __str__(self) -> str:
        return f"{self.source} {self.filename} ({self.sha256[:8]})"


class Transaction(models.Model):
    """Canonical transaction representation (current version)."""

    class Side(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    class Status(models.TextChoices):
        SETTLED = "SETTLED", "Settled"
        CANCELLED = "CANCELLED", "Cancelled"
        PENDING = "PENDING", "Pending"

    source = models.CharField(max_length=16)  # INTERNAL | EXTERNAL
    source_transaction_id = models.CharField(max_length=255)
    transaction_time = models.DateTimeField()
    instrument = models.CharField(max_length=64)
    side = models.CharField(max_length=16, choices=Side.choices)
    quantity = models.DecimalField(max_digits=38, decimal_places=18)
    price = models.DecimalField(max_digits=38, decimal_places=18)
    amount = models.DecimalField(max_digits=38, decimal_places=18)
    status = models.CharField(max_length=16, choices=Status.choices)
    raw_data = models.JSONField(default=dict, blank=True)
    current_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file = models.ForeignKey(
        "File",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    latest_for_source_id = models.CharField(max_length=255, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "source_transaction_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_transaction_id"],
                name="uniq_source_tx_latest",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.source_transaction_id} v{self.current_version}"


class TransactionVersion(models.Model):
    """Historical snapshot of a transaction (PRD section 18)."""

    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    raw_data = models.JSONField(default=dict, blank=True)
    quantity = models.DecimalField(max_digits=38, decimal_places=18)
    price = models.DecimalField(max_digits=38, decimal_places=18)
    amount = models.DecimalField(max_digits=38, decimal_places=18)
    transaction_time = models.DateTimeField()
    status = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "version"],
                name="uniq_tx_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.transaction} v{self.version}"


class ReconciliationRun(models.Model):
    """One execution of the reconciliation process (PRD section 19)."""

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    internal_file = models.ForeignKey(
        File, on_delete=models.SET_NULL, null=True, related_name="internal_runs"
    )
    external_file = models.ForeignKey(
        File, on_delete=models.SET_NULL, null=True, related_name="external_runs"
    )
    summary = models.JSONField(default=dict, blank=True)
    rules = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"Run #{self.id} ({self.status})"


class ReconciliationResult(models.Model):
    """Outcome of one (pair of) transaction(s) in a run (PRD 21/12)."""

    class Status(models.TextChoices):
        MATCHED = "MATCHED", "Matched"
        DISCREPANCY = "DISCREPANCY", "Discrepancy"
        UNMATCHED_INTERNAL = "UNMATCHED_INTERNAL", "Unmatched Internal"
        UNMATCHED_EXTERNAL = "UNMATCHED_EXTERNAL", "Unmatched External"
        MANUALLY_MATCHED = "MANUALLY_MATCHED", "Manually Matched"
        ACCEPTED_UNMATCHED = "ACCEPTED_UNMATCHED", "Accepted Unmatched"

    class MatchMethod(models.TextChoices):
        ID = "ID", "Exact ID"
        FUZZY = "FUZZY", "Fuzzy"
        MANUAL = "MANUAL", "Manual"
        NONE = "NONE", "None"

    run = models.ForeignKey(
        ReconciliationRun, on_delete=models.CASCADE, related_name="results"
    )
    internal_transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="internal_results"
    )
    external_transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="external_results"
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    match_method = models.CharField(max_length=16, choices=MatchMethod.choices, default=MatchMethod.NONE)
    reason = models.TextField(blank=True, default="")
    match_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["run", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.run}: {self.status}"


class ReconciliationDifference(models.Model):
    """Field-level difference for a matched/discrepancy pair (PRD 13)."""

    result = models.ForeignKey(
        ReconciliationResult, on_delete=models.CASCADE, related_name="differences"
    )
    field_name = models.CharField(max_length=64)
    internal_value = models.TextField(blank=True, default="")
    external_value = models.TextField(blank=True, default="")
    difference = models.TextField(blank=True, default="")
    within_tolerance = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.result} {self.field_name}"


class ManualResolution(models.Model):
    """Persisted human decision that survives future runs (PRD 16)."""

    class ResolutionType(models.TextChoices):
        MATCH = "MATCH", "Manual match"
        ACCEPT_UNMATCHED_INTERNAL = "ACCEPT_UNMATCHED_INTERNAL", "Accept unmatched (internal)"
        ACCEPT_UNMATCHED_EXTERNAL = "ACCEPT_UNMATCHED_EXTERNAL", "Accept unmatched (external)"

    internal_transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="manual_resolutions_int",
    )
    external_transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="manual_resolutions_ext",
    )
    resolution_type = models.CharField(max_length=32, choices=ResolutionType.choices)
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["internal_transaction", "external_transaction"],
                name="uniq_manual_resolution",
            )
        ]

    def __str__(self) -> str:
        return f"MR {self.resolution_type} {self.internal_transaction_id}->{self.external_transaction_id}"