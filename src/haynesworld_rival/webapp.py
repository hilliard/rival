from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from .config import RivalSettings
from .db import RivalDatabase, generate_rival_api_key, hash_api_key
from .version import API_VERSION, APP_VERSION, SERVICE_NAME


def _site_shell_html(title: str, body_html: str) -> str:
        return f"""
<!doctype html>
<html lang='en'>
<head>
    <meta charset='utf-8' />
    <meta name='viewport' content='width=device-width, initial-scale=1' />
    <title>{title}</title>
    <script src='https://unpkg.com/htmx.org@1.9.12'></script>
    <script src='https://cdn.tailwindcss.com'></script>
</head>
<body class='min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-sky-950 text-slate-100'>
    <div class='absolute inset-0 -z-10 overflow-hidden pointer-events-none'>
        <div class='absolute left-[-8rem] top-[-8rem] h-80 w-80 rounded-full bg-sky-500/20 blur-3xl'></div>
        <div class='absolute right-[-6rem] top-24 h-72 w-72 rounded-full bg-emerald-400/10 blur-3xl'></div>
        <div class='absolute bottom-[-7rem] left-1/3 h-96 w-96 rounded-full bg-cyan-300/10 blur-3xl'></div>
    </div>
    <header class='sticky top-0 z-20 border-b border-white/10 bg-slate-950/80 backdrop-blur'>
        <div class='mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4 md:px-8'>
            <div>
                <p class='text-xs uppercase tracking-[0.35em] text-cyan-300/80'>HaynesWorld Rival</p>
                <h1 class='text-lg font-black tracking-tight text-white'>@TheRival</h1>
            </div>
            <nav class='flex items-center gap-3 text-sm font-medium'>
                <a href='/' class='rounded-full border border-white/10 px-4 py-2 text-slate-200 transition hover:border-cyan-400/50 hover:text-white'>Home</a>
                <a href='/admin/dashboard' class='rounded-full bg-cyan-400 px-4 py-2 text-slate-950 transition hover:bg-cyan-300'>Admin Dashboard</a>
            </nav>
        </div>
    </header>
    <main class='mx-auto max-w-6xl px-6 py-10 md:px-8 md:py-14'>
        {body_html}
    </main>
    <footer class='border-t border-white/10 bg-slate-950/80'>
        <div class='mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 text-sm text-slate-400 md:flex-row md:items-center md:justify-between md:px-8'>
            <p>Built to brag, score, and post without Docker.</p>
            <p>Admin dashboard lives at <a href='/admin/dashboard' class='text-cyan-300 hover:text-cyan-200'>/admin/dashboard</a>.</p>
        </div>
    </footer>
</body>
</html>
"""


def _format_iso(value: str | None) -> str:
    if not value:
        return "not yet"
    return value.replace("T", " ").replace("+00:00", " UTC")


