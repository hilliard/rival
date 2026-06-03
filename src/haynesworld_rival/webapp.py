from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from .config import RivalSettings
from .db import RivalDatabase, generate_rival_api_key, hash_api_key
from .version import API_VERSION, APP_VERSION, SCHEMA_VERSION, SERVICE_NAME


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
                <a href='/admin/runs' class='rounded-full border border-white/10 px-4 py-2 text-slate-200 transition hover:border-cyan-400/50 hover:text-white'>Run History</a>
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


def _status_pill(label: str, tone: str) -> str:
    palette = {
        "good": "border-emerald-400/30 bg-emerald-400/15 text-emerald-100",
        "warn": "border-amber-400/30 bg-amber-400/15 text-amber-100",
        "bad": "border-rose-400/30 bg-rose-400/15 text-rose-100",
        "info": "border-cyan-400/30 bg-cyan-400/15 text-cyan-100",
    }
    classes = palette.get(tone, palette["info"])
    return f"<span class='rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] {classes}'>{label}</span>"


def _run_summary_card(title: str, run_data: dict[str, Any] | None, empty_message: str, tone: str) -> str:
    if not run_data:
        return (
            "<article class='rounded-3xl border border-dashed border-white/15 bg-white/5 p-5 text-sm text-slate-300'>"
            f"<p class='text-xs uppercase tracking-[0.25em] text-slate-400'>{title}</p>"
            f"<p class='mt-3'>{empty_message}</p>"
            "</article>"
        )

    return f"""
    <article class='rounded-3xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur'>
        <div class='flex items-center justify-between gap-3'>
            <p class='text-xs uppercase tracking-[0.25em] text-slate-400'>{title}</p>
            {_status_pill(str(run_data.get('status', 'unknown')), tone)}
        </div>
        <p class='mt-3 text-sm font-semibold text-white'>Run {run_data.get('run_id', 'unknown')}</p>
        <p class='mt-1 text-sm text-slate-300'>Completed {_format_iso(run_data.get('completed_at'))}</p>
        <p class='mt-3 text-sm text-slate-200'>{run_data.get('submission_count', 0)} submissions, {run_data.get('topic_count', 0)} topics, {run_data.get('comment_count', 0)} comments</p>
        <p class='mt-1 text-sm text-slate-300'>{run_data.get('error_message') or 'No error recorded.'}</p>
    </article>
    """


