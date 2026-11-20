# MentorMuni Placement Aptitude

MentorMuni Placement Aptitude is a placement-readiness assessment product organized around **Measure → Improve → Prove**.

## Current status

- The React + TypeScript workspace includes an assessment catalog, server-backed timed exams and results with topic/time diagnostics, and an assessment authoring studio.
- The FastAPI + PostgreSQL backend supports versioned assessments and questions, verified question pools, CSV/JSON imports, multi-choice and numeric questions, immutable result snapshots, and weak-topic practice.
- Dashboard, practice-zone, analytics, company-simulation, and recommendation areas still include sample data; do not treat them as candidate evaluation records.
- A fresh database intentionally has no published assessments. Create and review content in `/aptitude/manage` before publishing.
- The separate `/placement` portal provides bearer-token login, tenant-scoped college workspaces, question review, test generation/import, cohort assignments, student test attempts, and submitted-attempt analytics. It does not replace the existing candidate assessment routes.
- **Deployment boundary:** the legacy authoring APIs and `/aptitude/manage` workspace do not have authentication/authorization yet. Keep the legacy authoring surface private; use `/placement` for role-protected placement authoring.

## Run locally

Requirements: Node.js 20+, Python 3.12+, and Docker Compose (for PostgreSQL).

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

In another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

The web app is at `http://localhost:5173`; FastAPI and its interactive docs are at `http://localhost:8000` and `http://localhost:8000/docs`.
Compose waits for PostgreSQL, applies Alembic migrations, and then starts the API. The assessment catalog will show an empty state until verified question content and a published assessment are loaded; no sample assessment data is seeded.
The database is exposed on host port `5433` to avoid colliding with an existing local PostgreSQL service. The API container connects to PostgreSQL over the Compose network.

## Placement portal setup

The placement portal is available at `http://localhost:5173/placement`. It uses a separate placement bearer token stored for the current browser session; it does not reuse candidate-session tokens.

After Compose has started, create the initial platform administrator from PowerShell:

```powershell
$env:PLATFORM_ADMIN_EMAIL = "admin@example.com"
$env:PLATFORM_ADMIN_PASSWORD = "<use-a-unique-password-of-at-least-12-characters>"
docker compose exec -e PLATFORM_ADMIN_EMAIL -e PLATFORM_ADMIN_PASSWORD api python -m app.placement_seed
Remove-Item Env:PLATFORM_ADMIN_EMAIL
Remove-Item Env:PLATFORM_ADMIN_PASSWORD
```

Sign in at `/placement`, create a college and batch, then provision college-admin or student accounts. College admins can create and review questions, generate or extract draft content, publish tests, and assign them to cohorts. Students can start assigned tests, save answers, submit, and review their score, topic timing, and solutions. Set a unique `PLACEMENT_AUTH_SECRET` in `.env` before deployment; production configuration rejects the development secret.

Question extraction accepts pasted text or PDF, DOCX, CSV, and TXT uploads (up to 10 MB). Generated/imported questions remain drafts until a human approves them. Configure `LLM_API_KEY` for hosted structured generation; without it, the deterministic generator supports local development.

Run frontend validation:

```powershell
Set-Location frontend
npm test
npm run build
```

Run backend tests from the repository root:

```powershell
python -m pip install -r backend\requirements-dev.txt
Set-Location backend
python -m pytest
```

See [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md), and [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) for implementation details and current boundaries.
