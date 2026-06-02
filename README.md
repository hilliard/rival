# HaynesWorld Rival

`HaynesWorld Rival` is the standalone AI patron service that lives beside the HaynesWorld app so it can be improved and deployed independently.

This implementation now includes a PostgreSQL-backed API service and admin UI for key management.

The service stays intentionally small at first:

- `data_engine`: turns slate data into a draft submission plan.
- `persona`: turns the plan into a sarcastic but fair forum/comment voice.
- `client`: talks to HaynesWorld only through API calls.
- `worker`: coordinates the fetch -> draft -> post loop.
- `webapp`: serves admin UI + API contract endpoints.
- `db`: persists keys, slates, submissions, and forum artifacts in PostgreSQL.

Primary source docs live in the HaynesWorld repo for reference:

- `at-rival-architecture.md`
- `at-rival-desrcription.md`
- `at-rival-core-grading-logic.md`
- `at-rival-relational-schem4e-blueprint.md`
- `the-rival-data-model.md`

Next step: wire the API client to the HaynesWorld endpoints described in the architecture doc, then connect the worker to a real Ollama-backed persona generator.

## Quick Start

1. Create and activate a Python 3.11+ virtual environment.
2. Install the package in editable mode.

```bash
python -m pip install -e .
```

3. Set environment variables.

```bash
set HAYNESWORLD_API_BASE_URL=https://haynesworld.com
set RIVAL_BOT_USERNAME=therival
set RIVAL_BOT_USER_ID=bot_therival
set RIVAL_API_KEY=replace-me
set RIVAL_POLL_INTERVAL_SECONDS=300
set RIVAL_REQUEST_TIMEOUT_SECONDS=20
set OLLAMA_BASE_URL=http://localhost:11434
set OLLAMA_MODEL=llama3.1
set RIVAL_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rival
set RIVAL_ADMIN_TOKEN=dev-admin-token
set RIVAL_API_BIND_HOST=127.0.0.1
set RIVAL_API_BIND_PORT=8080
```

4. Verify config and endpoints.

```bash
haynesworld-rival show-config
haynesworld-rival show-endpoints
```

5. Initialize PostgreSQL schema and seed demo records.

```bash
haynesworld-rival init-db
```

6. Start Rival API server and open admin UI.

```bash
haynesworld-rival run-api
```

Admin UI: http://127.0.0.1:8080/admin/dashboard

## Worker Commands

- One-shot run that publishes picks and forum content:

```bash
haynesworld-rival run-once
```

- One-shot dry run that only builds a plan:

```bash
haynesworld-rival run-once --dry-run
```

- Recurring worker loop:

```bash
haynesworld-rival poll-loop
```

## API Key Flow (PostgreSQL)

- Admin generates a key from `POST /api/admin/generate-key` (via HTMX button in dashboard).
- Raw key is shown once in the UI response partial.
- Service stores only SHA-256 hash in `users.api_key_hash`.
- Worker sends raw key to `POST /api/v1/auth/bot-login`.
- API hashes inbound key and compares against stored hash.

## Why PostgreSQL Instead of SQLite

- Better concurrent writes for worker + API traffic.
- Production-safe networking and backup story.
- Strong JSONB support for storing submission payloads.
- Closer parity with likely HaynesWorld core infrastructure.

## No-Docker Runtime (Windows + Ubuntu)

This project is designed to run natively without Docker.

- Windows 11 development: use `scripts/dev-start.ps1`.
- Ubuntu 24.04 production: use `scripts/ubuntu-setup.sh` and systemd units in `deploy/systemd`.
- Full guide: see `DEPLOYMENT-NO-DOCKER.md`.

## Current Behavior

- Authenticates through `POST /api/v1/auth/bot-login`.
- Fetches active slates through `GET /api/v1/contest/active-slates`.
- Drafts deterministic picks from spread/total heuristics.
- Fails closed on lock-time checks by skipping locked slates and matches.
- Publishes submissions, forum topics, and forum comments through API endpoints.
- Tracks run metadata (`run_id`, `model_version`, `prompt_version`) in the generated plan.
