from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .config import RivalSettings
from .contracts import ActiveSlate, ContestSubmission, ForumCommentDraft, ForumTopicDraft, SlateMatch
from .version import APP_VERSION


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or value.strip() == "":
        return None
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _coerce_float(raw_value: Any, default: float = 0.0) -> float:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def _coerce_str(raw_value: Any, default: str = "") -> str:
    if raw_value is None:
        return default
    text = str(raw_value).strip()
    return text or default


@dataclass(slots=True)
class HaynesWorldClient:
    settings: RivalSettings
    session_token: str | None = None

    def endpoint(self, path: str) -> str:
        return urljoin(self.settings.api_base_url.rstrip("/") + "/", path.lstrip("/"))

    @property
    def bot_login_endpoint(self) -> str:
        return self.endpoint("/api/v1/auth/bot-login")

    @property
    def active_slates_endpoint(self) -> str:
        return self.endpoint("/api/v1/contest/active-slates")

    @property
    def submissions_endpoint(self) -> str:
        return self.endpoint("/api/v1/contest/submissions")

    @property
    def forum_topics_endpoint(self) -> str:
        return self.endpoint("/api/v1/forum/topics")

    @property
    def forum_comments_endpoint(self) -> str:
        return self.endpoint("/api/v1/forum/comments")

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        require_auth: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.settings.api_key:
            headers["X-API-Key"] = self.settings.api_key
        if require_auth and self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"

        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        request = Request(url=url, method=method.upper(), headers=headers, data=data)
        try:
            with urlopen(request, timeout=self.settings.request_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8").strip()
                if not raw_body:
                    return {}
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict):
                    return parsed
                return {"data": parsed}
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method.upper()} {url} failed with HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"{method.upper()} {url} failed: {exc.reason}") from exc

    def _extract_token(self, payload: dict[str, Any]) -> str:
        for key in ("access_token", "token", "jwt", "session_token"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("access_token", "token", "jwt", "session_token"):
                candidate = data.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

        raise RuntimeError("Bot login succeeded but no access token was returned.")

    def _parse_slate_match(self, raw_match: dict[str, Any], fallback_lock_at: datetime) -> SlateMatch:
        return SlateMatch(
            match_id=_coerce_str(raw_match.get("match_id"), "unknown-match"),
            home_team=_coerce_str(raw_match.get("home_team"), "Unknown Home"),
            away_team=_coerce_str(raw_match.get("away_team"), "Unknown Away"),
            spread_home_team=_coerce_float(raw_match.get("spread_home_team")),
            total_line=_coerce_float(raw_match.get("total_line")),
            lock_at=_parse_datetime(raw_match.get("lock_at")) or fallback_lock_at,
        )

    def _parse_active_slate(self, raw_slate: dict[str, Any]) -> ActiveSlate:
        lock_at = _parse_datetime(raw_slate.get("lock_at"))
        if lock_at is None:
            raise RuntimeError("Active slate is missing required lock_at field.")

        raw_matches = raw_slate.get("matches")
        if not isinstance(raw_matches, list):
            raw_matches = []

        matches = tuple(
            self._parse_slate_match(raw_match=raw_match, fallback_lock_at=lock_at)
            for raw_match in raw_matches
            if isinstance(raw_match, dict)
        )

        return ActiveSlate(
            slate_id=_coerce_str(raw_slate.get("slate_id"), "unknown-slate"),
            name=_coerce_str(raw_slate.get("name"), "Unnamed Slate"),
            lock_at=lock_at,
            matches=matches,
        )

    def login(self) -> str:
        if self.session_token:
            return self.session_token

        if not self.settings.api_key:
            raise RuntimeError("RIVAL_API_KEY is required for bot login.")

        payload = {
            "api_key": self.settings.api_key,
            "client_name": self.settings.bot_username,
            "client_version": APP_VERSION,
        }
        response = self._request_json("POST", self.bot_login_endpoint, payload=payload, require_auth=False)
        self.session_token = self._extract_token(response)
        return self.session_token

    def fetch_active_slates(self) -> tuple[ActiveSlate, ...]:
        self.login()
        response = self._request_json("GET", self.active_slates_endpoint)

        raw_slates = response.get("slates")
        if not isinstance(raw_slates, list):
            data = response.get("data")
            if isinstance(data, list):
                raw_slates = data
            elif isinstance(data, dict) and isinstance(data.get("slates"), list):
                raw_slates = data["slates"]
            else:
                raw_slates = []

        return tuple(self._parse_active_slate(raw_slate) for raw_slate in raw_slates if isinstance(raw_slate, dict))

    def submit_predictions(self, submission: ContestSubmission) -> None:
        self.login()
        self._request_json("POST", self.submissions_endpoint, payload=submission.to_payload())

    def post_topic(self, draft: ForumTopicDraft) -> None:
        self.login()
        self._request_json("POST", self.forum_topics_endpoint, payload=draft.to_payload())

    def post_comment(self, draft: ForumCommentDraft) -> None:
        self.login()
        self._request_json("POST", self.forum_comments_endpoint, payload=draft.to_payload())