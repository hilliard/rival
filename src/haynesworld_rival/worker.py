from __future__ import annotations

import logging
from datetime import UTC, datetime
from dataclasses import dataclass, field
from time import sleep
from uuid import uuid4

from .client import HaynesWorldClient
from .config import RivalSettings
from .contracts import ActiveSlate, RivalRunPlan
from .data_engine import RivalDataEngine
from .persona import RivalPersonaEngine


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RivalWorker:
    settings: RivalSettings
    client: HaynesWorldClient
    data_engine: RivalDataEngine = field(default_factory=RivalDataEngine)
    persona_engine: RivalPersonaEngine = field(default_factory=RivalPersonaEngine)

    def _is_slate_open(self, slate: ActiveSlate, as_of: datetime) -> bool:
        return slate.lock_at > as_of

    def build_plan(self, active_slates: tuple[ActiveSlate, ...], as_of: datetime | None = None) -> RivalRunPlan:
        now = as_of or datetime.now(UTC)
        submissions = []
        topics = []
        comments = []
        notes = []

        bot_user_id = self.settings.bot_user_id or self.settings.bot_username

        for slate in active_slates:
            if not self._is_slate_open(slate, as_of=now):
                notes.append(f"Skipped {slate.name}: slate is already locked.")
                continue

            submission = self.data_engine.draft_submission(slate, bot_user_id, as_of=now)
            if not submission.picks:
                notes.append(f"Skipped {slate.name}: no unlocked matches remain.")
                continue

            submissions.append(submission)
            topics.append(self.persona_engine.build_topic(submission))
            comments.append(self.persona_engine.build_comment(submission))
            notes.append(f"Drafted {len(submission.picks)} picks for {slate.name}.")

        return RivalRunPlan(
            run_id=str(uuid4()),
            generated_at=now,
            model_version=self.settings.ollama_model,
            prompt_version="rival-persona-v1",
            submissions=tuple(submissions),
            topics=tuple(topics),
            comments=tuple(comments),
            notes=tuple(notes),
        )

    def publish_plan(self, plan: RivalRunPlan) -> RivalRunPlan:
        publish_notes = list(plan.notes)

        for submission in plan.submissions:
            self.client.submit_predictions(submission)
            publish_notes.append(
                f"Submitted {len(submission.picks)} picks for slate {submission.slate_id}."
            )

        for draft in plan.topics:
            self.client.post_topic(draft)
            publish_notes.append(f"Posted benchmark topic: {draft.title}")

        for draft in plan.comments:
            self.client.post_comment(draft)
            publish_notes.append("Posted benchmark comment.")

        return RivalRunPlan(
            run_id=plan.run_id,
            generated_at=plan.generated_at,
            model_version=plan.model_version,
            prompt_version=plan.prompt_version,
            submissions=plan.submissions,
            topics=plan.topics,
            comments=plan.comments,
            notes=tuple(publish_notes),
        )

    def run_once(self, publish: bool = True) -> RivalRunPlan:
        active_slates = self.client.fetch_active_slates()
        plan = self.build_plan(active_slates)
        if not publish:
            return plan
        return self.publish_plan(plan)

    def run_poll_loop(self, publish: bool = True) -> None:
        LOGGER.info("Starting Rival worker poll loop at %ss intervals.", self.settings.poll_interval_seconds)
        while True:
            try:
                plan = self.run_once(publish=publish)
                LOGGER.info(
                    "Completed run %s with %d submissions and %d notes.",
                    plan.run_id,
                    len(plan.submissions),
                    len(plan.notes),
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Rival run failed: %s", exc)

            sleep(self.settings.poll_interval_seconds)