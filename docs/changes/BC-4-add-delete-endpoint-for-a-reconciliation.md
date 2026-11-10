## Summary

Add reconciliation run deletion endpoint

## What changed

`DELETE /api/reconciliation-runs/<id>` deletes the run and its results and
returns 204, or returns a 404 detail message for a missing run.

## Decisions

Extend the existing run detail view on the existing route, preserving GET and
its lookup/404 pattern. Use the model's cascade to delete results and their
field differences; files, transactions and manual resolutions remain intact.

## How each criterion is met

- Deletion and 204: `TestDeleteRun::test_delete_run_and_results` checks the run,
  result and difference are removed, the response is empty, and unrelated data
  remains.
- Missing ID and 404 detail: `TestDeleteRun::test_delete_missing_run_returns_404`.
- Both cases are pytest integration tests in `backend/tests/test_reconciliation_api.py`.
- No changes to `engine/`, `files.py`, or other endpoint implementations; the
  found test also checks GET on the existing run detail route.

## How to verify

Start PostgreSQL as described in the README and run
`backend/.venv/bin/python -m pytest` from the repository root. Send DELETE to
an existing run ID and an unused ID to check the 204 and 404 responses.

## Tests

- Added the two `TestDeleteRun` integration tests above.
- PostgreSQL targeted run: 2 setup errors; PostgreSQL on localhost:5433 was unavailable.
- PostgreSQL full suite: 41 passed, 13 setup errors due to the unavailable database.
- Temporary SQLite settings with a case-sensitive collation and reconciliation
  migrations disabled: targeted run 2 passed; full suite 54 passed. This does
  not replace PostgreSQL verification.
- `backend/.venv/bin/python backend/manage.py check`: passed.
- `git diff --check`: passed.
- No project typecheck or lint commands are configured. Frontend npm typecheck
  and lint scripts are absent; Python mypy and ruff are not installed.

## Docs updated

`README.md` documents deletion, retained data, and the 404 response.

## Open questions

None. PostgreSQL test verification remains outstanding when a database is available.
