"""Base CSV parsing infrastructure and provider adapters.

Each provider (internal / external / future provider) maps its own column
names and value formats onto the canonical `Transaction` shape (PRD 8). The
parser layer is the ONLY place that knows about provider-specific formats.
"""
import csv
import io
from abc import ABC, abstractmethod
from typing import List

from ..normalization import (
    Transaction,
    canonical_id,
    normalize_datetime,
    normalize_decimal,
    normalize_quantity,
    normalize_side,
    normalize_amount,
    normalize_price,
)


class ParseError(ValueError):
    """Raised when a CSV file cannot be parsed into canonical transactions."""

    def __init__(self, message: str, row_number: int = None, column: str = None):
        self.message = message
        self.row_number = row_number
        self.column = column
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = []
        if self.row_number:
            parts.append(f"row {self.row_number}")
        if self.column:
            parts.append(f"column '{self.column}'")
        prefix = f"[{' '.join(parts)}] " if parts else ""
        return f"{prefix}{self.message}"


class ProviderParser(ABC):
    """Base class for one source's CSV adapter."""

    source: str = ""
    required_columns: List[str] = []

    def parse(self, content: str) -> List[Transaction]:
        """Parse CSV text into canonical `Transaction` objects."""
        try:
            reader = csv.DictReader(io.StringIO(content))
        except csv.Error as exc:
            raise ParseError(f"could not read CSV: {exc}") from None
        if reader.fieldnames is None or not reader.fieldnames:
            raise ParseError("file is empty (no header row found)")

        missing = [c for c in self.required_columns if c not in reader.fieldnames]
        if missing:
            raise ParseError(
                f"missing required column(s): {', '.join(missing)}"
            )

        transactions = []
        seen_ids = set()
        for i, row in enumerate(reader, start=1):
            if not any((v or "").strip() for v in row.values()):
                continue  # blank line
            try:
                tx = self._row_to_transaction(row, i)
            except ParseError:
                raise
            except Exception as exc:
                raise ParseError(str(exc), row_number=i) from exc

            id_key = canonical_id(tx.source_transaction_id)
            if id_key in seen_ids:
                raise ParseError(
                    f"duplicate transaction ID '{tx.source_transaction_id}' within file",
                    row_number=i,
                    column="source_transaction_id",
                )
            seen_ids.add(id_key)
            transactions.append(tx)
        return transactions

    @abstractmethod
    def _row_to_transaction(self, row: dict, row_number: int) -> Transaction:
        raise NotImplementedError