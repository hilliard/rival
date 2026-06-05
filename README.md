# HaynesWorld Rival

`HaynesWorld Rival` is the standalone AI patron service that lives beside the HaynesWorld app so it can be improved and deployed independently.

This implementation includes a PostgreSQL-backed API service, a live admin UI for key management, and a home page with a live brag board.

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

Next step: harden the remaining production edges now that persona generation is fully LLM-driven.

## Quick Start

1. Create and activate a Python 3.11+ virtual environment.
2. Install the package in editable mode.

```bash
python -m pip install -e .
```

3. Set environment variables.

```bash
$env:HAYNESWORLD_API_BASE_URL = 'https://haynesworld.com'
$env:RIVAL_BOT_USERNAME = 'therival'
$env:RIVAL_BOT_USER_ID = 'bot_therival'
$env:RIVAL_API_KEY = 'replace-me'
$env:RIVAL_POLL_INTERVAL_SECONDS = '300'
$env:RIVAL_REQUEST_TIMEOUT_SECONDS = '20'
$env:RIVAL_RUNTIME_MODE = 'mock'
$env:OLLAMA_BASE_URL = 'http://localhost:11434'
$env:OLLAMA_MODEL = 'qwen2.5:1b'
$env:RIVAL_DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/rival'
$env:RIVAL_ADMIN_TOKEN = 'dev-admin-token'
$env:RIVAL_API_BIND_HOST = '127.0.0.1'
$env:RIVAL_API_BIND_PORT = '8080'
```

If you prefer Command Prompt instead of PowerShell, replace those lines with `set NAME=value`.

`RIVAL_RUNTIME_MODE` accepts `mock` for in-process prototyping and `go_live` for the real API-backed flow. You can also override the mode per command with `--runtime-mode mock` or `--runtime-mode go_live`.

For mock-mode persona generation, run the local Ollama helper in another terminal:

```bash
python scripts/mock_ollama.py --port 11434
```

If you want to keep the helper on a different port, point `OLLAMA_BASE_URL` at it before running Rival.

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
Home page: http://127.0.0.1:8080/

## Stop the API server

$pid = (Get-NetTCPConnection -LocalPort 8080).OwningProcess
Stop-Process -Id $pid -Force

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

## Local Chat Scripts

Use these helpers to test Ollama output and Rival-style prompt behavior directly in this workspace.

- Python streaming chat (inherits `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and timeout env vars):

```bash
python scripts/ollama_chat.py
```

- PowerShell streaming chat (same env defaults):

```powershell
./scripts/ollama_chat.ps1
```

Optional overrides:

```bash
python scripts/ollama_chat.py --model qwen2.5:1b --base-url http://127.0.0.1:11434 --timeout 30
```

```powershell
./scripts/ollama_chat.ps1 -Model qwen2.5:1b -BaseUrl http://127.0.0.1:11434 -TimeoutSeconds 30
```

## Runtime Modes

- `mock`: uses in-process mock slates and mock publish targets. Pair it with `scripts/mock_ollama.py` if you want persona generation to stay local too.
- `go_live`: uses the real HaynesWorld API client and the normal publish flow.
- `local`: treated as an alias for `mock`.

Example:

```bash
haynesworld-rival --runtime-mode mock run-once --dry-run
haynesworld-rival --runtime-mode go_live run-once
```

## Ollama Prerequisites (Dev + Prod)

With fallback templates removed, persona generation requires a reachable Ollama endpoint and the configured model in any environment where Rival runs.

Development options:

- Real Ollama (recommended for parity)

```bash
ollama serve
ollama pull qwen2.5:1b
ollama list
```

- Local mock helper (fast prototyping)

```bash
python scripts/mock_ollama.py --port 11434
```

Production requirement (`go_live`):

```bash
ollama serve
ollama pull qwen2.5:1b
ollama list
curl -s http://127.0.0.1:11434/api/tags
```

If `OLLAMA_MODEL` is changed, pull that exact model tag on the host before starting Rival.

Tiny-model fallback ladder (low disk VPS):

- `qwen2.5:1b` (default)
- `qwen2.5:1.5b` (use if 1b tone quality is too weak and you have extra space)
- `qwen2.5:3b` (use if you can spare more space and want stronger style consistency)

Recommended systemd pattern (Ubuntu):

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama --no-pager
```

If your host does not already provide an `ollama` unit, create one and ensure it starts before your Rival worker/API services.

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

- Serves a home page with a live brag board backed by PostgreSQL.
- Authenticates through `POST /api/v1/auth/bot-login`.
- Fetches active slates through `GET /api/v1/contest/active-slates`.
- Drafts deterministic picks from spread/total heuristics.
- Supports both mock and go_live runtime modes for prototyping and live API usage.
- Persona generation is fully LLM-driven and fails closed if Ollama does not return valid content.
- Fails closed on lock-time checks by skipping locked slates and matches.
- Publishes submissions, forum topics, and forum comments through API endpoints.
- Tracks run metadata (`run_id`, `model_version`, `prompt_version`) in the generated plan.
