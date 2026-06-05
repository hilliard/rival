from __future__ import annotations

from contextlib import contextmanager
from contextlib import redirect_stdout
from datetime import UTC
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest

from haynesworld_rival.client import HaynesWorldClient
from haynesworld_rival.config import RivalSettings
from haynesworld_rival.cli import main as cli_main
from haynesworld_rival.client import MockHaynesWorldClient, create_client
from haynesworld_rival.contracts import ForumCommentDraft, ForumTopicDraft
from haynesworld_rival.data_engine import RivalDataEngine


class _MockApiHandler(BaseHTTPRequestHandler):
    submissions: list[dict] = []
    topics: list[dict] = []
    comments: list[dict] = []
    auth_mode: str = "nested"

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _write_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/v1/auth/bot-login":
            request = self._read_json()
            if request.get("api_key") != "dev-rival-local-key":
                self._write_json(401, {"error": "bad key"})
                return
            if _MockApiHandler.auth_mode == "nested":
                self._write_json(200, {"data": {"access_token": "jwt-test-token"}})
                return
            self._write_json(200, {"access_token": "jwt-test-token-top"})
            return

        if self.path == "/api/v1/contest/submissions":
            _MockApiHandler.submissions.append(self._read_json())
            self._write_json(200, {"ok": True})
            return

        if self.path == "/api/v1/forum/topics":
            _MockApiHandler.topics.append(self._read_json())
            self._write_json(200, {"ok": True})
            return

        if self.path == "/api/v1/forum/comments":
            _MockApiHandler.comments.append(self._read_json())
            self._write_json(200, {"ok": True})
            return

        self._write_json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/v1/contest/active-slates":
            self._write_json(
                200,
                {
                    "slates": [
                        {
                            "slate_id": "slate_2026_week_01",
                            "name": "NFL Week 1",
                            "lock_at": "2099-09-10T16:30:00Z",
                            "matches": [
                                {
                                    "match_id": "match_001",
                                    "home_team": "Lakers",
                                    "away_team": "Nuggets",
                                    "spread_home_team": -3.5,
                                    "total_line": 228.5,
                                }
                            ],
                        }
                    ]
                },
            )
            return

        self._write_json(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


@contextmanager
def _mock_server(auth_mode: str = "nested") -> str:
    _MockApiHandler.submissions = []
    _MockApiHandler.topics = []
    _MockApiHandler.comments = []
    _MockApiHandler.auth_mode = auth_mode

    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockApiHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


class ClientParsingTests(unittest.TestCase):
    def test_fetch_parse_and_publish_shape(self) -> None:
        with _mock_server() as base_url:
            settings = RivalSettings(
                api_base_url=base_url,
                api_key="dev-rival-local-key",
                bot_username="therival",
                bot_user_id="bot_therival",
            )
            client = HaynesWorldClient(settings=settings)

            token = client.login()
            self.assertEqual(token, "jwt-test-token")

            slates = client.fetch_active_slates()
            self.assertEqual(len(slates), 1)
            self.assertEqual(slates[0].slate_id, "slate_2026_week_01")
            self.assertEqual(slates[0].matches[0].match_id, "match_001")
            self.assertEqual(slates[0].lock_at.tzinfo, UTC)

            engine = RivalDataEngine()
            submission = engine.draft_submission(slates[0], bot_user_id="bot_therival")
            client.submit_predictions(submission)
            client.post_topic(ForumTopicDraft(title="@TheRival benchmark drop", body="Benchmark body"))
            client.post_comment(ForumCommentDraft(body="Benchmark comment"))

            self.assertEqual(len(_MockApiHandler.submissions), 1)
            self.assertEqual(_MockApiHandler.submissions[0]["slate_id"], "slate_2026_week_01")
            self.assertIn(_MockApiHandler.submissions[0]["picks"][0]["selected_pick"], {"HOME_SPREAD", "AWAY_SPREAD", "OVER", "UNDER"})

    def test_login_parses_top_level_access_token(self) -> None:
        with _mock_server(auth_mode="top_level") as base_url:
            settings = RivalSettings(
                api_base_url=base_url,
                api_key="dev-rival-local-key",
                bot_username="therival",
                bot_user_id="bot_therival",
            )
            client = HaynesWorldClient(settings=settings)

            token = client.login()
            self.assertEqual(token, "jwt-test-token-top")

    def test_mock_runtime_client_uses_in_process_slates_and_records_actions(self) -> None:
        settings = RivalSettings(runtime_mode="mock")
        client = create_client(settings)

        self.assertIsInstance(client, MockHaynesWorldClient)

        slates = client.fetch_active_slates()
        self.assertEqual(len(slates), 1)
        self.assertEqual(slates[0].slate_id, "slate_2026_week_01")
        self.assertEqual(client.login_count, 1)

        engine = RivalDataEngine()
        submission = engine.draft_submission(slates[0], bot_user_id="bot_therival")
        client.submit_predictions(submission)

        self.assertEqual(len(client.submitted_predictions), 1)
        self.assertEqual(client.submitted_predictions[0]["slate_id"], "slate_2026_week_01")
        self.assertEqual(len(client.posted_topics), 0)
        self.assertEqual(len(client.posted_comments), 0)

    def test_runtime_mode_local_aliases_to_mock(self) -> None:
        client = create_client(RivalSettings(runtime_mode="local"))

        self.assertIsInstance(client, MockHaynesWorldClient)

    def test_runtime_mode_go_live_uses_real_client(self) -> None:
        client = create_client(RivalSettings(runtime_mode="go_live"))

        self.assertIsInstance(client, HaynesWorldClient)

    def test_show_config_reports_cli_runtime_mode_override(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = cli_main(["--runtime-mode", "mock", "show-config"])

        self.assertEqual(exit_code, 0)
        self.assertIn("'runtime_mode': 'mock'", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
