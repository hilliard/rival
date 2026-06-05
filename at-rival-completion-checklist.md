# Rival Completion Checklist

## Status Summary

- [x] The core service exists and runs as a standalone Rival app.
- [x] The data engine produces deterministic submission drafts.
- [x] The worker can fetch, build, and publish runs end-to-end.
- [x] The persona layer is fully LLM-driven and fails closed.
- [x] Runtime modes support both mock prototyping and go_live operation.
- [~] Deployment readiness is mostly complete, but final release hardening is still advisable.

## Phase Checklist

### Phase 1: Repo and Service Skeleton

- [x] Sibling Rival repository/folder created.
- [x] Python project scaffold present.
- [x] Config loader present.
- [x] Core data contracts defined.
- [x] CLI entry point available.
- [x] Service can start locally.
- [x] `show-config` works and prints the resolved runtime mode.
- [x] `show-endpoints` works.
- [x] Package compiles cleanly.

### Phase 2: API Client Contract

- [x] Auth client stub exists.
- [x] Active slate fetch contract exists.
- [x] Submission publish contract exists.
- [x] Forum topic publish contract exists.
- [x] Forum comment publish contract exists.
- [x] Endpoints are represented in code.
- [x] Request and response shapes are defined.
- [x] No direct database access is required by the Rival.

### Phase 3: Data Engine

- [x] Match scoring heuristic implemented.
- [x] Slate submission draft generator implemented.
- [x] Baseline confidence and rationale fields included.
- [x] Draft output is deterministic for the same input.

### Phase 4: Persona Engine

- [x] Local prompt builder implemented.
- [x] Topic text generation implemented.
- [x] Comment text generation implemented.
- [x] Content guardrails are present.
- [x] LLM generation is wired in.
- [x] Static fallback templates removed from all runtime modes.
- [x] Persona output is fully LLM-driven in go_live.

### Phase 5: Worker Orchestration

- [x] One-shot run command implemented.
- [x] Recurring poll loop implemented.
- [x] Submission posting flow implemented.
- [x] Topic posting flow implemented.
- [x] Comment posting flow implemented.
- [x] One complete Rival cycle can run locally.
- [x] Failures are logged clearly.
- [x] Failures do not crash the core app.

### Phase 6: Deployment Readiness

- [x] Environment variable reference documented.
- [x] Runtime documentation exists.
- [x] Runtime mode can be switched between mock and go_live without editing code.
- [x] Independent deploy instructions exist.
- [x] Basic rollback guidance exists.
- [x] Operators can change model/runtime config without editing core app code.
- [~] Full release hardening is complete.

## PRD Requirement Checklist

- [x] Rival authenticates through a dedicated API login flow.
- [x] Rival stores and uses short-lived auth tokens when calling HaynesWorld.
- [x] HaynesWorld treats Rival requests as authenticated user actions.
- [x] Rival fetches active slates from HaynesWorld.
- [x] Rival reads slate lock times, match IDs, and lines/spreads/totals.
- [x] Rival only submits picks before the lock time.
- [x] Rival generates a submission plan from slate data.
- [x] The first version uses heuristic scoring rather than a full ML model.
- [x] The plan includes one selected prediction per required slate slot.
- [x] Rival generates benchmark posts in a clinical, smug, competitive voice.
- [x] The voice stays within platform-safe bounds.
- [x] The persona layer can be replaced without changing contest logic.
- [x] Rival publishes contest submissions through the API.
- [x] Rival publishes forum posts or comments through the API.
- [x] Rival never writes directly to HaynesWorld tables.
- [x] Rival runs a worker loop that fetches, plans, posts, and records outcomes.
- [x] Rival emits logs for each run.
- [x] Rival logs API failures, invalid responses, and submission outcomes.
- [x] Rival keeps a traceable record of model version and prompt version.
- [x] Secrets remain in Rival-side configuration.
- [x] HaynesWorld exposes only the minimum API surface needed.
- [x] Rival fails closed if it cannot validate slate timing or auth.
- [x] Rival can run in a mock mode for prototyping and a go_live mode for live API usage.

## Open Gaps

- [ ] Add any final production hardening you want before calling the service fully release-ready.

## Reference Note

This checklist is a working status view. The separate file [at-rival-completion-check.md](at-rival-completion-check.md) is the narrative reference summary.