def _run_history_table(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "<div class='rounded-3xl border border-dashed border-white/15 bg-white/5 p-6 text-sm text-slate-300'>No worker runs have been recorded yet.</div>"

    rows_html = "".join(
        f"""
        <tr class='border-t border-white/10'>
            <td class='px-4 py-3 text-sm text-white'>{run.get('run_id', 'unknown')}</td>
            <td class='px-4 py-3 text-sm text-slate-300'>{_format_iso(run.get('completed_at'))}</td>
            <td class='px-4 py-3 text-sm'>{_status_pill(str(run.get('status', 'unknown')), 'good' if run.get('status') == 'succeeded' else 'bad')}</td>
            <td class='px-4 py-3 text-sm text-slate-300'>{'yes' if run.get('published') else 'no'}</td>
            <td class='px-4 py-3 text-sm text-slate-300'>{run.get('submission_count', 0)} / {run.get('topic_count', 0)} / {run.get('comment_count', 0)}</td>
            <td class='px-4 py-3 text-sm text-slate-300'>{run.get('model_version') or 'unknown'}</td>
            <td class='px-4 py-3 text-sm text-slate-300'>{run.get('error_message') or 'No error'}</td>
        </tr>
        """
        for run in runs
    )
    return f"""
    <div class='overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/80 shadow-2xl shadow-slate-950/30'>
        <table class='min-w-full border-collapse'>
            <thead class='bg-white/5'>
                <tr>
                    <th class='px-4 py-3 text-left text-xs uppercase tracking-[0.25em] text-slate-400'>Run ID</th>
                    <th class='px-4 py-3 text-left text-xs uppercase tracking-[0.25em] text-slate-400'>Completed</th>
                    <th class='px-4 py-3 text-left text-xs uppercase tracking-[0.25em] text-slate-400'>Status</th>
                    <th class='px-4 py-3 text-left text-xs uppercase tracking-[0.25em] text-slate-400'>Published</th>
                    <th class='px-4 py-3 text-left text-xs uppercase tracking-[0.25em] text-slate-400'>Counts S/T/C</th>
                    <th class='px-4 py-3 text-left text-xs uppercase tracking-[0.25em] text-slate-400'>Model</th>
                    <th class='px-4 py-3 text-left text-xs uppercase tracking-[0.25em] text-slate-400'>Error</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """


def _run_history_summary(summary: dict[str, Any]) -> str:
    latest_failure = summary.get("latest_failure") or {}
    latest_failure_text = (
        f"{latest_failure.get('run_id')} at {_format_iso(latest_failure.get('completed_at'))}"
        if latest_failure.get("run_id")
        else "No failures in this window"
    )
    cards = [
        ("Total runs", str(summary.get("total_runs", 0))),
        ("Failures", str(summary.get("failure_count", 0))),
        ("Publish rate", f"{summary.get('publish_rate', 0.0):.1f}%"),
        ("Latest failure", latest_failure_text),
    ]
    cards_html = "".join(
        f"""
        <article class='rounded-3xl border border-white/10 bg-white/5 p-4'>
            <p class='text-xs uppercase tracking-[0.25em] text-slate-400'>{label}</p>
            <p class='mt-3 text-lg font-semibold text-white'>{value}</p>
        </article>
        """
        for label, value in cards
    )
    return f"<section class='grid gap-4 md:grid-cols-2 xl:grid-cols-4'>{cards_html}</section>"


def _normalize_history_date(value: str) -> str:
    if not value:
        return ""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return ""
    return value


def _history_date_start(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def _history_date_end(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC) + timedelta(days=1)


def _normalize_history_preset(value: str) -> str:
    return value if value in {"last24h", "last7d", "release"} else ""


def _history_display_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).date().isoformat()


def _resolve_history_preset(
    preset: str,
    release_started_at: datetime | None,
) -> tuple[str, datetime | None, datetime | None]:
    normalized_preset = _normalize_history_preset(preset)
    now = _utc_now()
    if normalized_preset == "last24h":
        return normalized_preset, now - timedelta(hours=24), now
    if normalized_preset == "last7d":
        return normalized_preset, now - timedelta(days=7), now
    if normalized_preset == "release" and release_started_at is not None:
        return normalized_preset, release_started_at, now
    return "", None, None


def _history_query_string(
    status: str,
    limit: int,
    offset: int,
    completed_from: str,
    completed_to: str,
    preset: str,
) -> str:
    return urlencode(
        {
            "status": status,
            "limit": limit,
            "offset": offset,
            "completed_from": completed_from,
            "completed_to": completed_to,
            "preset": preset,
        }
    )


def _run_history_filters(status: str, limit: int, completed_from: str, completed_to: str, preset: str, release_preset_available: bool) -> str:
    options = [
        ("all", "All runs"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    ]
    option_html = "".join(
        f"<option value='{value}'{' selected' if value == status else ''}>{label}</option>"
        for value, label in options
    )
    preset_links = [
        ("last24h", "Last 24h"),
        ("last7d", "Last 7 days"),
    ]
    preset_html = "".join(
        f"<a href='/admin/runs?{_history_query_string(status, limit, 0, '', '', value)}' class='rounded-full border px-4 py-2 text-sm transition {'border-cyan-300 bg-cyan-400/15 text-cyan-100' if preset == value else 'border-white/10 text-slate-200 hover:border-cyan-300 hover:text-cyan-100'}'>{label}</a>"
        for value, label in preset_links
    )
    if release_preset_available:
        preset_html += (
            f"<a href='/admin/runs?{_history_query_string(status, limit, 0, '', '', 'release')}' class='rounded-full border px-4 py-2 text-sm transition {'border-cyan-300 bg-cyan-400/15 text-cyan-100' if preset == 'release' else 'border-white/10 text-slate-200 hover:border-cyan-300 hover:text-cyan-100'}'>This release window</a>"
        )
    else:
        preset_html += "<span class='rounded-full border border-white/10 px-4 py-2 text-sm text-slate-500'>This release window unavailable</span>"
    preset_html += f"<a href='/admin/runs?{_history_query_string(status, limit, 0, '', '', '')}' class='rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-300 hover:text-cyan-100'>Clear presets</a>"
    return f"""
    <div class='space-y-4 rounded-3xl border border-white/10 bg-white/5 p-4'>
        <div class='flex flex-wrap items-center gap-3'>
            <span class='text-xs uppercase tracking-[0.25em] text-slate-400'>Quick windows</span>
            {preset_html}
        </div>
        <form method='get' action='/admin/runs' class='flex flex-wrap items-end gap-4'>
        <label class='space-y-2 text-sm text-slate-300'>
            <span class='block text-xs uppercase tracking-[0.25em] text-slate-400'>Status</span>
            <select name='status' class='rounded-2xl border border-white/10 bg-slate-950 px-4 py-2 text-sm text-white'>
                {option_html}
            </select>
        </label>
        <label class='space-y-2 text-sm text-slate-300'>
            <span class='block text-xs uppercase tracking-[0.25em] text-slate-400'>Page size</span>
            <select name='limit' class='rounded-2xl border border-white/10 bg-slate-950 px-4 py-2 text-sm text-white'>
                <option value='10'{' selected' if limit == 10 else ''}>10</option>
                <option value='20'{' selected' if limit == 20 else ''}>20</option>
                <option value='50'{' selected' if limit == 50 else ''}>50</option>
            </select>
        </label>
        <label class='space-y-2 text-sm text-slate-300'>
            <span class='block text-xs uppercase tracking-[0.25em] text-slate-400'>Completed from</span>
            <input type='date' name='completed_from' value='{completed_from}' class='rounded-2xl border border-white/10 bg-slate-950 px-4 py-2 text-sm text-white' />
        </label>
        <label class='space-y-2 text-sm text-slate-300'>
            <span class='block text-xs uppercase tracking-[0.25em] text-slate-400'>Completed to</span>
            <input type='date' name='completed_to' value='{completed_to}' class='rounded-2xl border border-white/10 bg-slate-950 px-4 py-2 text-sm text-white' />
        </label>
        <input type='hidden' name='preset' value='' />
        <input type='hidden' name='offset' value='0' />
        <button type='submit' class='rounded-full bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300'>Apply</button>
        </form>
    </div>
    """


def _run_history_pagination(
    status: str,
    limit: int,
    offset: int,
    total: int,
    has_more: bool,
    completed_from: str,
    completed_to: str,
    preset: str,
) -> str:
    if total == 0:
        return ""
    previous_offset = max(0, offset - limit)
    previous_href = f"/admin/runs?{_history_query_string(status, limit, previous_offset, completed_from, completed_to, preset)}"
    next_href = f"/admin/runs?{_history_query_string(status, limit, offset + limit, completed_from, completed_to, preset)}"
    page_number = (offset // limit) + 1
    total_pages = max(1, (total + limit - 1) // limit)
    previous_link = (
        f"<a href='{previous_href}' class='rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200'>Previous</a>"
        if offset > 0
        else "<span class='rounded-full border border-white/10 px-4 py-2 text-sm text-slate-500'>Previous</span>"
    )
    next_link = (
        f"<a href='{next_href}' class='rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200'>Next</a>"
        if has_more
        else "<span class='rounded-full border border-white/10 px-4 py-2 text-sm text-slate-500'>Next</span>"
    )
    return f"""
    <div class='flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-white/10 bg-white/5 px-4 py-3'>
        <p class='text-sm text-slate-300'>Showing {offset + 1}-{min(offset + limit, total)} of {total} runs. Page {page_number} of {total_pages}.</p>
        <div class='flex items-center gap-3'>
            {previous_link}
            {next_link}
        </div>
    </div>
    """


def _run_history_html(
    run_page: dict[str, Any],
    status: str,
    completed_from: str,
    completed_to: str,
    preset: str,
    release_preset_available: bool,
) -> str:
    runs = run_page.get("runs", [])
    summary = run_page.get("summary", {})
    limit = int(run_page.get("limit", 20))
    offset = int(run_page.get("offset", 0))
    total = int(run_page.get("total", 0))
    has_more = bool(run_page.get("has_more"))
    return _site_shell_html(
        "The Rival Run History",
        f"""
        <section class='space-y-6'>
            <div class='flex items-start justify-between gap-4'>
                <div>
                    <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>Admin</p>
                    <h2 class='mt-2 text-3xl font-black tracking-tight text-white'>Worker Run History</h2>
                    <p class='mt-2 max-w-3xl text-sm text-slate-300'>A full recent history of worker executions, including successful publishes, failures, models, and recorded error messages.</p>
                </div>
                <a href='/admin/dashboard' class='rounded-full bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300'>Back to Dashboard</a>
            </div>
            {_run_history_filters(status, limit, completed_from, completed_to, preset, release_preset_available)}
            {_run_history_summary(summary)}
            {_run_history_table(runs)}
            {_run_history_pagination(status, limit, offset, total, has_more, completed_from, completed_to, preset)}
        </section>
        """,
    )


def _home_html(snapshot: dict[str, Any], diagnostics: dict[str, Any]) -> str:
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
    run_history_html = "".join(
        [
            _run_summary_card(
                "Last successful run",
                diagnostics.get("latest_successful_run"),
                "No successful worker run has been recorded yet.",
                "good",
            ),
            _run_summary_card(
                "Last failed run",
                diagnostics.get("latest_failed_run"),
                "No failed worker run has been recorded yet.",
                "bad",
            ),
        ]
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

        <section class='mt-12'>
            <div>
                <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>Worker history</p>
                <h3 class='mt-2 text-2xl font-bold text-white'>Last successful run and last failure</h3>
            </div>
            <div class='mt-6 grid gap-4 md:grid-cols-2'>
                {run_history_html}
            </div>
        </section>
        """,
    )


def _dashboard_html(diagnostics: dict[str, Any], message_html: str | None = None) -> str:
    message_block = message_html or (
        "<div class='text-sm text-slate-500 bg-slate-50 p-4 rounded-xl border border-dashed text-center'>"
        "No key shown. Generating a new key immediately invalidates the previous one."
        "</div>"
    )
    latest_run = diagnostics.get("latest_run") or {}
    schema_status = str(diagnostics.get("schema_status", "unknown"))
    schema_tone = "good" if schema_status == "ready" else "warn"
    latest_run_status = str(latest_run.get("status", "not-run")) if latest_run else "not-run"
    latest_run_tone = "good" if latest_run_status == "succeeded" else ("bad" if latest_run_status == "failed" else "warn")
    ollama_model = str(diagnostics.get("ollama_model", "unknown"))
    health_checks_html = "".join(
        (
            f"<div class='flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-3'>"
            f"<span class='text-sm text-slate-200'>{label}</span>{_status_pill(status, tone)}</div>"
        )
        for label, status, tone in [
            ("API release", f"v{diagnostics['app_version']}", "info"),
            ("API contract", diagnostics["api_version"], "info"),
            ("DB schema", schema_status, schema_tone),
            ("Ollama", ollama_model if ollama_model else "missing", "good" if ollama_model else "warn"),
            ("Worker", latest_run_status, latest_run_tone),
        ]
    )
    latest_run_html = (
        f"""
        <div class='space-y-3'>
            <div class='flex items-center justify-between gap-3'>
                <div>
                    <p class='text-sm font-semibold text-white'>Run {latest_run.get('run_id', 'unknown')}</p>
                    <p class='mt-1 text-xs text-slate-400'>Generated {_format_iso(latest_run.get('generated_at'))}, completed {_format_iso(latest_run.get('completed_at'))}</p>
                </div>
                {_status_pill(latest_run_status, latest_run_tone)}
            </div>
            <div class='grid gap-3 md:grid-cols-2'>
                <div class='rounded-2xl border border-white/10 bg-slate-900/80 p-4'>
                    <p class='text-xs uppercase tracking-[0.25em] text-slate-400'>Release</p>
                    <p class='mt-2 text-sm text-slate-200'>App {diagnostics['app_version']} / API {diagnostics['api_version']}</p>
                    <p class='mt-1 text-sm text-slate-300'>Schema {diagnostics.get('schema_version') or 'not initialized'}</p>
                </div>
                <div class='rounded-2xl border border-white/10 bg-slate-900/80 p-4'>
                    <p class='text-xs uppercase tracking-[0.25em] text-slate-400'>Run output</p>
                    <p class='mt-2 text-sm text-slate-200'>{latest_run.get('submission_count', 0)} submissions, {latest_run.get('topic_count', 0)} topics, {latest_run.get('comment_count', 0)} comments</p>
                    <p class='mt-1 text-sm text-slate-300'>Model {latest_run.get('model_version') or ollama_model} / Prompt {latest_run.get('prompt_version') or 'unknown'}</p>
                </div>
            </div>
            <div class='rounded-2xl border border-white/10 bg-slate-900/80 p-4'>
                <p class='text-xs uppercase tracking-[0.25em] text-slate-400'>Run diagnostics</p>
                <p class='mt-2 text-sm text-slate-200'>Published: {'yes' if latest_run.get('published') else 'no'} · Notes: {latest_run.get('note_count', 0)}</p>
                <p class='mt-1 text-sm text-slate-300'>{latest_run.get('error_message') or 'No runtime error recorded for the latest run.'}</p>
            </div>
        </div>
        """
        if latest_run
        else "<div class='rounded-2xl border border-dashed border-white/15 bg-slate-900/60 p-4 text-sm text-slate-300'>No worker run has been recorded yet.</div>"
    )
    worker_history_html = "".join(
        [
            _run_summary_card(
                "Last successful run",
                diagnostics.get("latest_successful_run"),
                "No successful worker run has been recorded yet.",
                "good",
            ),
            _run_summary_card(
                "Last failed run",
                diagnostics.get("latest_failed_run"),
                "No failed worker run has been recorded yet.",
                "bad",
            ),
        ]
    )
    return _site_shell_html(
        "The Rival Admin",
        f"""
        <section class='grid gap-6 xl:grid-cols-[1.1fr_0.9fr]'>
            <div class='rounded-3xl border border-white/10 bg-white/95 p-6 text-slate-900 shadow-2xl shadow-slate-950/40 md:p-8'>
                <div class='flex items-start justify-between gap-4'>
                    <div>
                        <p class='text-xs uppercase tracking-[0.3em] text-cyan-700/70'>Admin</p>
                        <h2 class='mt-2 text-3xl font-black tracking-tight'>@TheRival Control Console</h2>
                        <p class='mt-2 text-sm text-slate-600'>Generate and rotate bot API credentials, inspect release/runtime diagnostics, and verify the worker is shipping against the expected schema.</p>
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
            </div>

            <div class='rounded-3xl border border-white/10 bg-slate-950/80 p-6 shadow-2xl shadow-slate-950/40 md:p-8'>
                <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>Diagnostics</p>
                <h3 class='mt-2 text-2xl font-bold text-white'>Release and runtime status</h3>
                <div class='mt-6 grid gap-3'>
                    {health_checks_html}
                </div>
            </div>
        </section>

        <section class='mt-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]'>
            <article class='rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/40'>
                <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>Runtime</p>
                <h3 class='mt-2 text-2xl font-bold text-white'>Version lockstep</h3>
                <div class='mt-5 space-y-3 text-sm text-slate-200'>
                    <div class='rounded-2xl border border-white/10 bg-white/5 p-4'>App version: {diagnostics['app_version']}</div>
                    <div class='rounded-2xl border border-white/10 bg-white/5 p-4'>API version: {diagnostics['api_version']}</div>
                    <div class='rounded-2xl border border-white/10 bg-white/5 p-4'>DB schema version: {diagnostics.get('schema_version') or 'not initialized'}</div>
                    <div class='rounded-2xl border border-white/10 bg-white/5 p-4'>Expected schema version: {diagnostics['expected_schema_version']}</div>
                    <div class='rounded-2xl border border-white/10 bg-white/5 p-4'>Ollama model: {ollama_model}</div>
                    <div class='rounded-2xl border border-white/10 bg-white/5 p-4'>Runtime mode: {diagnostics['runtime_mode']}</div>
                </div>
            </article>
            <article class='rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/40'>
                <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>Worker</p>
                <h3 class='mt-2 text-2xl font-bold text-white'>Last worker run</h3>
                <div class='mt-5'>
                    {latest_run_html}
                </div>
            </article>
        </section>

        <section class='mt-6'>
            <article class='rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/40'>
                <p class='text-xs uppercase tracking-[0.3em] text-cyan-300/80'>History</p>
                <h3 class='mt-2 text-2xl font-bold text-white'>Worker outcomes</h3>
                <div class='mt-5 grid gap-4 md:grid-cols-2'>
                    {worker_history_html}
                </div>
            </article>
        </section>
        """,
    )


def create_app(settings: RivalSettings | None = None) -> FastAPI:
    app = FastAPI(title="HaynesWorld Rival API", version=APP_VERSION)
    resolved = settings or RivalSettings.from_env()
    db = RivalDatabase(resolved)
    resolved_schema_version = db.ensure_schema_compatible()
    release_started_at = db.get_schema_applied_at(SCHEMA_VERSION)
    schema_status = "ready" if resolved_schema_version else "uninitialized"

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "api_version": API_VERSION,
            "schema_version": resolved_schema_version,
            "expected_schema_version": SCHEMA_VERSION,
            "schema_status": schema_status,
        }

    @app.get("/version")
    def version_info() -> dict[str, Any]:
        return {
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "api_version": API_VERSION,
            "schema_version": resolved_schema_version,
            "expected_schema_version": SCHEMA_VERSION,
            "schema_status": schema_status,
        }

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        diagnostics = {
            "app_version": APP_VERSION,
            "api_version": API_VERSION,
            "schema_version": resolved_schema_version,
            "expected_schema_version": SCHEMA_VERSION,
            "schema_status": schema_status,
            "ollama_model": resolved.ollama_model,
            "runtime_mode": resolved.runtime_mode,
            "latest_run": db.fetch_latest_run(),
            "latest_successful_run": db.fetch_latest_successful_run(),
            "latest_failed_run": db.fetch_latest_failed_run(),
        }
        return _home_html(db.fetch_dashboard_snapshot(), diagnostics)

    @app.get("/admin/dashboard", response_class=HTMLResponse)
    def admin_dashboard() -> str:
        diagnostics = {
            "app_version": APP_VERSION,
            "api_version": API_VERSION,
            "schema_version": resolved_schema_version,
            "expected_schema_version": SCHEMA_VERSION,
            "schema_status": schema_status,
            "ollama_model": resolved.ollama_model,
            "runtime_mode": resolved.runtime_mode,
            "latest_run": db.fetch_latest_run(),
            "latest_successful_run": db.fetch_latest_successful_run(),
            "latest_failed_run": db.fetch_latest_failed_run(),
        }
        return _dashboard_html(diagnostics)

    @app.get("/admin/runs", response_class=HTMLResponse)
    def admin_run_history(
        status: str = "all",
        limit: int = 20,
        offset: int = 0,
        completed_from: str = "",
        completed_to: str = "",
        preset: str = "",
    ) -> str:
        selected_status = status if status in {"all", "succeeded", "failed"} else "all"
        selected_preset, preset_completed_from, preset_completed_to = _resolve_history_preset(preset, release_started_at)
        normalized_completed_from = _normalize_history_date(completed_from)
        normalized_completed_to = _normalize_history_date(completed_to)
        effective_completed_from = _history_date_start(normalized_completed_from) if selected_preset == "" else preset_completed_from
        effective_completed_to = _history_date_end(normalized_completed_to) if selected_preset == "" else preset_completed_to
        display_completed_from = normalized_completed_from if selected_preset == "" else _history_display_date(preset_completed_from)
        display_completed_to = normalized_completed_to if selected_preset == "" else _history_display_date(preset_completed_to)
        run_page = db.fetch_recent_runs(
            limit=limit,
            offset=offset,
            status=None if selected_status == "all" else selected_status,
            completed_from=effective_completed_from,
            completed_to=effective_completed_to,
        )
        return _run_history_html(
            run_page,
            selected_status,
            display_completed_from,
            display_completed_to,
            selected_preset,
            release_started_at is not None,
        )

    @app.get("/api/v1/admin/status")
    def admin_status() -> dict[str, Any]:
        return {
            **db.fetch_dashboard_snapshot(),
            "app_version": APP_VERSION,
            "api_version": API_VERSION,
            "schema_version": resolved_schema_version,
            "expected_schema_version": SCHEMA_VERSION,
            "schema_status": schema_status,
            "ollama_model": resolved.ollama_model,
            "runtime_mode": resolved.runtime_mode,
            "latest_run": db.fetch_latest_run(),
            "latest_successful_run": db.fetch_latest_successful_run(),
            "latest_failed_run": db.fetch_latest_failed_run(),
        }

    @app.get("/api/v1/admin/runs")
    def admin_runs(
        limit: int = 20,
        offset: int = 0,
        status: str = "all",
        completed_from: str = "",
        completed_to: str = "",
        preset: str = "",
    ) -> dict[str, Any]:
        selected_status = status if status in {"all", "succeeded", "failed"} else "all"
        selected_preset, preset_completed_from, preset_completed_to = _resolve_history_preset(preset, release_started_at)
        normalized_completed_from = _normalize_history_date(completed_from)
        normalized_completed_to = _normalize_history_date(completed_to)
        effective_completed_from = _history_date_start(normalized_completed_from) if selected_preset == "" else preset_completed_from
        effective_completed_to = _history_date_end(normalized_completed_to) if selected_preset == "" else preset_completed_to
        display_completed_from = normalized_completed_from if selected_preset == "" else _history_display_date(preset_completed_from)
        display_completed_to = normalized_completed_to if selected_preset == "" else _history_display_date(preset_completed_to)
        run_page = db.fetch_recent_runs(
            limit=limit,
            offset=offset,
            status=None if selected_status == "all" else selected_status,
            completed_from=effective_completed_from,
            completed_to=effective_completed_to,
        )
        return {
            **run_page,
            "status": selected_status,
            "completed_from": display_completed_from or None,
            "completed_to": display_completed_to or None,
            "preset": selected_preset or None,
        }

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
