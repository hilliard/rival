from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from haynesworld_rival.config import RivalSettings
from haynesworld_rival.webapp import create_app
from haynesworld_rival.version import API_VERSION, APP_VERSION, SCHEMA_VERSION


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


class _FakeDashboardDatabase:
    def __init__(self, settings: RivalSettings) -> None:
        self.settings = settings
        self.last_fetch_recent_runs_args: dict[str, object] | None = None

    def ensure_schema_compatible(self, expected_schema_version: str = SCHEMA_VERSION) -> str | None:
        return SCHEMA_VERSION

    def get_schema_applied_at(self, schema_version: str = SCHEMA_VERSION) -> datetime | None:
        return datetime(2026, 6, 2, 9, 0, tzinfo=UTC)

    def fetch_dashboard_snapshot(self) -> dict[str, object]:
        return {
            "user_count": 1,
            "slate_count": 1,
            "active_slate_count": 1,
            "active_match_count": 2,
            "submission_count": 3,
            "topic_count": 2,
            "comment_count": 2,
            "next_slate_lock_at": None,
            "latest_topic_title": "Latest topic",
            "latest_topic_at": None,
            "latest_submission_at": None,
            "latest_comment_at": None,
        }

    def fetch_latest_run(self) -> dict[str, object] | None:
        return {
            "run_id": "run-123",
            "generated_at": "2026-06-03T12:00:00+00:00",
            "completed_at": "2026-06-03T12:01:00+00:00",
            "model_version": "llama3.1",
            "prompt_version": "rival-persona-v1",
            "published": True,
            "status": "succeeded",
            "submission_count": 1,
            "topic_count": 1,
            "comment_count": 1,
            "note_count": 4,
            "error_message": None,
        }

    def fetch_latest_successful_run(self) -> dict[str, object] | None:
        return {
            "run_id": "run-success",
            "generated_at": "2026-06-03T12:00:00+00:00",
            "completed_at": "2026-06-03T12:01:00+00:00",
            "model_version": "llama3.1",
            "prompt_version": "rival-persona-v1",
            "published": True,
            "status": "succeeded",
            "submission_count": 2,
            "topic_count": 1,
            "comment_count": 1,
            "note_count": 4,
            "error_message": None,
        }

    def fetch_latest_failed_run(self) -> dict[str, object] | None:
        return {
            "run_id": "run-failed",
            "generated_at": "2026-06-03T10:00:00+00:00",
            "completed_at": "2026-06-03T10:00:10+00:00",
            "model_version": "llama3.1",
            "prompt_version": "rival-persona-v1",
            "published": True,
            "status": "failed",
            "submission_count": 0,
            "topic_count": 0,
            "comment_count": 0,
            "note_count": 1,
            "error_message": "boom",
        }

    def fetch_recent_runs(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        completed_from: object | None = None,
        completed_to: object | None = None,
    ) -> dict[str, object]:
        self.last_fetch_recent_runs_args = {
            "limit": limit,
            "offset": offset,
            "status": status,
            "completed_from": completed_from,
            "completed_to": completed_to,
        }
        runs = [
            {
                "run_id": "run-history-1",
                "generated_at": "2026-06-03T12:00:00+00:00",
                "completed_at": "2026-06-03T12:01:00+00:00",
                "model_version": "llama3.1",
                "prompt_version": "rival-persona-v1",
                "published": True,
                "status": "succeeded",
                "submission_count": 2,
                "topic_count": 1,
                "comment_count": 1,
                "note_count": 4,
                "error_message": None,
            },
            {
                "run_id": "run-history-2",
                "generated_at": "2026-06-02T10:00:00+00:00",
                "completed_at": "2026-06-02T10:00:10+00:00",
                "model_version": "llama3.1",
                "prompt_version": "rival-persona-v1",
                "published": True,
                "status": "failed",
                "submission_count": 0,
                "topic_count": 0,
                "comment_count": 0,
                "note_count": 1,
                "error_message": "boom",
            },
            {
                "run_id": "run-history-3",
                "generated_at": "2026-06-01T08:00:00+00:00",
                "completed_at": "2026-06-01T08:00:30+00:00",
                "model_version": "llama3.1",
                "prompt_version": "rival-persona-v1",
                "published": True,
                "status": "succeeded",
                "submission_count": 1,
                "topic_count": 1,
                "comment_count": 0,
                "note_count": 2,
                "error_message": None,
            },
        ]
        if status is not None:
            runs = [run for run in runs if run["status"] == status]
        if completed_from is not None:
            lower_bound = _as_datetime(completed_from)
            runs = [
                run
                for run in runs
                if lower_bound is None or _as_datetime(run["completed_at"]) is not None and _as_datetime(run["completed_at"]) >= lower_bound
            ]
        if completed_to is not None:
            upper_bound = _as_datetime(completed_to)
            runs = [
                run
                for run in runs
                if upper_bound is None or _as_datetime(run["completed_at"]) is not None and _as_datetime(run["completed_at"]) < upper_bound
            ]
        page = runs[offset : offset + limit]
        return {
            "runs": page,
            "summary": {
                "total_runs": len(runs),
                "failure_count": len([run for run in runs if run["status"] == "failed"]),
                "published_count": len([run for run in runs if run["published"]]),
                "publish_rate": round((len([run for run in runs if run["published"]]) / len(runs)) * 100, 1) if runs else 0.0,
                "latest_failure": next(
                    (
                        {
                            "run_id": run["run_id"],
                            "completed_at": run["completed_at"],
                            "error_message": run["error_message"],
                        }
                        for run in runs
                        if run["status"] == "failed"
                    ),
                    None,
                ),
            },
            "limit": limit,
            "offset": offset,
            "status": status,
            "completed_from": str(completed_from) if completed_from is not None else None,
            "completed_to": str(completed_to) if completed_to is not None else None,
            "total": len(runs),
            "has_more": offset + len(page) < len(runs),
        }


