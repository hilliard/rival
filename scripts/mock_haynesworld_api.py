from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ALLOWED_PICKS = {"HOME_SPREAD", "AWAY_SPREAD", "OVER", "UNDER"}


def _validate_submission(payload: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload.get("slate_id"), str) or not payload["slate_id"].strip():
        errors.append("slate_id must be a non-empty string")
    if not isinstance(payload.get("bot_user_id"), str) or not payload["bot_user_id"].strip():
        errors.append("bot_user_id must be a non-empty string")

    picks = payload.get("picks")
    if not isinstance(picks, list) or not picks:
        errors.append("picks must be a non-empty array")
        return errors

    for index, pick in enumerate(picks):
        if not isinstance(pick, dict):
            errors.append(f"picks[{index}] must be an object")
            continue

        match_id = pick.get("match_id")
        selected_pick = pick.get("selected_pick")
        confidence = pick.get("confidence")
        rationale = pick.get("rationale")

        if not isinstance(match_id, str) or not match_id.strip():
            errors.append(f"picks[{index}].match_id must be a non-empty string")
        if selected_pick not in ALLOWED_PICKS:
            errors.append(f"picks[{index}].selected_pick must be one of {sorted(ALLOWED_PICKS)}")
        if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
            errors.append(f"picks[{index}].confidence must be a number between 0 and 1")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"picks[{index}].rationale must be a non-empty string")

    return errors


def _validate_topic(payload: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload.get("title"), str) or not payload["title"].strip():
        errors.append("title must be a non-empty string")
    if not isinstance(payload.get("body"), str) or not payload["body"].strip():
        errors.append("body must be a non-empty string")
    if payload.get("topic_type") != "benchmark-drop":
        errors.append("topic_type must be 'benchmark-drop'")
    return errors


def _validate_comment(payload: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload.get("body"), str) or not payload["body"].strip():
        errors.append("body must be a non-empty string")
    return errors


class MockApiHandler(BaseHTTPRequestHandler):
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

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
                self._write_json(401, {"error": "invalid api key"})
                return
            self._write_json(200, {"data": {"access_token": "jwt-dev-token"}})
            return

        if self.path == "/api/v1/contest/submissions":
            payload = self._read_json()
            errors = _validate_submission(payload)
            self._write_json(200 if not errors else 422, {"received": payload, "ok": not errors, "errors": errors})
            return

        if self.path == "/api/v1/forum/topics":
            payload = self._read_json()
            errors = _validate_topic(payload)
            self._write_json(200 if not errors else 422, {"received": payload, "ok": not errors, "errors": errors})
            return

        if self.path == "/api/v1/forum/comments":
            payload = self._read_json()
            errors = _validate_comment(payload)
            self._write_json(200 if not errors else 422, {"received": payload, "ok": not errors, "errors": errors})
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
                            "name": "NFL 2026 Week 1",
                            "lock_at": "2099-09-10T16:30:00Z",
                            "matches": [
                                {
                                    "match_id": "match_001",
                                    "home_team": "Lakers",
                                    "away_team": "Nuggets",
                                    "spread_home_team": -3.5,
                                    "total_line": 228.5,
                                },
                                {
                                    "match_id": "match_002",
                                    "home_team": "Celtics",
                                    "away_team": "Heat",
                                    "spread_home_team": 2.0,
                                    "total_line": 219.0,
                                },
                            ],
                        }
                    ]
                },
            )
            return

        self._write_json(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), MockApiHandler)
    print("Mock HaynesWorld API listening on http://127.0.0.1:8765")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
