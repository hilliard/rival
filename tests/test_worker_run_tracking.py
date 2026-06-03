from __future__ import annotations

import unittest

from haynesworld_rival.config import RivalSettings
from haynesworld_rival.worker import RivalWorker


class _FakeClient:
    def __init__(self, slates: tuple = (), exc: Exception | None = None) -> None:
        self._slates = slates
        self._exc = exc

    def fetch_active_slates(self):
        if self._exc is not None:
            raise self._exc
        return self._slates

    def submit_predictions(self, submission) -> None:
        return None

    def post_topic(self, draft) -> None:
        return None

    def post_comment(self, draft) -> None:
        return None


class _FakeDatabase:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record_run(self, plan, *, published: bool, status: str, error_message: str | None = None) -> None:
        self.records.append(
            {
                "run_id": plan.run_id,
                "published": published,
                "status": status,
                "error_message": error_message,
            }
        )


class WorkerRunTrackingTests(unittest.TestCase):
    def test_run_once_records_successful_run(self) -> None:
        db = _FakeDatabase()
        worker = RivalWorker(settings=RivalSettings(), client=_FakeClient(), db=db)

        plan = worker.run_once(publish=False)

        self.assertEqual(len(db.records), 1)
        self.assertEqual(db.records[0]["run_id"], plan.run_id)
        self.assertEqual(db.records[0]["status"], "succeeded")
        self.assertFalse(db.records[0]["published"])

    def test_run_once_records_failed_run(self) -> None:
        db = _FakeDatabase()
        worker = RivalWorker(
            settings=RivalSettings(),
            client=_FakeClient(exc=RuntimeError("boom")),
            db=db,
        )

        with self.assertRaisesRegex(RuntimeError, "boom"):
            worker.run_once(publish=True)

        self.assertEqual(len(db.records), 1)
        self.assertEqual(db.records[0]["status"], "failed")
        self.assertEqual(db.records[0]["error_message"], "boom")
        self.assertTrue(db.records[0]["published"])


if __name__ == "__main__":
    unittest.main()