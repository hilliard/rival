from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from haynesworld_rival.config import RivalSettings
from haynesworld_rival.webapp import create_app
from haynesworld_rival.version import SCHEMA_VERSION


class _FakeDatabase:
    schema_version: str | None = SCHEMA_VERSION

    def __init__(self, settings: RivalSettings) -> None:
        self.settings = settings

    def ensure_schema_compatible(self, expected_schema_version: str = SCHEMA_VERSION) -> str | None:
        if self.schema_version == "mismatch":
            raise RuntimeError(
                f"Database schema version 0.9.0 is incompatible with expected schema version {expected_schema_version}."
            )
        return self.schema_version

    def get_schema_applied_at(self, schema_version: str = SCHEMA_VERSION) -> datetime | None:
        if self.schema_version is None or self.schema_version == "mismatch":
            return None
        return datetime(2026, 6, 2, 9, 0, tzinfo=UTC)

    def fetch_dashboard_snapshot(self) -> dict[str, object]:
        return {
            "user_count": 0,
            "slate_count": 0,
            "active_slate_count": 0,
            "active_match_count": 0,
            "submission_count": 0,
            "topic_count": 0,
            "comment_count": 0,
            "next_slate_lock_at": None,
            "latest_topic_title": None,
            "latest_topic_at": None,
            "latest_submission_at": None,
            "latest_comment_at": None,
        }


class SchemaVersioningTests(unittest.TestCase):
    def test_healthz_reports_ready_schema_state(self) -> None:
        _FakeDatabase.schema_version = SCHEMA_VERSION
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDatabase):
            app = create_app(RivalSettings())
            health = app.router.routes[0].endpoint  # type: ignore[attr-defined]
            # Route order is not relied on elsewhere; use HTTP client for the real assertion.

        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDatabase):
            from fastapi.testclient import TestClient

            client = TestClient(create_app(RivalSettings()))
            response = client.get("/healthz")
            payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["schema_status"], "ready")

    def test_healthz_reports_uninitialized_schema_state(self) -> None:
        _FakeDatabase.schema_version = None
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDatabase):
            from fastapi.testclient import TestClient

            client = TestClient(create_app(RivalSettings()))
            response = client.get("/healthz")
            payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(payload["schema_version"])
        self.assertEqual(payload["schema_status"], "uninitialized")

    def test_create_app_fails_fast_on_schema_mismatch(self) -> None:
        _FakeDatabase.schema_version = "mismatch"
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDatabase):
            with self.assertRaisesRegex(RuntimeError, "incompatible with expected schema version"):
                create_app(RivalSettings())


if __name__ == "__main__":
    unittest.main()