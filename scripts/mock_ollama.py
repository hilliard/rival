from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SLATE_ID_PATTERN = re.compile(r"Slate ID:\s*(?P<slate_id>.+?)\s*(?:\n|$)", re.IGNORECASE)
PICK_COUNT_PATTERN = re.compile(r"Pick Count:\s*(?P<pick_count>\d+)", re.IGNORECASE)


def _build_response(prompt: str, model: str) -> dict[str, str]:
    slate_match = SLATE_ID_PATTERN.search(prompt)
    pick_count_match = PICK_COUNT_PATTERN.search(prompt)

    slate_id = slate_match.group("slate_id").strip() if slate_match else "unknown-slate"
    pick_count = pick_count_match.group("pick_count") if pick_count_match else "0"

    return {
        "response": json.dumps(
            {
                "title": f"@TheRival benchmark drop for {slate_id}",
                "body": (
                    f"The numbers are clean, the plan is set, and {pick_count} picks are on the board. "
                    f"Model: {model}."
                ),
                "comment": (
                    f"{pick_count} picks submitted for {slate_id}. If you want to argue, bring better numbers."
                ),
            }
        )
    }


class MockOllamaHandler(BaseHTTPRequestHandler):
    model_name: str = "llama3.1"

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}

    def _write_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/generate":
            self._write_json(404, {"error": "not found"})
            return

        payload = self._read_json()
        prompt = str(payload.get("prompt", ""))
        model = str(payload.get("model", self.model_name))
        self._write_json(200, _build_response(prompt, model))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mock-ollama")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", default=11434, type=int, help="Port to listen on")
    parser.add_argument("--model", default="llama3.1", help="Default model name to echo back")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = type(
        "ConfiguredMockOllamaHandler",
        (MockOllamaHandler,),
        {"model_name": args.model},
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Mock Ollama listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())