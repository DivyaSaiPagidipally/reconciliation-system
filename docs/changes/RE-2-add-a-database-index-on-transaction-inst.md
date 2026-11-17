# Add an index on transaction instrument

## Summary
Add an index on transaction instrument

## What changed
- Declared a single-field index in `Transaction.Meta` and added migration 0004.
- Added model metadata and database index introspection tests.

## Decisions
- Used a normal Django `Index`, matching the surrounding model patterns. It does not change filtering semantics or uniqueness.

## How each criterion is met
1. `test_transaction_meta_declares_instrument_index` checks the model metadata.
2. `test_transaction_instrument_index_exists_in_database` checks the migrated database index and its column; migration 0004 was also applied, reversed, and reapplied on PostgreSQL 16.
3. The full backend pytest suite passes, including the existing tests and the two index tests.

## How to verify
- Start PostgreSQL and configure `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` as in `backend/.env.example`.
- From `backend`, run `PYTHONPATH=../engine .venv/bin/python manage.py migrate` and `PYTHONPATH=../engine .venv/bin/python manage.py makemigrations --check --dry-run`.
- From the repository root, run `backend/.venv/bin/python -m pytest`.

## Tests
- `backend/.venv/bin/python -m pytest backend/tests/test_transaction_index.py -q`: 2 passed.
- PostgreSQL 16 fresh `manage.py migrate`: all migrations applied; migration 0004 reversed to 0003 and reapplied successfully.
- `manage.py makemigrations --check --dry-run`: no changes detected.
- `backend/.venv/bin/python -m pytest` against PostgreSQL 16: 54 passed.
- `manage.py check`: no issues; `python -m py_compile` on changed Python files and `git diff --check` succeeded.
- No project typecheck or lint commands are configured.

## Docs updated
- README decision log documents the instrument index.

## Open questions
- None.
