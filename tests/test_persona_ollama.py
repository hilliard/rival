from __future__ import annotations

from contextlib import contextmanager
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest

from haynesworld_rival.config import RivalSettings
from haynesworld_rival.contracts import ContestSubmission, SubmissionPick
from haynesworld_rival.persona import RivalPersonaEngine


class _MockOllamaHandler(BaseHTTPRequestHandler):
    response_text: str = ""
    status_code: int = 200
    request_count: int = 0

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/generate":
            self.send_response(404)
            self.end_headers()
            return

        _MockOllamaHandler.request_count += 1

        body = json.dumps({"response": self.response_text}).encode("utf-8")
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


@contextmanager
def _mock_ollama(response_text: str, status_code: int = 200) -> str:
    _MockOllamaHandler.response_text = response_text
    _MockOllamaHandler.status_code = status_code
    _MockOllamaHandler.request_count = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockOllamaHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


class PersonaOllamaTests(unittest.TestCase):
    def _submission(self) -> ContestSubmission:
        return ContestSubmission(
            slate_id="slate_2026_week_01",
            bot_user_id="bot_therival",
            picks=(
                SubmissionPick(
                    match_id="match_001",
                    selected_pick="UNDER",
                    confidence=0.8,
                    rationale="Total is inflated enough that the under is the cleaner baseline.",
                ),
            ),
        )

    def test_persona_uses_ollama_json_when_available(self) -> None:
        response_text = json.dumps(
            {
                "title": "@TheRival benchmark drop",
                "body": "The numbers are cleaner than your gut. One slate, one angle, one edge.",
                "comment": "The pick is in. Bring evidence if you want to argue.",
            }
        )
        with _mock_ollama(response_text) as base_url:
            settings = RivalSettings(ollama_base_url=base_url, ollama_model="llama3.1")
            engine = RivalPersonaEngine(settings=settings)

            topic = engine.build_topic(self._submission())
            comment = engine.build_comment(self._submission())

            self.assertEqual(topic.title, "@TheRival benchmark drop")
            self.assertIn("cleaner than your gut", topic.body)
            self.assertIn("Bring evidence", comment.body)
            self.assertEqual(_MockOllamaHandler.request_count, 1)

    def test_persona_falls_back_when_ollama_response_is_invalid(self) -> None:
        with _mock_ollama("not-json-at-all") as base_url:
            settings = RivalSettings(ollama_base_url=base_url, ollama_model="llama3.1")
            engine = RivalPersonaEngine(settings=settings)

            topic = engine.build_topic(self._submission())
            comment = engine.build_comment(self._submission())

            self.assertIn("Benchmark drop", topic.body)
            self.assertIn("bring a model, not a mood", comment.body)


if __name__ == "__main__":
    unittest.main()