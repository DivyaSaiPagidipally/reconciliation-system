# Summary

Index reconciliation run start times

## What changed

- Declared a `started_at` index on `ReconciliationRun` and added migration 0004.
- Added model metadata and database introspection tests.

## Decisions

Used a normal single-column Django index, consistent with existing model indexes. PostgreSQL can scan it backwards for newest-first queries; no ordering or API behavior changes.

## How each criterion is met

1. `test_run_declares_started_at_index` checks the model metadata.
2. `test_started_at_index_exists_in_database` checks the migrated database index and its column. The upgrade from 0003 to 0004 was also applied on PostgreSQL 17.
3. The existing backend tests pass in the full pytest run.

## How to verify

Start PostgreSQL using the README instructions, then run `cd backend && .venv/bin/python manage.py migrate && .venv/bin/python manage.py makemigrations --check --dry-run`. From the repository root run `backend/.venv/bin/python -m pytest`.

## Tests

- Added `backend/tests/test_run_index.py`: metadata and database index checks; targeted pytest: 2 passed.
- Full `backend/.venv/bin/python -m pytest`: 54 passed on PostgreSQL 17.
- Migrated PostgreSQL 17 to reconciliation 0003 then to latest: 0004 applied successfully. `makemigrations --check --dry-run`: no changes.
- `manage.py check`: no issues; `showmigrations reconciliation`: 0004 applied.
- No project typecheck or lint commands/configuration are defined; neither could be run as a project check.

## Docs updated

README notes the index and migration requirement. No API changes.

## Open questions

None.
