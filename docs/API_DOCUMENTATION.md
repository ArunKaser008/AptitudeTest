# API contracts

Base path: `/api/v1`. JSON requests and responses use Pydantic schemas and consistent error envelopes. List endpoints are paginated. Candidate routes require a high-entropy candidate-session token; admin routes require authenticated admin authorization.

## Implemented

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service liveness; currently outside the versioned domain API |

FastAPI publishes OpenAPI at `/docs` and `/openapi.json`.

## Planned domain surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/categories`, `/topics` | Read aptitude taxonomy |
| `GET` | `/api/v1/assessments` | Discover published assessment configurations |
| `POST` | `/api/v1/attempts` | Create an attempt and candidate session if needed |
| `GET` | `/api/v1/attempts/{attempt_id}` | Get owned attempt state and server-authoritative deadline |
| `GET` | `/api/v1/attempts/{attempt_id}/questions` | Get assigned questions without answer keys |
| `PUT` | `/api/v1/attempts/{attempt_id}/responses/{slot_id}` | Validate and persist a response; retry-safe |
| `POST` | `/api/v1/attempts/{attempt_id}/submit` | Submit once, calculate deterministic score, return result reference |
| `GET` | `/api/v1/attempts/{attempt_id}/results` | Get authorized results and any releasable explanations |
| `GET` | `/api/v1/analytics/overview`, `/trends` | Candidate-owned performance aggregates |
| `POST` | `/api/v1/practice-sessions` | Start timed practice and return its server-authoritative deadline |
| `POST` | `/api/v1/practice-sessions/{session_id}/responses` | Evaluate objective response immediately in practice mode |
| `GET` | `/api/v1/companies` | List sourced practice-simulation profiles |
| `GET` | `/api/v1/recommendations` | Get candidate practice recommendations |
| `GET/POST/PATCH` | `/api/v1/admin/questions` and `/api/v1/admin/assessments` | Protected content/configuration management |
| `POST` | `/api/v1/admin/imports` | Validate CSV/XLSX import before review/publication |

## Contract rules

- Error body: `{ "error": { "code": "string", "message": "string", "details": [] }, "request_id": "string" }`.
- Assessment delivery and response mutations verify token ownership and state/deadline server-side.
- All assessment and practice sessions have a server-issued deadline. Client countdowns are display-only; expired sessions cannot be extended by refresh or client clock changes.
- Use `Idempotency-Key` for attempt creation/submission; duplicate submissions return the existing final result.
- Do not accept client-computed score, readiness, or authoritative time.
- Admin content transitions require answer and explanation verification; AI output remains draft/review.
- Company simulations include a non-official status, source references, and a last-reviewed date.