class AdminDashboardDiagnosticsTests(unittest.TestCase):
    def test_dashboard_renders_release_runtime_and_last_run(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/admin/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn(APP_VERSION, html)
        self.assertIn(API_VERSION, html)
        self.assertIn(SCHEMA_VERSION, html)
        self.assertIn("llama3.1", html)
        self.assertIn("run-123", html)
        self.assertIn("Release and runtime status", html)
        self.assertIn("run-success", html)
        self.assertIn("run-failed", html)
        self.assertIn("Worker outcomes", html)

    def test_home_page_renders_worker_history_section(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Last successful run", html)
        self.assertIn("Last failed run", html)
        self.assertIn("run-success", html)
        self.assertIn("run-failed", html)

    def test_run_history_page_renders_recent_runs(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/admin/runs")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Worker Run History", html)
        self.assertIn("run-history-1", html)
        self.assertIn("run-history-2", html)
        self.assertIn("run-history-3", html)
        self.assertIn("All runs", html)
        self.assertIn("Page 1 of 1", html)
        self.assertIn("Last 24h", html)
        self.assertIn("Last 7 days", html)
        self.assertIn("This release window", html)
        self.assertIn("Total runs", html)
        self.assertIn("Failures", html)
        self.assertIn("Publish rate", html)
        self.assertIn("Latest failure", html)
        self.assertIn("run-history-2", html)

    def test_run_history_page_applies_last_24_hours_preset(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase), patch(
            "haynesworld_rival.webapp._utc_now",
            return_value=datetime(2026, 6, 3, 12, 5, tzinfo=UTC),
        ):
            client = TestClient(create_app(settings))
            response = client.get("/admin/runs?preset=last24h")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("run-history-1", html)
        self.assertNotIn("run-history-2", html)
        self.assertNotIn("run-history-3", html)
        self.assertIn("value='2026-06-02'", html)
        self.assertIn("value='2026-06-03'", html)

    def test_run_history_page_applies_release_window_preset(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase), patch(
            "haynesworld_rival.webapp._utc_now",
            return_value=datetime(2026, 6, 3, 12, 5, tzinfo=UTC),
        ):
            client = TestClient(create_app(settings))
            response = client.get("/admin/runs?preset=release")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("run-history-1", html)
        self.assertIn("run-history-2", html)
        self.assertNotIn("run-history-3", html)
        self.assertIn("value='2026-06-02'", html)

    def test_run_history_page_applies_status_filter(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/admin/runs?status=failed&limit=10&offset=0")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("run-history-2", html)
        self.assertNotIn("run-history-1", html)
        self.assertIn("Showing 1-1 of 1 runs", html)
        self.assertIn("Failures", html)
        self.assertIn("1", html)
        self.assertIn("100.0%", html)

    def test_run_history_page_applies_completed_date_window(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/admin/runs?completed_from=2026-06-03&completed_to=2026-06-03")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("run-history-1", html)
        self.assertNotIn("run-history-2", html)
        self.assertNotIn("run-history-3", html)
        self.assertIn("value='2026-06-03'", html)

    def test_run_history_api_returns_recent_runs(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/api/v1/admin/runs?limit=1&offset=0&status=all")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["runs"]), 1)
        self.assertEqual(payload["runs"][0]["run_id"], "run-history-1")
        self.assertEqual(payload["summary"]["total_runs"], 3)
        self.assertEqual(payload["summary"]["failure_count"], 1)
        self.assertEqual(payload["limit"], 1)
        self.assertEqual(payload["offset"], 0)
        self.assertEqual(payload["status"], "all")
        self.assertTrue(payload["has_more"])

    def test_run_history_api_filters_by_completed_date_window(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/api/v1/admin/runs?completed_from=2026-06-02&completed_to=2026-06-02")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["completed_from"], "2026-06-02")
        self.assertEqual(payload["completed_to"], "2026-06-02")
        self.assertEqual(payload["runs"][0]["run_id"], "run-history-2")

    def test_run_history_api_applies_last_7_days_preset(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase), patch(
            "haynesworld_rival.webapp._utc_now",
            return_value=datetime(2026, 6, 3, 12, 5, tzinfo=UTC),
        ):
            client = TestClient(create_app(settings))
            response = client.get("/api/v1/admin/runs?preset=last7d")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["preset"], "last7d")
        self.assertEqual(payload["completed_from"], "2026-05-27")
        self.assertEqual(payload["completed_to"], "2026-06-03")
        self.assertEqual(payload["total"], 3)

    def test_run_history_api_filters_failed_runs(self) -> None:
        settings = RivalSettings(ollama_model="llama3.1", runtime_mode="local")
        with patch("haynesworld_rival.webapp.RivalDatabase", _FakeDashboardDatabase):
            client = TestClient(create_app(settings))
            response = client.get("/api/v1/admin/runs?limit=10&offset=0&status=failed")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["runs"][0]["run_id"], "run-history-2")
        self.assertEqual(payload["summary"]["latest_failure"]["run_id"], "run-history-2")


if __name__ == "__main__":
    unittest.main()