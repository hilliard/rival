from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .contracts import ActiveSlate, ContestSubmission, PredictionType, SlateMatch, SubmissionPick


@dataclass(frozen=True, slots=True)
class MatchAssessment:
    match_id: str
    selected_pick: PredictionType
    confidence: float
    rationale: str


class RivalDataEngine:
    def assess_match(self, match: SlateMatch) -> MatchAssessment:
        spread_strength = abs(match.spread_home_team)
        total_strength = abs(match.total_line - 46.5)

        if spread_strength >= total_strength:
            if match.spread_home_team <= 0:
                selected_pick: PredictionType = "HOME_SPREAD"
                rationale = (
                    f"Home team is favored by {abs(match.spread_home_team):.1f}; "
                    "baseline leans with the chalk."
                )
            else:
                selected_pick = "AWAY_SPREAD"
                rationale = (
                    f"Home team is catching {match.spread_home_team:.1f}; "
                    "baseline leans with the points."
                )
            confidence = min(0.85, 0.55 + spread_strength / 20)
        else:
            if match.total_line >= 47.5:
                selected_pick = "UNDER"
                rationale = "Total is inflated enough that the under is the cleaner baseline."
            else:
                selected_pick = "OVER"
                rationale = "Total is modest enough that the over is the cleaner baseline."
            confidence = min(0.80, 0.54 + total_strength / 18)

        return MatchAssessment(
            match_id=match.match_id,
            selected_pick=selected_pick,
            confidence=round(confidence, 3),
            rationale=rationale,
        )

    def draft_submission(
        self,
        slate: ActiveSlate,
        bot_user_id: str,
        as_of: datetime | None = None,
    ) -> ContestSubmission:
        now = as_of or datetime.now(UTC)
        picks = tuple(
            SubmissionPick(
                match_id=match.match_id,
                selected_pick=assessment.selected_pick,
                confidence=assessment.confidence,
                rationale=assessment.rationale,
            )
            for match in slate.matches
            if (match.lock_at is None or match.lock_at > now)
            for assessment in [self.assess_match(match)]
        )

        return ContestSubmission(slate_id=slate.slate_id, bot_user_id=bot_user_id, picks=picks)