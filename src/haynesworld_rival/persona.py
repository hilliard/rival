from __future__ import annotations

from dataclasses import dataclass

from .contracts import ContestSubmission, ForumCommentDraft, ForumTopicDraft


@dataclass(frozen=True, slots=True)
class PersonaPrompt:
    system_prompt: str
    user_prompt: str


class RivalPersonaEngine:
    def build_topic(self, submission: ContestSubmission) -> ForumTopicDraft:
        body_lines = [
            "Benchmark drop: the market is about to learn the difference between instinct and math.",
            "",
            f"Slate ID: {submission.slate_id}",
            f"Bot: {submission.bot_user_id}",
            "",
            "The Rival is live. Keep up if you can.",
        ]
        return ForumTopicDraft(
            title=f"@TheRival Benchmark Drop for Slate {submission.slate_id}",
            body="\n".join(body_lines),
        )

    def build_comment(self, submission: ContestSubmission, target_thread_id: str | None = None) -> ForumCommentDraft:
        pick_count = len(submission.picks)
        body = (
            f"{pick_count} picks submitted. If you want to beat the bot, bring a model, not a mood."
        )
        return ForumCommentDraft(body=body, thread_id=target_thread_id)

    def build_prompt(self, submission: ContestSubmission) -> PersonaPrompt:
        system_prompt = (
            "You are @TheRival, a clinical, smug, competitive sports analyst. "
            "Stay fair, avoid slurs, avoid threats, and never cross into harassment. "
            "Sound sharp, data-driven, and a little provoking."
        )
        user_prompt = (
            f"Write a short benchmark post for slate {submission.slate_id}. "
            "Announce the picks with cocky but professional trash talk."
        )
        return PersonaPrompt(system_prompt=system_prompt, user_prompt=user_prompt)