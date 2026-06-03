from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import RivalSettings
from .contracts import RivalRunPlan
from .version import SCHEMA_VERSION


def hash_api_key(raw_key: str) -> str:
    return sha256(raw_key.encode("utf-8")).hexdigest()


def generate_rival_api_key(prefix: str = "rival") -> str:
    return f"{prefix}_{secrets.token_hex(24)}"


@dataclass(slots=True)
class RivalDatabase:
    settings: RivalSettings

    def connect(self) -> Connection:
        return Connection.connect(self.settings.database_url, row_factory=dict_row)

    def init_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id BIGSERIAL PRIMARY KEY,
            schema_version TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            api_key_hash TEXT
        );

        CREATE TABLE IF NOT EXISTS slates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lock_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS slate_matches (
            id BIGSERIAL PRIMARY KEY,
            slate_id TEXT NOT NULL REFERENCES slates(id) ON DELETE CASCADE,
            match_id TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            spread_home_team DOUBLE PRECISION NOT NULL,
            total_line DOUBLE PRECISION NOT NULL,
            lock_at TIMESTAMPTZ,
            UNIQUE (slate_id, match_id)
        );

        CREATE TABLE IF NOT EXISTS contest_submissions (
            id BIGSERIAL PRIMARY KEY,
            slate_id TEXT NOT NULL,
            bot_user_id TEXT NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS forum_topics (
            id BIGSERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            topic_type TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS forum_comments (
            id BIGSERIAL PRIMARY KEY,
            body TEXT NOT NULL,
            thread_id TEXT,
            parent_comment_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS rival_runs (
            id BIGSERIAL PRIMARY KEY,
            run_id TEXT UNIQUE NOT NULL,
            generated_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            model_version TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            published BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL,
            submission_count INTEGER NOT NULL DEFAULT 0,
            topic_count INTEGER NOT NULL DEFAULT 0,
            comment_count INTEGER NOT NULL DEFAULT 0,
            note_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
                cur.execute(
                    """
                    INSERT INTO schema_migrations (schema_version)
                    VALUES (%s)
                    ON CONFLICT (schema_version) DO NOTHING
                    """,
                    (SCHEMA_VERSION,),
                )
            conn.commit()

    def get_schema_version(self) -> str | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.schema_migrations') AS table_name")
                row = cur.fetchone() or {}
                if row.get("table_name") != "schema_migrations":
                    return None

                cur.execute(
                    """
                    SELECT schema_version
                    FROM schema_migrations
                    ORDER BY applied_at DESC, id DESC
                    LIMIT 1
                    """
                )
                version_row = cur.fetchone() or {}
        schema_version = version_row.get("schema_version")
        return str(schema_version) if schema_version else None

    def get_schema_applied_at(self, schema_version: str = SCHEMA_VERSION) -> datetime | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.schema_migrations') AS table_name")
                row = cur.fetchone() or {}
                if row.get("table_name") != "schema_migrations":
                    return None

                cur.execute(
                    """
                    SELECT applied_at
                    FROM schema_migrations
                    WHERE schema_version = %s
                    ORDER BY applied_at DESC, id DESC
                    LIMIT 1
                    """,
                    (schema_version,),
                )
                applied_row = cur.fetchone() or {}
        applied_at = applied_row.get("applied_at")
        return applied_at if isinstance(applied_at, datetime) else None

    def ensure_schema_compatible(self, expected_schema_version: str = SCHEMA_VERSION) -> str | None:
        current_schema_version = self.get_schema_version()
        if current_schema_version is None:
            return None
        if current_schema_version != expected_schema_version:
            raise RuntimeError(
                "Database schema version "
                f"{current_schema_version} is incompatible with expected schema version {expected_schema_version}. "
                "Run init-db or the required migration before starting the API."
            )
        return current_schema_version

    def seed_demo_data(self) -> None:
        now = datetime.now(UTC)
        lock_at = now + timedelta(hours=4)

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, username)
                    VALUES (%s, %s)
                    ON CONFLICT (id) DO UPDATE SET username = excluded.username
                    """,
                    ("bot_therival", "therival"),
                )
                cur.execute(
                    """
                    INSERT INTO slates (id, name, lock_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET name = excluded.name, lock_at = excluded.lock_at
                    """,
                    ("slate_2026_week_01", "NFL 2026 Week 1", lock_at),
                )
                cur.execute(
                    """
                    INSERT INTO slate_matches (slate_id, match_id, home_team, away_team, spread_home_team, total_line, lock_at)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s),
                        (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (slate_id, match_id) DO UPDATE SET
                        home_team = excluded.home_team,
                        away_team = excluded.away_team,
                        spread_home_team = excluded.spread_home_team,
                        total_line = excluded.total_line,
                        lock_at = excluded.lock_at
                    """,
                    (
                        "slate_2026_week_01",
                        "match_001",
                        "Lakers",
                        "Nuggets",
                        -3.5,
                        228.5,
                        lock_at,
                        "slate_2026_week_01",
                        "match_002",
                        "Celtics",
                        "Heat",
                        2.0,
                        219.0,
                        lock_at,
                    ),
                )
            conn.commit()

    def set_user_api_key_hash(self, username: str, api_key_hash: str) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET api_key_hash = %s WHERE username = %s",
                    (api_key_hash, username),
                )
            conn.commit()

    def validate_api_key(self, raw_api_key: str, username: str = "therival") -> bool:
        hashed = hash_api_key(raw_api_key)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT api_key_hash FROM users WHERE username = %s",
                    (username,),
                )
                row = cur.fetchone()
        return bool(row and row.get("api_key_hash") == hashed)

    def fetch_active_slates(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, lock_at
                    FROM slates
                    WHERE lock_at > now()
                    ORDER BY lock_at ASC
                    """
                )
                slates = cur.fetchall()

                result: list[dict[str, Any]] = []
                for slate in slates:
                    cur.execute(
                        """
                        SELECT match_id, home_team, away_team, spread_home_team, total_line, lock_at
                        FROM slate_matches
                        WHERE slate_id = %s
                        ORDER BY id ASC
                        """,
                        (slate["id"],),
                    )
                    matches = cur.fetchall()
                    result.append(
                        {
                            "slate_id": slate["id"],
                            "name": slate["name"],
                            "lock_at": slate["lock_at"].isoformat(),
                            "matches": [
                                {
                                    "match_id": m["match_id"],
                                    "home_team": m["home_team"],
                                    "away_team": m["away_team"],
                                    "spread_home_team": float(m["spread_home_team"]),
                                    "total_line": float(m["total_line"]),
                                    "lock_at": m["lock_at"].isoformat() if m["lock_at"] else None,
                                }
                                for m in matches
                            ],
                        }
                    )

                return result

    def fetch_dashboard_snapshot(self) -> dict[str, Any]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        (SELECT count(*) FROM users) AS user_count,
                        (SELECT count(*) FROM slates) AS slate_count,
                        (SELECT count(*) FROM slates WHERE lock_at > now()) AS active_slate_count,
                        (SELECT count(*) FROM slate_matches sm JOIN slates s ON s.id = sm.slate_id WHERE s.lock_at > now()) AS active_match_count,
                        (SELECT count(*) FROM contest_submissions) AS submission_count,
                        (SELECT count(*) FROM forum_topics) AS topic_count,
                        (SELECT count(*) FROM forum_comments) AS comment_count,
                        (SELECT min(lock_at) FROM slates WHERE lock_at > now()) AS next_slate_lock_at,
                        (SELECT title FROM forum_topics ORDER BY created_at DESC LIMIT 1) AS latest_topic_title,
                        (SELECT created_at FROM forum_topics ORDER BY created_at DESC LIMIT 1) AS latest_topic_at,
                        (SELECT created_at FROM contest_submissions ORDER BY created_at DESC LIMIT 1) AS latest_submission_at,
                        (SELECT created_at FROM forum_comments ORDER BY created_at DESC LIMIT 1) AS latest_comment_at
                    """
                )
                row = cur.fetchone() or {}

        def _iso(value: Any) -> str | None:
            return value.isoformat() if hasattr(value, "isoformat") and value is not None else None

        return {
            "user_count": int(row.get("user_count", 0)),
            "slate_count": int(row.get("slate_count", 0)),
            "active_slate_count": int(row.get("active_slate_count", 0)),
            "active_match_count": int(row.get("active_match_count", 0)),
            "submission_count": int(row.get("submission_count", 0)),
            "topic_count": int(row.get("topic_count", 0)),
            "comment_count": int(row.get("comment_count", 0)),
            "next_slate_lock_at": _iso(row.get("next_slate_lock_at")),
            "latest_topic_title": row.get("latest_topic_title"),
            "latest_topic_at": _iso(row.get("latest_topic_at")),
            "latest_submission_at": _iso(row.get("latest_submission_at")),
            "latest_comment_at": _iso(row.get("latest_comment_at")),
        }

    def record_run(
        self,
        plan: RivalRunPlan,
        *,
        published: bool,
        status: str,
        error_message: str | None = None,
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rival_runs (
                        run_id,
                        generated_at,
                        model_version,
                        prompt_version,
                        published,
                        status,
                        submission_count,
                        topic_count,
                        comment_count,
                        note_count,
                        error_message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        generated_at = excluded.generated_at,
                        completed_at = now(),
                        model_version = excluded.model_version,
                        prompt_version = excluded.prompt_version,
                        published = excluded.published,
                        status = excluded.status,
                        submission_count = excluded.submission_count,
                        topic_count = excluded.topic_count,
                        comment_count = excluded.comment_count,
                        note_count = excluded.note_count,
                        error_message = excluded.error_message
                    """,
                    (
                        plan.run_id,
                        plan.generated_at,
                        plan.model_version,
                        plan.prompt_version,
                        published,
                        status,
                        len(plan.submissions),
                        len(plan.topics),
                        len(plan.comments),
                        len(plan.notes),
                        error_message,
                    ),
                )
            conn.commit()

    def fetch_latest_run(self) -> dict[str, Any] | None:
        return self._fetch_latest_run_by_status()

    def fetch_latest_successful_run(self) -> dict[str, Any] | None:
        return self._fetch_latest_run_by_status(status="succeeded")

    def fetch_latest_failed_run(self) -> dict[str, Any] | None:
        return self._fetch_latest_run_by_status(status="failed")

    def fetch_recent_runs(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        completed_from: datetime | None = None,
        completed_to: datetime | None = None,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        normalized_status = status if status in {"succeeded", "failed"} else None
        filters: list[str] = []
        filter_params: list[Any] = []
        if normalized_status is not None:
            filters.append("status = %s")
            filter_params.append(normalized_status)
        if completed_from is not None:
            filters.append("completed_at >= %s")
            filter_params.append(completed_from)
        if completed_to is not None:
            filters.append("completed_at < %s")
            filter_params.append(completed_to)
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.rival_runs') AS table_name")
                row = cur.fetchone() or {}
                if row.get("table_name") != "rival_runs":
                    return {
                        "runs": [],
                        "summary": {
                            "total_runs": 0,
                            "failure_count": 0,
                            "published_count": 0,
                            "publish_rate": 0.0,
                            "latest_failure": None,
                        },
                        "limit": safe_limit,
                        "offset": safe_offset,
                        "status": normalized_status,
                        "completed_from": completed_from.isoformat() if completed_from is not None else None,
                        "completed_to": completed_to.isoformat() if completed_to is not None else None,
                        "total": 0,
                        "has_more": False,
                    }

                cur.execute(
                    f"SELECT count(*) AS total FROM rival_runs {where_sql}",
                    tuple(filter_params),
                )
                total_row = cur.fetchone() or {}
                cur.execute(
                    f"""
                    SELECT
                        COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failure_count,
                        COALESCE(SUM(CASE WHEN published THEN 1 ELSE 0 END), 0) AS published_count
                    FROM rival_runs
                    {where_sql}
                    """,
                    tuple(filter_params),
                )
                summary_row = cur.fetchone() or {}
                cur.execute(
                    f"""
                    SELECT
                        run_id,
                        generated_at,
                        completed_at,
                        model_version,
                        prompt_version,
                        published,
                        status,
                        submission_count,
                        topic_count,
                        comment_count,
                        note_count,
                        error_message
                    FROM rival_runs
                    {where_sql}
                    ORDER BY completed_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple([*filter_params, safe_limit, safe_offset]),
                )
                rows = cur.fetchall()

                latest_failure_row: dict[str, Any] | None = None
                if normalized_status != "succeeded":
                    failure_where_sql = where_sql
                    failure_params = list(filter_params)
                    if normalized_status is None:
                        failure_where_sql = f"WHERE {' AND '.join([*filters, 'status = %s'])}" if filters else "WHERE status = %s"
                        failure_params.append("failed")
                    cur.execute(
                        f"""
                        SELECT
                            run_id,
                            completed_at,
                            error_message
                        FROM rival_runs
                        {failure_where_sql}
                        ORDER BY completed_at DESC, id DESC
                        LIMIT 1
                        """,
                        tuple(failure_params),
                    )
                    latest_failure_row = cur.fetchone() or None

        def _iso(value: Any) -> str | None:
            return value.isoformat() if hasattr(value, "isoformat") and value is not None else None

        total = int(total_row.get("total", 0))
        failure_count = int(summary_row.get("failure_count", 0))
        published_count = int(summary_row.get("published_count", 0))
        runs = [
            {
                "run_id": row.get("run_id"),
                "generated_at": _iso(row.get("generated_at")),
                "completed_at": _iso(row.get("completed_at")),
                "model_version": row.get("model_version"),
                "prompt_version": row.get("prompt_version"),
                "published": bool(row.get("published")),
                "status": row.get("status"),
                "submission_count": int(row.get("submission_count", 0)),
                "topic_count": int(row.get("topic_count", 0)),
                "comment_count": int(row.get("comment_count", 0)),
                "note_count": int(row.get("note_count", 0)),
                "error_message": row.get("error_message"),
            }
            for row in rows
        ]
        latest_failure = None
        if latest_failure_row:
            latest_failure = {
                "run_id": latest_failure_row.get("run_id"),
                "completed_at": _iso(latest_failure_row.get("completed_at")),
                "error_message": latest_failure_row.get("error_message"),
            }
        return {
            "runs": runs,
            "summary": {
                "total_runs": total,
                "failure_count": failure_count,
                "published_count": published_count,
                "publish_rate": round((published_count / total) * 100, 1) if total else 0.0,
                "latest_failure": latest_failure,
            },
            "limit": safe_limit,
            "offset": safe_offset,
            "status": normalized_status,
            "completed_from": completed_from.isoformat() if completed_from is not None else None,
            "completed_to": completed_to.isoformat() if completed_to is not None else None,
            "total": total,
            "has_more": safe_offset + len(runs) < total,
        }

    def _fetch_latest_run_by_status(self, status: str | None = None) -> dict[str, Any] | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.rival_runs') AS table_name")
                row = cur.fetchone() or {}
                if row.get("table_name") != "rival_runs":
                    return None

                if status is None:
                    cur.execute(
                        """
                        SELECT
                            run_id,
                            generated_at,
                            completed_at,
                            model_version,
                            prompt_version,
                            published,
                            status,
                            submission_count,
                            topic_count,
                            comment_count,
                            note_count,
                            error_message
                        FROM rival_runs
                        ORDER BY completed_at DESC, id DESC
                        LIMIT 1
                        """
                    )
                else:
                    cur.execute(
                        """
                        SELECT
                            run_id,
                            generated_at,
                            completed_at,
                            model_version,
                            prompt_version,
                            published,
                            status,
                            submission_count,
                            topic_count,
                            comment_count,
                            note_count,
                            error_message
                        FROM rival_runs
                        WHERE status = %s
                        ORDER BY completed_at DESC, id DESC
                        LIMIT 1
                        """,
                        (status,),
                    )
                run_row = cur.fetchone()

        if not run_row:
            return None

        def _iso(value: Any) -> str | None:
            return value.isoformat() if hasattr(value, "isoformat") and value is not None else None

        return {
            "run_id": run_row.get("run_id"),
            "generated_at": _iso(run_row.get("generated_at")),
            "completed_at": _iso(run_row.get("completed_at")),
            "model_version": run_row.get("model_version"),
            "prompt_version": run_row.get("prompt_version"),
            "published": bool(run_row.get("published")),
            "status": run_row.get("status"),
            "submission_count": int(run_row.get("submission_count", 0)),
            "topic_count": int(run_row.get("topic_count", 0)),
            "comment_count": int(run_row.get("comment_count", 0)),
            "note_count": int(run_row.get("note_count", 0)),
            "error_message": run_row.get("error_message"),
        }

    def insert_submission(self, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO contest_submissions (slate_id, bot_user_id, payload) VALUES (%s, %s, %s)",
                    (payload.get("slate_id"), payload.get("bot_user_id"), Jsonb(payload)),
                )
            conn.commit()

    def insert_topic(self, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO forum_topics (title, body, topic_type) VALUES (%s, %s, %s)",
                    (payload.get("title"), payload.get("body"), payload.get("topic_type", "benchmark-drop")),
                )
            conn.commit()

    def insert_comment(self, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO forum_comments (body, thread_id, parent_comment_id) VALUES (%s, %s, %s)",
                    (payload.get("body"), payload.get("thread_id"), payload.get("parent_comment_id")),
                )
            conn.commit()
