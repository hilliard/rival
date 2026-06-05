from __future__ import annotations

import argparse
import logging
from pprint import pprint

from .client import create_client
from .config import RivalSettings
from .db import RivalDatabase
from .webapp import run as run_api_server
from .worker import RivalWorker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="haynesworld-rival")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set runtime log verbosity",
    )
    parser.add_argument(
        "--runtime-mode",
        choices=["mock", "go_live", "local"],
        help="Override the configured runtime mode for this command",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("show-config", help="Print the resolved runtime configuration")
    subcommands.add_parser("show-endpoints", help="Print the API endpoints the rival will call")
    run_once = subcommands.add_parser("run-once", help="Execute one worker pass")
    run_once.add_argument(
        "--dry-run",
        action="store_true",
        help="Build plan without publishing submissions or forum content",
    )

    poll = subcommands.add_parser("poll-loop", help="Run the recurring worker loop")
    poll.add_argument(
        "--dry-run",
        action="store_true",
        help="Build plans but do not publish submissions or forum content",
    )
    subcommands.add_parser("init-db", help="Initialize PostgreSQL schema and seed demo data")
    subcommands.add_parser("run-api", help="Run Rival FastAPI server with admin UI")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = RivalSettings.from_env()
    if args.runtime_mode:
        settings = RivalSettings(
            base_url=settings.base_url,
            api_base_url=settings.api_base_url,
            bot_username=settings.bot_username,
            bot_user_id=settings.bot_user_id,
            api_key=settings.api_key,
            ollama_base_url=settings.ollama_base_url,
            ollama_model=settings.ollama_model,
            poll_interval_seconds=settings.poll_interval_seconds,
            request_timeout_seconds=settings.request_timeout_seconds,
            runtime_mode=args.runtime_mode,
            database_url=settings.database_url,
            admin_token=settings.admin_token,
            api_bind_host=settings.api_bind_host,
            api_bind_port=settings.api_bind_port,
        )
    client = create_client(settings=settings)

    if args.command == "show-config":
        pprint(
            {
                "base_url": settings.base_url,
                "api_base_url": settings.api_base_url,
                "bot_username": settings.bot_username,
                "bot_user_id": settings.bot_user_id,
                "ollama_base_url": settings.ollama_base_url,
                "ollama_model": settings.ollama_model,
                "poll_interval_seconds": settings.poll_interval_seconds,
                "request_timeout_seconds": settings.request_timeout_seconds,
                "runtime_mode": settings.runtime_mode,
                "database_url": settings.database_url,
                "admin_token": settings.admin_token,
                "api_bind_host": settings.api_bind_host,
                "api_bind_port": settings.api_bind_port,
            }
        )
        return 0

    if args.command == "show-endpoints":
        pprint(
            {
                "bot_login": client.bot_login_endpoint,
                "active_slates": client.active_slates_endpoint,
                "submissions": client.submissions_endpoint,
                "forum_topics": client.forum_topics_endpoint,
                "forum_comments": client.forum_comments_endpoint,
            }
        )
        return 0

    worker = RivalWorker(settings=settings, client=client)

    if args.command == "run-once":
        plan = worker.run_once(publish=not args.dry_run)
        pprint(plan)
        return 0

    if args.command == "init-db":
        db = RivalDatabase(settings)
        db.init_schema()
        db.seed_demo_data()
        print("Database initialized and seeded.")
        return 0

    if args.command == "run-api":
        return run_api_server()

    worker.run_poll_loop(publish=not args.dry_run)
    return 0