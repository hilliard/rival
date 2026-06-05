from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import RivalSettings
from .contracts import ContestSubmission, ForumCommentDraft, ForumTopicDraft


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PersonaPrompt:
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True, slots=True)
class PersonaOutput:
    title: str
    body: str
    comment: str


def _fallback_topic(submission: ContestSubmission) -> ForumTopicDraft:
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


def _fallback_comment(submission: ContestSubmission, target_thread_id: str | None = None) -> ForumCommentDraft:
    pick_count = len(submission.picks)
    body = f"{pick_count} picks submitted. If you want to beat the bot, bring a model, not a mood."
    return ForumCommentDraft(body=body, thread_id=target_thread_id)


@dataclass(slots=True)
class RivalPersonaEngine:
    settings: RivalSettings = field(default_factory=RivalSettings.from_env)
    _output_cache: dict[ContestSubmission, PersonaOutput | None] = field(default_factory=dict, init=False)

    def build_topic(self, submission: ContestSubmission) -> ForumTopicDraft:
        generated = self._get_persona_output(submission)
        if generated is None:
            raise RuntimeError("Persona generation failed.")
        return ForumTopicDraft(title=generated.title, body=generated.body)

    def build_comment(self, submission: ContestSubmission, target_thread_id: str | None = None) -> ForumCommentDraft:
        generated = self._get_persona_output(submission)
        if generated is None:
            raise RuntimeError("Persona generation failed.")
        return ForumCommentDraft(body=generated.comment, thread_id=target_thread_id)

    def build_prompt(self, submission: ContestSubmission) -> PersonaPrompt:
        system_prompt = (
            "You are @TheRival, a clinical, smug, competitive sports analyst. "
            "Stay fair, avoid slurs, avoid threats, and never cross into harassment. "
            "Sound sharp, data-driven, and a little provoking."
        )
        picks_summary = "\n".join(
            f"- {pick.match_id}: {pick.selected_pick} ({pick.confidence:.2f}) because {pick.rationale or 'no rationale provided'}"
            for pick in submission.picks
        )
        user_prompt = (
            "Return valid JSON with exactly these string keys: title, body, comment. "
            "Write a short benchmark topic and one short follow-up comment for @TheRival. "
            "Be sharp and competitive, but not abusive. Use the data below and do not invent picks.\n\n"
            f"Slate ID: {submission.slate_id}\n"
            f"Bot User ID: {submission.bot_user_id}\n"
            f"Pick Count: {len(submission.picks)}\n"
            f"Picks:\n{picks_summary or '- No picks'}"
        )
        return PersonaPrompt(system_prompt=system_prompt, user_prompt=user_prompt)

    def _generate_persona_output(self, submission: ContestSubmission) -> PersonaOutput | None:
        prompt = self.build_prompt(submission)
        payload = {
            "model": self.settings.ollama_model,
            "prompt": f"System: {prompt.system_prompt}\n\nUser: {prompt.user_prompt}",
            "stream": False,
        }
        request = Request(
            url=f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.settings.request_timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            exc.close()
            LOGGER.debug("Ollama persona generation failed: %s", exc)
            return None
        except (URLError, TimeoutError, OSError) as exc:
            LOGGER.debug("Ollama persona generation failed: %s", exc)
            return None

        try:
            envelope = json.loads(raw)
            generated_text = str(envelope.get("response", "")).strip()
            if not generated_text:
                return None
            return self._parse_generated_output(generated_text)
        except (json.JSONDecodeError, ValueError) as exc:
            LOGGER.debug("Ollama persona response was invalid: %s", exc)
            return None

    def _get_persona_output(self, submission: ContestSubmission) -> PersonaOutput | None:
        if submission not in self._output_cache:
            self._output_cache[submission] = self._generate_persona_output(submission)
        return self._output_cache[submission]

    def _parse_generated_output(self, generated_text: str) -> PersonaOutput:
        start = generated_text.find("{")
        end = generated_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Missing JSON object in Ollama response.")

        payload = json.loads(generated_text[start : end + 1])
        title = str(payload.get("title", "")).strip()
        body = str(payload.get("body", "")).strip()
        comment = str(payload.get("comment", "")).strip()
        if not title or not body or not comment:
            raise ValueError("Incomplete Ollama persona payload.")
        return PersonaOutput(title=title, body=body, comment=comment)