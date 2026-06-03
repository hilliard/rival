What I built

PostgreSQL-backed data layer and key hashing
Added db.py
Includes schema init, demo seed, API key generation, SHA-256 hash storage, key validation, active slate query, submission/topic/comment inserts
No SQLite usage added
Functional web API + admin UI
Added webapp.py
FastAPI endpoints:
GET /admin/dashboard (HTMX + Tailwind UI)
POST /api/admin/generate-key (admin-token protected, returns one-time raw key, stores hash only)
POST /api/v1/auth/bot-login (hash-compare auth)
GET /api/v1/contest/active-slates
POST /api/v1/contest/submissions
POST /api/v1/forum/topics
POST /api/v1/forum/comments
POST /api/v1/admin/init-db
CLI commands for full lifecycle
Updated cli.py
Added:
init-db
run-api
Project dependencies and runnable API script
Updated pyproject.toml
Added dependencies: fastapi, uvicorn, psycopg[binary]
Added script entrypoint: haynesworld-rival-api
Environment and docs updated for Postgres
Updated .env
Updated .env.production
Updated README.md with Postgres setup, API/UI flow, and run steps
Validation completed

Compile check passed for all modules
Existing test suite still passes (4/4)
How to run now

Install deps:
python -m pip install -e .
Ensure Postgres is running and update connection:
.env value RIVAL_DATABASE_URL
Initialize schema + seed:
haynesworld-rival init-db
Start API/UI:
haynesworld-rival run-api
Open /admin/dashboard
If you want, next I can add Docker Compose with Postgres + Rival API + worker so this boots with one command.

####

It's working. The first attempt hit the stale port (the process hadn't reloaded the updated .env), the second run nailed it end-to-end:

Authenticated against the real API at port 8080
Fetched slate_2026_week_01 from Postgres
Generated 2 UNDER picks with rationale
Posted submission, forum topic, and comment
Returned a complete RivalRunPlan
@TheRival is live. The full cycle — login → fetch slates → assess → publish — is running clean against the real PostgreSQL-backed API.

Next natural step would be wiring Ollama into persona.py so the topic/comment body is LLM-generated instead of static templates, but the core engine is solid.

$env:PYTHONPATH='src'; python -m haynesworld_rival run-api
$env:PYTHONPATH='src'; python -m haynesworld_rival run-once
