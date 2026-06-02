from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from .config import RivalSettings
from .db import RivalDatabase, generate_rival_api_key, hash_api_key


def _dashboard_html(message_html: str | None = None) -> str:
    message_block = message_html or (
        "<div class='text-sm text-slate-500 bg-slate-50 p-4 rounded-xl border border-dashed text-center'>"
        "No key shown. Generating a new key immediately invalidates the previous one."
        "</div>"
    )
    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>The Rival Admin</title>
  <script src='https://unpkg.com/htmx.org@1.9.12'></script>
  <script src='https://cdn.tailwindcss.com'></script>
</head>
<body class='min-h-screen bg-gradient-to-br from-slate-100 via-sky-50 to-teal-100 text-slate-900'>
  <main class='mx-auto max-w-3xl p-6 md:p-10'>
    <section class='rounded-2xl border border-slate-200 bg-white/90 shadow-xl p-6 md:p-8'>
      <h1 class='text-2xl md:text-3xl font-black tracking-tight'>@TheRival Control Console</h1>
      <p class='mt-2 text-sm text-slate-600'>Generate and rotate bot API credentials, then inject them into the Rival worker runtime.</p>

      <div id='api-key-container' class='mt-6'>
        {message_block}
      </div>

      <button
        hx-post='/api/admin/generate-key'
        hx-target='#api-key-container'
        hx-swap='innerHTML'
        hx-headers='{{"X-Admin-Token": "dev-admin-token"}}'
        class='mt-6 inline-flex items-center rounded-xl bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 active:bg-sky-900 transition'
      >
        Generate New Rival API Key
      </button>
      <p class='mt-3 text-xs text-slate-500'>Set the real admin token in RIVAL_ADMIN_TOKEN and send it as X-Admin-Token.</p>
    </section>
  </main>
</body>
</html>
"""


def create_app(settings: RivalSettings | None = None) -> FastAPI:
    app = FastAPI(title="HaynesWorld Rival API", version="0.1.0")
    resolved = settings or RivalSettings.from_env()
    db = RivalDatabase(resolved)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"ok": True, "service": "rival-api"}

    @app.get("/admin/dashboard", response_class=HTMLResponse)
    def admin_dashboard() -> str:
        return _dashboard_html()

    @app.post("/api/admin/generate-key", response_class=HTMLResponse)
    async def generate_key(x_admin_token: str | None = Header(default=None)) -> str:
        if x_admin_token != resolved.admin_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

        raw_key = generate_rival_api_key()
        db.set_user_api_key_hash("therival", hash_api_key(raw_key))

        return (
            "<div class='p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-900 space-y-2'>"
            "<p class='text-sm font-bold'>Copy this key now. It cannot be retrieved again:</p>"
            f"<div class='rounded bg-white border p-2 text-xs font-mono break-all select-all'>{raw_key}</div>"
            "<p class='text-xs text-slate-600'>Store this as RIVAL_API_KEY in the worker environment.</p>"
            "</div>"
        )

    @app.post("/api/v1/auth/bot-login")
    async def bot_login(payload: dict[str, Any]) -> dict[str, Any]:
        api_key = str(payload.get("api_key", ""))
        if not api_key or not db.validate_api_key(api_key, username="therival"):
            raise HTTPException(status_code=401, detail="Invalid API key")

        expires_at = datetime.now(UTC) + timedelta(hours=1)
        token_material = f"therival:{expires_at.isoformat()}:{api_key}"
        access_token = sha256(token_material.encode("utf-8")).hexdigest()
        return {"access_token": access_token, "expires_at": expires_at.isoformat()}

    @app.get("/api/v1/contest/active-slates")
    async def active_slates() -> dict[str, Any]:
        return {"slates": db.fetch_active_slates()}

    @app.post("/api/v1/contest/submissions")
    async def create_submission(payload: dict[str, Any]) -> JSONResponse:
        required = {"slate_id", "bot_user_id", "picks"}
        if not required.issubset(payload.keys()):
            raise HTTPException(status_code=422, detail="Invalid submission payload")
        db.insert_submission(payload)
        return JSONResponse({"ok": True}, status_code=201)

    @app.post("/api/v1/forum/topics")
    async def create_topic(payload: dict[str, Any]) -> JSONResponse:
        required = {"title", "body", "topic_type"}
        if not required.issubset(payload.keys()):
            raise HTTPException(status_code=422, detail="Invalid topic payload")
        db.insert_topic(payload)
        return JSONResponse({"ok": True}, status_code=201)

    @app.post("/api/v1/forum/comments")
    async def create_comment(payload: dict[str, Any]) -> JSONResponse:
        if "body" not in payload:
            raise HTTPException(status_code=422, detail="Invalid comment payload")
        db.insert_comment(payload)
        return JSONResponse({"ok": True}, status_code=201)

    @app.post("/api/v1/admin/init-db")
    async def init_db(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
        if x_admin_token != resolved.admin_token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        db.init_schema()
        db.seed_demo_data()
        return {"ok": True}

    return app


def run() -> int:
    settings = RivalSettings.from_env()
    uvicorn.run(
        create_app(settings),
        host=settings.api_bind_host,
        port=settings.api_bind_port,
        log_level="info",
    )
    return 0
