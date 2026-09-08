"""File upload lifecycle: validation, deduplication, normalization, versioning.

Implements PRD sections 7, 17 (duplicate files via SHA-256), 18 (corrected
files -> transaction_versions) and 31 (error handling).
"""
import hashlib
import secrets

from django.db import transaction as db_transaction

from engine.parsers.external import ExternalCSVParser
from engine.parsers.internal import InternalCSVParser
from engine.parsers.base import ParseError

from ..models import File, Transaction, TransactionVersion
from .constants import MAX_UPLOAD_BYTES, SUPPORTED_EXTENSIONS


class FileImportError(ValueError):
    """Raised for user-facing file upload failures."""

    def __init__(self, message: str, code: str = "invalid_file"):
        self.message = message
        self.code = code
        super().__init__(message)


class DuplicateFileError(FileImportError):
    def __init__(self, message: str, existing_file=None):
        super().__init__(message, code="duplicate_file")
        self.existing_file = existing_file


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parser_for_source(source: str):
    """Select the provider adapter by source identifier (PRD 7.1/8)."""
    if source == File.Source.INTERNAL:
        return InternalCSVParser()
    if source == File.Source.EXTERNAL:
        return ExternalCSVParser()
    raise FileImportError(f"unknown source identifier: {source!r}", code="invalid_source")


def _get_or_create_transaction(map, source, source_id, **fields):
    """Insert the current version, archiving an existing row if the ID exists.

    Returns (transaction, created) like Django's get_or_create.
    """
    tx = map.get((source, source_id))
    if tx is not None:
        return tx, False
    existing = (
        Transaction.objects.filter(source=source, source_transaction_id=source_id)
        .select_for_update()
        .first()
    )
    if existing is not None:
        # Corrected file: archive the old current version, bump the version.
        TransactionVersion.objects.create(
            transaction=existing,
            version=existing.current_version,
            raw_data=existing.raw_data,
            quantity=existing.quantity,
            price=existing.price,
            amount=existing.amount,
            transaction_time=existing.transaction_time,
            status=existing.status,
        )
        existing.current_version += 1
        for fname, val in fields.items():
            setattr(existing, fname, val)
        existing.save()
        map[(source, source_id)] = existing
        return existing, False
    tx_obj = Transaction.objects.create(
        source=source,
        source_transaction_id=source_id,
        latest_for_source_id=source_id,
        **fields,
    )
    map[(source, source_id)] = tx_obj
    return tx_obj, True


@db_transaction.atomic
def import_file(*, filename: str, source: str, content: str, content_bytes: bytes) -> File:
    """Validate, deduplicate, parse, normalize and persist an uploaded file.

    Raises FileImportError / DuplicateFileError with user-friendly messages.
    """
    if not filename:
        raise FileImportError("filename is required", code="missing_filename")

    ext_map = {"." + filename.split(".")[-1].lower()}
    if not ext_map & SUPPORTED_EXTENSIONS:
        raise FileImportError(
            "unsupported file type — please upload a .csv file", code="unsupported_type"
        )

    if content_bytes and len(content_bytes) > MAX_UPLOAD_BYTES:
        raise FileImportError(f"file too large (max {MAX_UPLOAD_BYTES} bytes)", code="file_too_large")

    digest = sha256_of_bytes(content_bytes or content.encode("utf-8"))
    existing = File.objects.filter(source=source, sha256=digest).first()
    if existing is not None:
        raise DuplicateFileError(
            f"'{filename}' is a duplicate of already-imported file '{existing.filename}' "
            f"(SHA-256 {digest[:12]}…). No new records created.",
            existing_file=existing,
        )

    parser = _parser_for_source(source)
    try:
        transactions = parser.parse(content)
    except ParseError as exc:
        raise FileImportError(str(exc), code="parse_error") from exc

    if not transactions:
        raise FileImportError(
            "file parsed successfully but contained no transactions", code="empty_file"
        )

    new_file = File.objects.create(filename=filename, source=source, sha256=digest)
    in_mem = {}
    for tx in transactions:
        _get_or_create_transaction(
            in_mem,
            source,
            tx.source_transaction_id,
            transaction_time=tx.transaction_time,
            instrument=tx.instrument,
            side=tx.side,
            quantity=tx.quantity,
            price=tx.price,
            amount=tx.amount,
            status=tx.status,
            raw_data=tx.raw_data,
            file=new_file,
        )
    new_file.record_count = len(transactions)
    new_file.save(update_fields=["record_count"])

    # Return count of records that were brand-new (created) this upload.
    return new_file