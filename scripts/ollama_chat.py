from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/chat"


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        url=url,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {}


def _stream_chat(url: str, payload: dict[str, Any], timeout: int) -> str:
    request = Request(
        url=url,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    response_text = ""
    with urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            chunk = json.loads(line)
            message = chunk.get("message") if isinstance(chunk, dict) else None
            if isinstance(message, dict):
                text_chunk = str(message.get("content", ""))
                if text_chunk:
                    print(text_chunk, end="", flush=True)
                    response_text += text_chunk
    return response_text


def _chat_loop(model: str, base_url: str, timeout: int, stream: bool) -> int:
    messages: list[dict[str, str]] = []
    url = _endpoint(base_url)
    print(f"Rival Ollama Chat | model={model} | endpoint={url}")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        user_input = input("\nYou> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            return 0

        messages.append({"role": "user", "content": user_input})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        print("Rival> ", end="", flush=True)
        try:
            if stream:
                assistant_text = _stream_chat(url=url, payload=payload, timeout=timeout)
                print()
            else:
                response = _post_json(url=url, payload=payload, timeout=timeout)
                message = response.get("message")
                assistant_text = ""
                if isinstance(message, dict):
                    assistant_text = str(message.get("content", ""))
                print(assistant_text)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"\n[HTTP {exc.code}] {detail}")
            continue
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            print(f"\n[Error] {exc}")
            continue

        if assistant_text:
            messages.append({"role": "assistant", "content": assistant_text})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ollama-chat")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen2.5:1b"))
    parser.add_argument("--base-url", default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("RIVAL_REQUEST_TIMEOUT_SECONDS", "20")))
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming response mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _chat_loop(
        model=args.model,
        base_url=args.base_url,
        timeout=args.timeout,
        stream=not args.no_stream,
    )


if __name__ == "__main__":
    raise SystemExit(main())
