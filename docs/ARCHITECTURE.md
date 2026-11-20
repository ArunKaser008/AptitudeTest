# Architecture

## Product boundary

The MVP serves anonymous student assessment and practice flows plus protected question-bank administration. Student identity is optional. College and TPO workflows are future extensions; the schema and API are versioned so those capabilities can be added without making them prerequisites for the student MVP.

## Repository layout

- `frontend/`: React 19, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Zustand, React Hook Form, Zod, Recharts, and Lucide.
- `backend/`: FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic, PostgreSQL driver.
- `docs/`: architecture, database and API contracts, and development guidance.
- `docker-compose.yml`: local PostgreSQL and API services.

## Runtime shape

The browser uses feature-oriented React screens and calls typed API services. TanStack Query owns remote request caching; local state is limited to interface and in-progress interactions. A candidate token identifies an anonymous session and is never a sequential database ID.

The API is organized as routers and validation schemas over application services, repositories, and SQLAlchemy models. Domain services own assessment lifecycle rules, scoring, result aggregation, and recommendation inputs. PostgreSQL is authoritative for timing, configuration versions, answer records, scoring, and submission state. AI services are optional; they cannot modify a verified answer or scoring policy.

## Versioning and lifecycle invariants

1. Published question versions and assessment configuration versions are immutable.
2. Starting an attempt pins the applicable assessment config and question versions; question selection is randomized per candidate attempt and avoids previously delivered eligible questions until that candidate's available pool cycles.
3. Candidate question payloads omit answer keys and explanations until release policy permits them.
4. Response saves are scoped to the candidate session and attempt; submissions are idempotent.
5. Server timestamps and deadlines determine validity. Browser timers are display-only.
6. Scoring is deterministic and policy-driven; readiness is a learning indicator, not hiring probability.
7. Company assessments are labeled MentorMuni practice simulations and retain public source/review metadata.

## Brand and UI direction

The inspected MentorMuni homepage uses a deep navy canvas, white typography, warm amber calls to action, and a blue/teal-and-gold logo. The app carries this direction into a high-contrast dark workspace, retaining MentorMuni blue `#1A8FC4` for progress and information accents. Inter and Rethink Sans are used for readable body text and headings.

## Initial implementation boundary

The frontend demo data is isolated in `frontend/src/data/mockData.ts` and `frontend/src/data/assessmentQuestionBanks.ts`, and explicitly labeled in the UI. Foundation, Advanced, and Company-style previews each draw from their own 20-question sample pool. Each 10-question set follows its assessment's section distribution and avoids recently used questions in the current browser tab until that assessment's pool cycles. The exact selected IDs flow through navigation, refresh recovery, submission, and results. Preview duration scales the configured full-assessment duration by the preview question count (10 minutes for Foundation; 15 minutes for Advanced and Company-style). Assessment attempts use an absolute deadline; practice sets are timed at one minute per selected question. Deadline checks recalculate after focus/visibility changes so time cannot be paused by refresh or backgrounding. Preview attempt state/history use `sessionStorage` only and are not candidate identity or production persistence. API requests and database persistence are not yet integrated. The API currently provides health/OpenAPI only. Both flows must not be used for real candidate evaluation.

## Future extension points

- Authentication providers and admin roles.
- Organization/college tenancy and TPO dashboards.
- Technical/coding assessments and AI interview capabilities.
- Redis and worker queue for asynchronous imports and AI work when warranted.
- Analytics aggregation tables/materialized views at measured scale.
