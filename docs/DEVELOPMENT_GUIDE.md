# Development guide

## Requirements

- Node.js 20 or newer and npm.
- Python 3.12 or newer.
- Docker Compose for local PostgreSQL.

## Start the services

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d db api
Set-Location frontend
npm install
npm run dev
```

The current frontend is a preview using sample data. The API exposes health and OpenAPI only; the database container is prepared for later migrations.

## Validate

```powershell
Set-Location frontend
npm test
npm run build
```

The backend currently has a focused health/OpenAPI contract test:

```powershell
Set-Location backend
python -m pip install -r requirements-dev.txt
python -m pytest
```

No live assessment should be run against the frontend preview.

## Working conventions

- Keep feature code grouped by product domain and shared UI reusable.
- Keep demo data isolated and label it; do not treat it as seed/production content.
- Use Alembic for all schema changes.
- Keep scoring deterministic and server-side.
- Do not publish unverified questions or expose answer keys prematurely.
- Update the development checklist after each completed implementation phase.

## Checklist

- [x] Repository inspection and approved architecture proposal.
- [x] Frontend/backend foundation, architecture docs, and sample-data student workspace.
- [x] Consistent 10-question assessment previews, fresh question rotation, in-tab attempt recovery, and attempt-derived results.
- [x] Separate section-balanced question pools for Foundation, Advanced, and Company-style previews; realistic 10/15/15-minute timers and responsive answer-breakdown charts.
- [x] Countdown deadlines for all assessment previews, refresh/background time recalculation, timed practice, expiry auto-submit, and MentorMuni dark-brand styling.
- [ ] Assessment APIs, persistence, secure anonymous attempt lifecycle, and scoring.
- [ ] Question-bank authoring/review and practice APIs.
- [ ] Frontend/API integration, analytics, and recommendation rules.
- [ ] Production server-authoritative timing, focused backend/frontend/E2E testing, and deployment hardening.

## Operational notes

The browser preview scales each assessment's configured full duration to its 10-question sample (Foundation 10 minutes; Advanced and Company-style 15 minutes) and uses one minute per selected question for practice. It uses assessment-specific sample banks, rotates through unseen questions in the current browser tab, and resets when a bank is exhausted. It recalculates on each tick and when the page regains visibility/focus. Its clock and browser storage are not authoritative; only server-issued deadlines and server-side expiry enforcement are suitable for live assessments.

Compose credentials are for local development only. Replace them with secrets supplied by the deployment environment before any shared or production deployment. Restrict CORS to deployed origins, protect admin routes, use TLS, and establish backups/restore tests before storing candidate data.
