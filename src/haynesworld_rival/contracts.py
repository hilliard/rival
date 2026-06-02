from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

PredictionType = Literal["HOME_SPREAD", "AWAY_SPREAD", "OVER", "UNDER"]


@dataclass(frozen=True, slots=True)
class SlateMatch:
    match_id: str
    home_team: str
    away_team: str
    spread_home_team: float
    total_line: float
    lock_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ActiveSlate:
    slate_id: str
    name: str
    lock_at: datetime
    matches: tuple[SlateMatch, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SubmissionPick:
    match_id: str
    selected_pick: PredictionType
    confidence: float = 0.0
    rationale: str = ""

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContestSubmission:
    slate_id: str
    bot_user_id: str
    picks: tuple[SubmissionPick, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, object]:
        return {
            "slate_id": self.slate_id,
            "bot_user_id": self.bot_user_id,
            "picks": [pick.to_payload() for pick in self.picks],
        }


@dataclass(frozen=True, slots=True)
class ForumTopicDraft:
    title: str
    body: str
    topic_type: str = "benchmark-drop"

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ForumCommentDraft:
    body: str
    thread_id: str | None = None
    parent_comment_id: str | None = None

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RivalRunPlan:
    run_id: str = ""
    generated_at: datetime | None = None
    model_version: str = ""
    prompt_version: str = ""
    submissions: tuple[ContestSubmission, ...] = field(default_factory=tuple)
    topics: tuple[ForumTopicDraft, ...] = field(default_factory=tuple)
    comments: tuple[ForumCommentDraft, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)