# Transaction Reconciliation System

A web application that lets an operations/finance user reconcile transaction
records between two independently maintained systems:

- **Internal Ledger** — the company's own transaction records.
- **External Statement** — transaction records received from another company.

The two systems use different schemas, date formats, side vocabularies, and
amount conventions. The application normalizes them into a common model,
automatically matches records (exact ID, then fuzzy scoring), compares matched
records field-by-field within configurable tolerances, flags unmatched records,
and lets the user manually resolve exceptions. Manual decisions persist and
automatically apply to future runs.

**Stack:** React (Vite) · Django + Django REST Framework · PostgreSQL.

---

## Architecture

The most important design decision is **isolation of the reconciliation
engine**: the matching business logic is a pure, framework-independent Python
package at [`engine/`](engine) with **zero** knowledge of Django, the HTTP
layer, or the UI. This mirrors the PRD's recommended structure:

```
CSV files
   ↓
Provider parsers (internal / external adapters)   ← engine/parsers
   ↓
Canonical Transaction[]                            ← engine/normalization
   ↓
Reconciliation engine                              ← engine/matching
   ↓
Results[] + field differences                      ← engine/comparison
   ↓
Persistence (Django models)                        ← backend/reconciliation
   ↓
REST API (DRF)                                     ← backend/reconciliation/api
   ↓
React UI (Vite)                                    ← frontend
```

Because parsing and matching live in the engine, adding a *future provider*
means adding one CSV adapter — the reconciliation logic never changes
(PRD section 8).

### Repo layout

```
reconciliation/
├── engine/                 # Pure reconciliation engine (no Django/HTTP deps)
│   ├── normalization.py    # Canonical Transaction, side/date/decimal normalization
│   ├── rules.py            # Central tolerances (5m time, 0.01 amount)
│   ├── matching.py         # Exact-ID + scored fuzzy matching
│   ├── comparison.py       # Field-level comparison with tolerance flags
│   └── parsers/            # internal.py / external.py CSV adapters
├── backend/                # Django REST API
│   ├── config/             # settings, urls, wsgi
│   └── reconciliation/
│       ├── models.py       # Files, Transactions(+versions), Runs, Results, Resolutions
│       ├── services/       # file import, run lifecycle, manual resolution
│       ├── api/            # DRF views
│       └── management/commands/seed_demo.py
├── frontend/               # React + Vite
│   └── src/pages/          # Dashboard, ResultDetail
├── data/                   # Demo CSVs
└── docker-compose.yml      # PostgreSQL 16
```

---

## Running locally

Prerequisites: Docker, Python 3.10+, Node 18+.

```bash
# 1. Start PostgreSQL (port 5433, user recon / password recon)
docker compose up -d db

# 2. Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo          # loads data/*.csv and runs reconciliation
python manage.py runserver 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                         # http://localhost:5174
```

Open <http://localhost:5174> — the dashboard shows summary counts for the last
run and any unresolved transactions.

> The Vite dev server proxies `/api` to Django on `127.0.0.1:8000`; no CORS
> configuration is needed for local development.

### Demo walkthrough

1. Upload **internal.csv** (Internal ledger) and **external.csv**
   (External statement).
2. Click **Start New Run**.
3. The dashboard shows `7 matched · 1 discrepancy · 1 internal-only ·
   2 external-only · 1 cancelled`.
4. Open the discrepancy (L-1002 / X-9002) to see the field-level table:
   price +17, amount +170, both outside tolerance.
5. Open the unmatched internal record (L-1020), pick an external candidate,
   click **Match**.
6. Accept X-9100 as unmatched with a reason.
7. Re-run reconciliation — both decisions persist automatically.

---

## File details API

`GET /api/files/<id>` returns one uploaded file with the same fields as an
entry from `GET /api/files/list`: `id`, `filename`, `source`, `sha256`,
`uploaded_at`, and `record_count`. A nonexistent ID returns HTTP 404 with
`{"detail": "file not found"}`.

---

## Running tests

```bash
cd backend
.venv/bin/pip install pytest pytest-django
cd ..
backend/.venv/bin/python -m pytest
```

Tests cover normalization, matching (exact ID, fuzzy, tolerances, cancelled
exclusion), determinism, manual resolution overrides, and file import
(dedup, correction versioning, error handling).

---

## Decision log

- **Timestamp tolerance: ±5 minutes**, **amount tolerance: ±0.01**, defined
  centrally in `engine/rules.py` (PRD §11). Quantity, instrument and side are
  exact matches (side compared in normalized form, so `BUY` == `B`).
- **Matching** (PRD §27): cancelled records are excluded first; then exact
  transaction-ID matching (case-insensitive); then fuzzy matching scored on
  instrument (+30), side (+20), quantity (+20), time (+20) and amount (+10),
  with a minimum score of 60. **Time tolerance is a hard candidate filter** —
  two records more than 5 minutes apart cannot fuzzy-match.
- **Duplicate files** are detected by SHA-256 of the file contents, scoped per
  source (`INTERNAL`/`EXTERNAL`). Re-uploading the same file returns HTTP 409
  with "File already imported" and creates no records (PRD §17).
- **Corrected files**: uploading a CSV with the same `source +
  source_transaction_id` as an existing record archives the current version
  into `transaction_versions` and bumps the transaction's `current_version`.
  The corrected value becomes current; history is preserved (PRD §18).
- **Manual resolutions persist** in `manual_resolutions`. On every run, the
  engine loads them and overrides automatic results, so a manually matched or
  accepted-unmatched record never returns as an unresolved exception (PRD §16).
- **Date normalization** assumes naive timestamps are UTC (the demo data has no
  offsets). Aware timestamps are converted to UTC.
- **Determinism**: the same input produces the same output — candidate pools
  are iterated in sorted order and ties are broken by external transaction ID.

## What was left out (per PRD §4)

Authentication/authorization · multiple users/roles · real-time reconciliation
· distributed processing · object storage · workflows/approvals ·
email/Slack notifications · accounting adjustment automation · third-party
integrations · Excel export · advanced analytics · configurable rule UI.

## What I'd do next

- **Authentication** (Django auth) and per-user audit fields on manual
  resolutions.
- **Background reconciliation jobs** (a worker/queue) for large files, instead
  of synchronous runs.
- **S3/object storage** for raw uploads instead of hashing content in memory.
- **Configurable matching rules** via a UI, and smarter fuzzy matching
  (normalized/Levenshtein ID matching, amount proportional to price×qty).
- **Provider configuration** so new counterparts can be onboarded without code.
- **Excel export**, a P&L-style summary, and observability (structured logs,
  run metrics).