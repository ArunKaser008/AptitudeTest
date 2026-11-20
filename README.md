# MentorMuni Placement Aptitude

MentorMuni Placement Aptitude is a placement-readiness assessment product organized around **Measure → Improve → Prove**. This repository is in the first implementation phase: the responsive student experience currently uses clearly identified sample data, while the API is a configured FastAPI service foundation.

## Current status

- The React + TypeScript workspace includes dashboard, assessment discovery and delivery, practice, results, analytics, company simulations, recommendations, and a question-bank preview.
- The aptitude catalog, exam, and results routes use the FastAPI assessment API. Attempts, candidate sessions, responses, server deadlines, scoring, and result snapshots are persisted in PostgreSQL.
- The remaining dashboard, practice, analytics, company, recommendation, and question-bank screens still use clearly labeled sample data.
- The production question bank is intentionally empty until verified question content is approved and loaded. The catalog therefore shows “No assessments are published yet” on a fresh install.
- The assessment API currently supports verified single-choice questions. Admin authentication and question authoring/import are not yet implemented.

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

See [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md), and [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) for the approved direction and current implementation boundaries.
