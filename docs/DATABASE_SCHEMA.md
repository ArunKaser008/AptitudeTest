# Database schema

The target database is PostgreSQL. All schema changes will be delivered through Alembic migrations; application-generated sample data is not production seed data.

## Entity groups

| Group | Tables | Purpose |
|---|---|---|
| Optional identity | `candidates`, `candidate_sessions` | Optional student identity and anonymous sessions; store only a hash of the unguessable candidate token |
| Taxonomy | `categories`, `topics`, `subtopics`, `skill_tags`, `question_version_tags` | Configurable module/topic organization and skill labeling |
| Question bank | `question_bank_items`, `question_versions`, `question_options` | Stable logical item with immutable, reviewable versions and answer/explanation data |
| Assessments | `assessments`, `assessment_config_versions`, `assessment_sections`, `assessment_question_slots` | Reusable definitions and immutable, versioned section/marking/time/question selection configuration |
| Attempts | `assessment_attempts`, `student_responses` | Session-owned attempt with pinned config, server timestamps, response state, review flags, and time-spent data |
| Results | `attempt_results`, `section_results`, `topic_results`, `readiness_scores` | Deterministic score snapshots and explainable skill-level aggregates |
| Practice | `practice_sessions`, `practice_responses`, `question_bookmarks` | Deadline-bound topic practice, retries, history, and candidate-owned bookmarks |
| Company preparation | `companies`, `company_sources`, `company_assessment_templates` | Public-source references, review dates, and configurable practice simulations |
| Recommendations | `improvement_recommendations` | Rule-based and optionally AI-enriched next-step suggestions |
| Administration | `admin_users`, `admin_audit_events` | Protected question/configuration management and change traceability |

## Relationships

- A candidate may have zero or more sessions; anonymous use requires no candidate row.
- A candidate session owns attempts, practice sessions, and bookmarks.
- One assessment has ordered config versions. Each attempt references exactly one immutable config version.
- Config versions contain ordered sections and question slots. Each slot references a specific immutable question version.
- A logical question has multiple versions; each version has options, taxonomy, tags, correct-answer data, and explanation.
- Attempts contain one response per assigned slot and one result snapshot after submission.
- Result snapshots contain section and topic aggregates; readiness score inputs and weights are versioned by assessment policy.
- Company templates reference assessment configurations and multiple source records with reviewed dates.

## Constraints and indexes

Use UUID primary keys, `created_at`/`updated_at`, explicit status enums/check constraints, foreign keys with intentional deletion behavior, and soft archive for managed content. Add unique constraints for `(question_bank_item_id, version_number)`, `(assessment_id, version_number)`, `(attempt_id, assessment_question_slot_id)`, `(category_id, topic_slug)`, and `(topic_id, subtopic_slug)`. Index candidate session token hash, active attempt/session lookup, attempt deadline/status, question publish status/category/topic/difficulty, and company slug.

Raw token values, unnecessary personal data, and answer keys must not be exposed in logs or candidate-facing responses. Published versions are retained for audit and attempt reproducibility.
