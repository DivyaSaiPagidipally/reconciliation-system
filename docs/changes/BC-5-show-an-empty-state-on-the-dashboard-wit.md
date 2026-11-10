## Summary

Show dashboard guidance before the first run

## What changed

The dashboard shows an upload-and-start prompt when the run list is empty, instead of the unresolved/results panels. Existing run controls remain available.

## Decisions

Use the existing panel and muted text styles. Distinguish an uninitialized run list from a confirmed empty list so loading or a failed refresh does not falsely claim no runs exist.

## How each criterion is met

- No runs: `empty dashboard offers guidance instead of tables` checks the message, absence of tables and availability of the start control.
- Once a run exists: `starting a run replaces empty state with summary and results` starts a run and checks the message disappears and the summary and result tables appear.
- No backend or ResultDetail changes: verified with `git diff`; no runtime test is needed for unchanged files.
- `loading and failed refresh do not claim there are no runs` covers pending and failed initial requests.

## How to verify

Run `npm install` in `frontend`, then `npm --prefix frontend test` from the repository root. With the app running against an empty database, open the dashboard, upload/select both files and start a run; check that the guidance is replaced by the run summary and results.

## Tests

- Added three dashboard component tests in `frontend/src/pages/Dashboard.test.js` using Node's test runner and React test renderer. First frontend run: 2 passed, 1 failed due to a test assertion treating separate React text nodes as one string; corrected the assertion. Final run: 3 passed.
- `npm test` at the repository root initially failed because it is not the frontend package; reran with `--prefix frontend`.
- `npm --prefix frontend run build`: passed.
- `backend/.venv/bin/python -m pytest`: 41 passed, 11 setup errors because PostgreSQL on localhost:5433 was unavailable. Docker and PostgreSQL executables are unavailable here.
- `npm --prefix frontend run typecheck` and `npm --prefix frontend run lint`: unavailable; neither script is configured. No Python mypy or ruff executable is installed.
- `git diff --check`: passed.

## Docs updated

`README.md` describes the empty state and the frontend test command. No API documentation changes are needed.

## Open questions

None. Full PostgreSQL-backed test verification remains outstanding in an environment with the database available.