def _pluralize(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"


def _home_html(snapshot: dict[str, Any]) -> str:
    status_summary = (
        f"{_pluralize(snapshot['user_count'], 'user')} in the system, "
        f"{_pluralize(snapshot['slate_count'], 'slate')} total, "
        f"{_pluralize(snapshot['active_slate_count'], 'slate')} currently open, "
        f"{_pluralize(snapshot['submission_count'], 'submission')} stored, "
        f"{_pluralize(snapshot['topic_count'], 'forum topic')} posted, and "
        f"{_pluralize(snapshot['comment_count'], 'comment')} attached to the feed"
    )

    live_notes = [
        ("Users", f"{_pluralize(snapshot['user_count'], 'user')} in the system.", "That is the bot identity the worker uses."),
        ("Open slates", "No slates are open right now." if snapshot["active_slate_count"] == 0 else f"{_pluralize(snapshot['active_slate_count'], 'slate')} are open for picks.", "These are the slates the worker can act on."),
        ("Open matches", "No matches are currently inside lock time." if snapshot["active_match_count"] == 0 else f"{_pluralize(snapshot['active_match_count'], 'match')} are still open.", "A locked match is skipped by design."),
        ("Submissions", f"{_pluralize(snapshot['submission_count'], 'submission')} have been stored.", "That is the worker's pick history."),
        ("Forum topics", f"{_pluralize(snapshot['topic_count'], 'forum topic')} have been posted.", "These are the brag posts on the feed."),
        ("Comments", f"{_pluralize(snapshot['comment_count'], 'comment')} have been attached.", "This is the follow-up chatter."),
    ]
    metric_cards_html = "".join(
        f"""
        <article class='rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-slate-950/40 backdrop-blur'>
            <p class='text-sm uppercase tracking-[0.25em] text-cyan-300/80'>{title}</p>
            <p class='mt-3 text-xl font-semibold leading-8 text-white'>{value}</p>
            <p class='mt-2 text-sm text-slate-300'>{caption}</p>
        </article>
        """
        for title, value, caption in live_notes
    )

    recent_items = [
        ("Next slate lock", _format_iso(snapshot["next_slate_lock_at"])),
        ("Latest topic", snapshot["latest_topic_title"] or "No topics yet"),
        ("Latest submission", _format_iso(snapshot["latest_submission_at"])),
        ("Latest comment", _format_iso(snapshot["latest_comment_at"])),
    ]
    recent_items_html = "".join(
        f"""
        <div class='flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3'>
            <span class='text-sm font-medium text-slate-300'>{label}</span>
            <span class='text-sm text-cyan-200'>{value}</span>
        </div>
        """
        for label, value in recent_items
    )

    return _site_shell_html(
        "@TheRival | Home",
        f"""
        <section class='grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-start'>
            <div class='space-y-6'>
                <div class='inline-flex items-center rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-cyan-200'>Brag Board</div>
                <div class='space-y-4'>
                    <h2 class='max-w-3xl text-4xl font-black tracking-tight text-white md:text-6xl'>
                        The rival that actually ships picks, posts, and paperwork.
                    </h2>
                    <p class='max-w-2xl text-base leading-7 text-slate-300 md:text-lg'>
                        @TheRival is the independent patron service for HaynesWorld: a bot with an API key,
                        a PostgreSQL brain, a live admin panel, and a worker loop that can run without Docker.
                    </p>
                    <div class='rounded-3xl border border-white/10 bg-slate-900/60 p-5 text-sm leading-7 text-slate-200'>
                        <p class='font-semibold text-cyan-200'>Current snapshot</p>
                        <p class='mt-2'>
                            {status_summary}.
                        </p>
                    </div>
                </div>
                <div class='flex flex-wrap gap-3'>
                    <a href='/admin/dashboard' class='rounded-full bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300'>Open Admin Dashboard</a>
                    <a href='/api/v1/admin/status' class='rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-white/30 hover:bg-white/5'>View Status JSON</a>
                </div>
            </div>
            <aside class='rounded-[2rem] border border-white/10 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/50 backdrop-blur'>
                <p class='text-xs uppercase tracking-[0.3em] text-slate-400'>Live status</p>
                <div class='mt-4 space-y-3'>
                    <div class='rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4'>
                        <p class='text-sm font-semibold text-emerald-200'>Online</p>
                        <p class='mt-1 text-sm text-slate-300'>API, database, and worker flow are live.</p>
                    </div>
                    <div class='rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4'>
                        <p class='text-sm font-semibold text-cyan-100'>Dashboard backed by DB</p>
                        <p class='mt-1 text-sm text-slate-300'>Every number below comes from PostgreSQL on request.</p>
                    </div>
                </div>
            </aside>
        </section>

        <section class='mt-12'>
            <div class='flex items-end justify-between gap-4'>
                <div>
                    <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>Brag Board</p>
                    <h3 class='mt-2 text-2xl font-bold text-white'>Live snapshot from PostgreSQL</h3>
                </div>
                <a href='/admin/dashboard' class='hidden text-sm font-semibold text-cyan-300 hover:text-cyan-200 md:inline'>Go to admin dashboard</a>
            </div>
            <div class='mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3'>
                {metric_cards_html}
            </div>
        </section>

        <section class='mt-12 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]'>
            <article class='rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-slate-950/40 backdrop-blur'>
                <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>Current cadence</p>
                <h3 class='mt-2 text-2xl font-bold text-white'>Recent activity</h3>
                <div class='mt-5 space-y-3'>
                    {recent_items_html}
                </div>
            </article>
            <article class='rounded-[2rem] border border-white/10 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/40 backdrop-blur'>
                <p class='text-xs uppercase tracking-[0.3em] text-slate-400'>What this means</p>
                <p class='mt-3 text-sm leading-7 text-slate-300'>
                    The brag board is no longer decoration. It is a live readout of the database state behind
                    the Rival service, so the landing page reflects the same slates, picks, posts, and comments
                    the worker is operating on right now.
                </p>
                <p class='mt-4 text-sm leading-7 text-slate-300'>
                    If the next lock time changes or the worker publishes a new submission, the numbers here change
                    with the next request.
                </p>
            </article>
        </section>
        """,
    )


def _dashboard_html(message_html: str | None = None) -> str:
    message_block = message_html or (
        "<div class='text-sm text-slate-500 bg-slate-50 p-4 rounded-xl border border-dashed text-center'>"
        "No key shown. Generating a new key immediately invalidates the previous one."
        "</div>"
    )
    return _site_shell_html(
        "The Rival Admin",
        f"""
        <section class='mx-auto max-w-3xl rounded-3xl border border-white/10 bg-white/95 p-6 text-slate-900 shadow-2xl shadow-slate-950/40 md:p-8'>
            <div class='flex items-start justify-between gap-4'>
                <div>
                    <p class='text-xs uppercase tracking-[0.3em] text-cyan-700/70'>Admin</p>
                    <h2 class='mt-2 text-3xl font-black tracking-tight'>@TheRival Control Console</h2>
                    <p class='mt-2 text-sm text-slate-600'>Generate and rotate bot API credentials, then inject them into the Rival worker runtime.</p>
                </div>
                <a href='/' class='rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50'>Back to Home</a>
            </div>

            <div id='api-key-container' class='mt-6'>
                {message_block}
            </div>

            <button
                hx-post='/api/admin/generate-key'
                hx-target='#api-key-container'
                hx-swap='innerHTML'
                hx-headers='{{"X-Admin-Token": "dev-admin-token"}}'
                class='mt-6 inline-flex items-center rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 active:bg-cyan-600'
            >
                Generate New Rival API Key
            </button>
            <p class='mt-3 text-xs text-slate-500'>Set the real admin token in RIVAL_ADMIN_TOKEN and send it as X-Admin-Token.</p>
        </section>
        """,
    )


def create_app(settings: RivalSettings | None = None) -> FastAPI:
    app = FastAPI(title="HaynesWorld Rival API", version=APP_VERSION)
    resolved = settings or RivalSettings.from_env()
    db = RivalDatabase(resolved)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"ok": True, "service": SERVICE_NAME, "version": APP_VERSION, "api_version": API_VERSION}

    @app.get("/version")
    def version_info() -> dict[str, Any]:
        return {"service": SERVICE_NAME, "version": APP_VERSION, "api_version": API_VERSION}

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return _home_html(db.fetch_dashboard_snapshot())

    @app.get("/admin/dashboard", response_class=HTMLResponse)
    def admin_dashboard() -> str:
        return _dashboard_html()

    @app.get("/api/v1/admin/status")
    def admin_status() -> dict[str, Any]:
        return db.fetch_dashboard_snapshot()

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
