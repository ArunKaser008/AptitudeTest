# API contracts

Base path: `/api/v1`. FastAPI publishes the live OpenAPI schema at `/openapi.json` and Swagger UI at `/docs`. Request/response models reject unknown fields. The assessment catalog is empty until verified questions are assigned to a ready, published assessment.

## Candidate assessment API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/candidate-sessions` | Create an anonymous candidate session |
| `GET` | `/assessments` | List published, ready assessments |
| `POST` | `/attempts` | Start or resume an attempt using an `Idempotency-Key` |
| `GET` | `/attempts/{attempt_id}` | Read owned attempt state, questions, and server deadline |
| `PUT` / `DELETE` | `/attempts/{attempt_id}/responses/{question_id}` | Save or clear a validated response |
| `PATCH` | `/attempts/{attempt_id}/position` | Navigate questions and record dwell time |
| `PATCH` | `/attempts/{attempt_id}/questions/{question_id}/review` | Set a review flag |
| `POST` | `/attempts/{attempt_id}/submit` | Atomically record active-question time and finalize a result |
| `GET` | `/attempts/{attempt_id}/results` | Read the immutable result snapshot |
| `POST` | `/practice-weak-topics` | Start an idempotent focused practice attempt from weak topics |

Candidate endpoints (except candidate-session creation and public catalog reads) require `X-Candidate-Token`. Attempt creation and weak-topic practice require an `Idempotency-Key`. Supported question types are `single_choice`, `multi_choice`, and `numeric`; optional structured stimuli support passages, tables, and code.

## Authoring API

| Method | Path | Purpose |
|---|---|---|
| `GET` / `POST` | `/authoring/questions` | Filter/paginate the question bank or create a draft |
| `PUT` | `/authoring/questions/{question_id}` | Edit a draft or fork a new draft version |
| `POST` | `/authoring/questions/{question_id}/verify-publish` | Validate and publish a question version |
| `POST` | `/authoring/questions/{question_id}/archive` | Soft-archive a question version |
| `POST` | `/authoring/questions/bulk-import` | Validate or import JSON/CSV rows |
| `GET` / `POST` | `/authoring/assessments` | List readiness or create a draft assessment |
| `POST` | `/authoring/assessments/{assessment_id}/clone` | Clone a draft with its configuration and pools |
| `PUT` | `/authoring/assessments/{assessment_id}/config` | Update a draft or fork a configuration version |
| `PUT` | `/authoring/sections/{section_id}/pool` | Replace a section's question pool |
| `POST` | `/authoring/assessments/{assessment_id}/publish` | Publish a ready assessment configuration |

**Security boundary:** these authoring routes currently have no admin authentication or authorization. The studio is for private development use only; add and enforce admin access controls before any public deployment.

## Lifecycle guarantees

- Candidate attempt ownership, server deadlines, locking, scoring, and idempotent submission are enforced by the API.
- Submissions persist an immutable result snapshot; defaults allow older snapshots without topic/time diagnostics to deserialize.
- Published question content is edited by creating a new version. Published assessment configurations are forked before editing.
- Assessment/question references use restrictive foreign keys; archival is soft and does not delete referenced records.
- Readiness and scores are computed server-side. The client cannot set authoritative scores, publication readiness, or deadlines.
