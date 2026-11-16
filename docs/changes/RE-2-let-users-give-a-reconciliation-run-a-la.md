## Summary

Add optional reconciliation run labels

## What changed

Added a 100-character label to runs and migration 0004. Run creation validates and stores the optional label; run responses include it.

## Decisions

Unlabeled and existing runs use an empty string, not null. Labels retain whitespace and are validated before creating a run. The shared run serializer also exposes labels in the dashboard's latest run.

## How each criterion is met

1. The model and migration define a blank label with a 100-character maximum and empty default. `test_create_without_label` and `test_create_with_label` exercise the field; `makemigrations --check --dry-run` verifies migration consistency.
2. `TestRunCreation::test_create_with_label`, `test_create_without_label`, `test_label_too_long` and `test_invalid_label` cover persistence, boundary and rejection.
3. `TestRunListing::test_list_and_detail_return_label` checks labeled and unlabeled runs in both endpoints.
4. `test_existing_run_gets_empty_label` migrates an existing run and checks its data and detail response.
5. `TestRunCreation` covers creation with and without labels and length validation against PostgreSQL.

## How to verify

Start PostgreSQL as described in README, then run `cd backend && .venv/bin/python manage.py migrate` and, from the repository root, `backend/.venv/bin/python -m pytest`.

## Tests

- Added run creation, validation, list/detail and migration tests.
- PostgreSQL 17: `backend/.venv/bin/python -m pytest` — 61 passed; targeted run API and migration tests — 9 passed.
- `manage.py migrate --noinput` — all migrations including 0004 applied on PostgreSQL; `manage.py makemigrations --check --dry-run` — no changes; `manage.py check` — no issues. Initial migration consistency check warned that PostgreSQL was unavailable; repeated successfully after starting PostgreSQL.
- `npm run build` — passed. `git diff --check` — passed.
- `npm run lint` and `npm run typecheck` — unavailable: no such scripts. No backend lint or typecheck configuration or tools are defined by the project.

## Docs updated

README run API and test coverage sections; this change note.

## Open questions

None.
