# @TheRival PRD

## Goal

Build `@TheRival` as a standalone, API-driven AI patron service that behaves like a normal HaynesWorld user while acting as a competitive, slightly smug benchmark for the community.

The service must be deployable independently from the core HaynesWorld app so it can be improved, scaled, and rolled back without affecting the main site.

## Product Summary

`@TheRival` is not part of the HaynesWorld web app runtime. It is a separate service that:

- logs in like a real user
- reads public or authorized contest data through API endpoints
- generates picks using a lightweight local data engine
- turns those picks into a persona-driven post or comment using a local/open-source LLM
- publishes its results back to HaynesWorld through the API only

## Source Documents

This PRD is based on the existing design notes in the HaynesWorld repo:

- `at-rival-architecture.md`
- `at-rival-desrcription.md`
- `at-rival-core-grading-logic.md`
- `at-rival-relational-schem4e-blueprint.md`
- `the-rival-data-model.md`

## Product Principles

- Keep the Rival isolated from HaynesWorld internals.
- Treat the Rival as a normal platform user, not a privileged insider.
- Prefer local and open-source tooling first to keep cost low.
- Keep the first version simple, deterministic, and easy to debug.
- Make the persona sharp and competitive, but still fair and non-abusive.

## Non-Goals

- No direct database access from the Rival service.
- No embedded LLM runtime inside the HaynesWorld core app.
- No complex ML training pipeline in v1.
- No real-money wagering logic.
- No attempt to make the bot perfectly accurate on day one.

## Users and Stakeholders

- HaynesWorld visitors who want a benchmark to beat.
- Internal operators who need a reliable, low-cost, independent AI service.
- The HaynesWorld app, which acts as the API host and source of truth.

## Success Metrics

- Rival can authenticate to HaynesWorld through a dedicated login flow.
- Rival can fetch active slates and submit predictions before lock time.
- Rival can publish benchmark posts and comments through API endpoints.
- Rival can run locally with Ollama and open-source tools.
- Rival failures do not block or slow the HaynesWorld app.
- Rival can be deployed independently from HaynesWorld.

## Required Architecture

The system must remain split into two deployable parts:

1. HaynesWorld core app
   - hosts UI, auth, leaderboards, and public APIs
   - validates all inbound Rival requests like any other user request
   - owns the database of record

2. Rival service
   - owns the AI workflow
   - runs the data engine, persona engine, and worker loop
   - holds its own config, logs, and API credentials

## Functional Requirements

### 1. Authentication

- The Rival must authenticate through a dedicated API login flow.
- The Rival must store and use short-lived auth tokens when calling HaynesWorld.
- The HaynesWorld app must treat Rival requests as authenticated user actions, not internal calls.

### 2. Contest Sync

- The Rival must fetch active slates from HaynesWorld.
- The Rival must read slate lock times, match IDs, and lines/spreads/totals.
- The Rival must only submit picks before the lock time.

### 3. Prediction Generation

- The Rival must generate a submission plan from slate data.
- The first version may use heuristic scoring rather than a full ML model.
- The plan must include one selected prediction per match or slate slot required by the contest rules.

### 4. Persona Generation

- The Rival must generate benchmark posts in a clinical, smug, competitive voice.
- The voice must stay within platform-safe bounds and avoid threats, harassment, or slurs.
- The persona layer should be replaceable without changing the contest logic.

### 5. Publishing

- The Rival must publish contest submissions through the API.
- The Rival must publish forum posts or comments through the API.
- The Rival must never write directly to HaynesWorld tables.

### 6. Worker Loop

- The Rival must run a worker loop that can:
  - fetch active slates
  - build a plan
  - post submissions
  - post commentary
  - record outcomes for follow-up review

### 7. Observability

- The Rival must emit logs for each run.
- The Rival must log API failures, invalid responses, and submission outcomes.
- The Rival should keep a traceable record of model version and prompt version used for each run.

### 8. Safety and Isolation

- Secrets must remain in Rival-side configuration.
- HaynesWorld should only expose the minimum API surface needed.
- The Rival should fail closed if it cannot validate slate timing or auth.

## Data and Domain Model

The Rival should model the contest domain with explicit, lightweight types:

- `ActiveSlate`
- `SlateMatch`
- `ContestSubmission`
- `SubmissionPick`
- `ForumTopicDraft`
- `ForumCommentDraft`
- `RivalRunPlan`

The Rival should preserve the distinction between:

- source data from HaynesWorld
- local decision logic
- output payloads sent back to HaynesWorld

## Implementation Phases

### Phase 1: Repo and Service Skeleton

Deliverables:

- sibling `rival` repository/folder
- Python project scaffold
- config loader
- core data contracts
- CLI entry point

Exit criteria:

- service can start locally
- `show-config` and `show-endpoints` work
- package compiles cleanly

### Phase 2: API Client Contract

Deliverables:

- auth client stub
- active slate fetch contract
- submission publish contract
- forum topic/comment publish contracts

Exit criteria:

- endpoints are represented in code
- request/response payload shapes are defined
- no direct database access is required by the Rival

### Phase 3: Data Engine

Deliverables:

- match scoring heuristic
- slate submission draft generator
- baseline confidence and rationale fields

Exit criteria:

- a slate can be turned into a deterministic submission draft
- draft output is reproducible for the same input

### Phase 4: Persona Engine

Deliverables:

- local prompt builder
- topic/comment text generation
- content guardrails

Exit criteria:

- Rival can produce a benchmark post in the expected tone
- generated language stays within safety bounds

### Phase 5: Worker Orchestration

Deliverables:

- one-shot run command
- recurring poll loop
- submission posting flow
- topic/comment posting flow

Exit criteria:

- one complete Rival cycle can run locally
- failures are logged clearly and do not crash the core app

### Phase 6: Deployment Readiness

Deliverables:

- environment variable reference
- runtime documentation
- independent deploy instructions
- basic rollback guidance

Exit criteria:

- Rival can be deployed without HaynesWorld release coupling
- operators can change model/runtime config without editing core app code

## Milestone Checklist

- [ ] Create sibling Rival repository/folder
- [ ] Define config and environment variables
- [ ] Define contest and persona contracts
- [ ] Implement API client stubs
- [ ] Implement baseline data engine
- [ ] Implement persona generator wrapper
- [ ] Implement worker orchestration
- [ ] Add logging and run metadata
- [ ] Document deployment and rollback
- [ ] Wire HaynesWorld endpoints and auth rules
- [ ] Add integration tests for the Rival workflow

## Environment Variables

Suggested Rival-side variables:

- `HAYNESWORLD_BASE_URL`
- `HAYNESWORLD_API_BASE_URL`
- `RIVAL_BOT_USERNAME`
- `RIVAL_BOT_USER_ID`
- `RIVAL_API_KEY`
- `RIVAL_RUNTIME_MODE`
- `RIVAL_POLL_INTERVAL_SECONDS`
- `RIVAL_REQUEST_TIMEOUT_SECONDS`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

## Open Questions

- Which HaynesWorld endpoints should be formalized first for the Rival?
- Should the Rival post both topic summaries and comments in v1, or only one of them?
- Should the first release use pure heuristics or a lightweight model wrapper?
- What are the minimum moderation rules for Rival-generated text?
- What metadata should be stored for prompt/model versioning?

## Definition of Done

The PRD is complete when:

- the Rival exists as a separate deployable service
- the Rival only interacts with HaynesWorld through API calls
- the Rival can fetch, draft, and submit without core app coupling
- the persona is competitive but safe
- the team has a clear phase-by-phase implementation path
