"""Internal ledger CSV adapter (provider A).

Columns (PRD example):

    trade_id,traded_at,instrument,side,quantity,price,gross_amount,state
    L-1001,2026-09-07T09:15:00Z,BTC-USD,BUY,0.50,62000,31000,SETTLED
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


class InternalCSVParser(ProviderParser):
    source = "INTERNAL"
    required_columns = ["trade_id", "traded_at", "instrument", "side", "quantity", "price", "gross_amount", "state"]

    def _row_to_transaction(self, row: dict, row_number: int) -> Transaction:
        try:
            return Transaction(
                source=self.source,
                source_transaction_id=str(row["trade_id"]).strip(),
                transaction_time=normalize_datetime(row["traded_at"]),
                instrument=str(row["instrument"]).strip(),
                side=normalize_side(row["side"]),
                quantity=normalize_quantity(row["quantity"]),
                price=normalize_price(row["price"]),
                amount=normalize_amount(row["gross_amount"]),
                status=str(row["state"]).strip().upper(),
                raw_data=dict(row),
            )
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(str(exc), row_number=row_number) from exc