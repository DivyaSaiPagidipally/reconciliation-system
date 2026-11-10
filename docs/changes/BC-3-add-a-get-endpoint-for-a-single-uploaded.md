## Summary

Add uploaded file detail endpoint

## What changed

Added `GET /api/files/<id>` and tests for existing and missing files.

## Decisions

Reuse `FileSerializer` and the lookup/404 pattern used by `get_run`; keep the
integer route after `files/list` and leave the existing endpoints unchanged.

## How each criterion is met

- File details use the list serializer: `TestFileDetail::test_get_uploaded_file_matches_list` uploads a file and compares the detail, list and upload representations.
- Missing IDs return a 404 detail message: `TestFileDetail::test_get_missing_file_returns_404`.
- Both cases have pytest coverage in `backend/tests/test_file_api.py`.
- No changes to `engine/` or existing endpoint implementations; the found test also exercises upload and list.

## How to verify

Start PostgreSQL as described in the README, then run
`backend/.venv/bin/python -m pytest` from the repository root. Upload a file and
request `/api/files/<id>`; request an unused numeric ID to check the 404.

## Tests

- Added the two file detail integration tests above.
- PostgreSQL targeted run: 2 setup errors; PostgreSQL on localhost:5433 was unavailable.
- PostgreSQL full suite: 41 passed, 11 setup errors due to the same unavailable database.
- Temporary SQLite settings with a case-sensitive collation and reconciliation migrations disabled: targeted run 2 passed; full suite 52 passed. This does not replace verification against PostgreSQL.
- `backend/.venv/bin/python backend/manage.py check`: passed.
- `git diff --check`: passed.
- Typecheck and lint: no project commands are configured. `npm --prefix frontend run typecheck` and `npm --prefix frontend run lint` reported missing scripts; Python mypy and ruff are not installed. Attempts to run npm scripts at the repository root also failed because there is no root package.json.

## Docs updated

`README.md` documents the endpoint, fields and 404 response, and removes the stale test count.

## Open questions

None. PostgreSQL test verification remains outstanding in an environment with the database available.
