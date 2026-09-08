"""External statement CSV adapter (provider B).

Columns (PRD example):

    reference,executed_at,symbol,direction,qty,unit_price,total,status
    X-9001,2026-09-07 09:15:03,BTC-USD,B,0.5,62000,31000,SETTLED

Note the different date format, side vocabulary (B/S), quantity column name
(qty) and amount column name (total) — all normalized per PRD section 8.
"""
from ..normalization import (
    Transaction,
    normalize_amount,
    normalize_datetime,
    normalize_price,
    normalize_quantity,
    normalize_side,
)
from .base import ParseError, ProviderParser


class ExternalCSVParser(ProviderParser):
    source = "EXTERNAL"
    required_columns = ["reference", "executed_at", "symbol", "direction", "qty", "unit_price", "total", "status"]

    def _row_to_transaction(self, row: dict, row_number: int) -> Transaction:
        try:
            return Transaction(
                source=self.source,
                source_transaction_id=str(row["reference"]).strip(),
                transaction_time=normalize_datetime(row["executed_at"]),
                instrument=str(row["symbol"]).strip(),
                side=normalize_side(row["direction"]),
                quantity=normalize_quantity(row["qty"]),
                price=normalize_price(row["unit_price"]),
                amount=normalize_amount(row["total"]),
                status=str(row["status"]).strip().upper(),
                raw_data=dict(row),
            )
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(str(exc), row_number=row_number) from exc