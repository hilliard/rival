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
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

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
