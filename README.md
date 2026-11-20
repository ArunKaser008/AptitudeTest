# MentorMuni Placement Aptitude

MentorMuni Placement Aptitude is a placement-readiness assessment product organized around **Measure → Improve → Prove**.

## Current status

- The React + TypeScript workspace includes an assessment catalog, server-backed timed exams and results with topic/time diagnostics, and an assessment authoring studio.
- The FastAPI + PostgreSQL backend supports versioned assessments and questions, verified question pools, CSV/JSON imports, multi-choice and numeric questions, immutable result snapshots, and weak-topic practice.
- Dashboard, practice-zone, analytics, company-simulation, and recommendation areas still include sample data; do not treat them as candidate evaluation records.
- A fresh database intentionally has no published assessments. Create and review content in `/aptitude/manage` before publishing.
- **Deployment boundary:** authoring APIs and the `/aptitude/manage` workspace do not have authentication/authorization yet. Keep them private and do not expose this service publicly until admin access controls are implemented.

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
