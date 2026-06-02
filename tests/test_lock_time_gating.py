from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from haynesworld_rival.config import RivalSettings
from haynesworld_rival.contracts import ActiveSlate, SlateMatch
from haynesworld_rival.data_engine import RivalDataEngine
from haynesworld_rival.worker import RivalWorker


class _DummyClient:
    def fetch_active_slates(self) -> tuple[ActiveSlate, ...]:
        return ()

    def submit_predictions(self, submission) -> None:
        return None

    def post_topic(self, draft) -> None:
        return None

    def post_comment(self, draft) -> None:
        return None


class LockTimeGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(UTC)
        self.engine = RivalDataEngine()

    def test_data_engine_skips_locked_matches(self) -> None:
        unlocked = SlateMatch(
            match_id="match_open",
            home_team="Lions",
            away_team="Bears",
            spread_home_team=-3.5,
            total_line=44.5,
            lock_at=self.now + timedelta(minutes=30),
        )
        locked = SlateMatch(
            match_id="match_locked",
            home_team="Jets",
            away_team="Bills",
            spread_home_team=4.0,
            total_line=47.0,
            lock_at=self.now - timedelta(minutes=1),
        )
        slate = ActiveSlate(
            slate_id="slate_1",
            name="Week 1",
            lock_at=self.now + timedelta(minutes=30),
            matches=(unlocked, locked),
        )

        submission = self.engine.draft_submission(slate, bot_user_id="bot_therival", as_of=self.now)
        self.assertEqual(len(submission.picks), 1)
        self.assertEqual(submission.picks[0].match_id, "match_open")

    def test_worker_skips_locked_slate(self) -> None:
        locked_slate = ActiveSlate(
            slate_id="slate_locked",
            name="Week Locked",
            lock_at=self.now - timedelta(seconds=1),
            matches=(),
        )
        settings = RivalSettings(bot_username="therival", bot_user_id="bot_therival")
        worker = RivalWorker(settings=settings, client=_DummyClient())

        plan = worker.build_plan((locked_slate,), as_of=self.now)
        self.assertEqual(len(plan.submissions), 0)
        self.assertTrue(any("already locked" in note for note in plan.notes))


if __name__ == "__main__":
    unittest.main()
