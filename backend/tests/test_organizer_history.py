import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.routers import organizer


class OrganizerHistoryTests(unittest.TestCase):
    def _request(self, source: Path, mode: str = "hardlink") -> organizer.CreateLinksRequest:
        return organizer.CreateLinksRequest(
            target_root=str(self.target_root),
            items=[
                organizer.LinkItem(
                    source_path=str(source),
                    target_parts=["Show", "Season 01"],
                    target_name="Show S01E01.mkv",
                )
            ],
            mode=mode,
            title="Show",
            media_type="tv",
        )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source_root = self.root / "source"
        self.target_root = self.root / "target"
        self.source_root.mkdir()
        self.target_root.mkdir()
        self.history_file = self.root / "config" / "task-history.json"
        self.history_patch = patch.object(organizer, "HISTORY_FILE", self.history_file)
        self.history_patch.start()

    def tearDown(self) -> None:
        self.history_patch.stop()
        self.temporary.cleanup()

    def test_hardlink_task_is_recorded_and_can_be_undone(self) -> None:
        source = self.source_root / "episode.mkv"
        source.write_bytes(b"video")

        result = organizer.execute_organization(self._request(source))
        target = self.target_root / "Show" / "Season 01" / "Show S01E01.mkv"

        self.assertTrue(target.exists())
        self.assertTrue(os.path.samefile(source, target))
        history = organizer.list_history(50)
        self.assertEqual(history["tasks"][0]["status"], "completed")

        undo = organizer.undo_task(str(result["task_id"]))

        self.assertEqual(undo["status"], "undone")
        self.assertTrue(source.exists())
        self.assertFalse(target.exists())
        self.assertEqual(organizer.list_history(50)["tasks"][0]["status"], "undone")

    def test_move_task_can_be_rolled_back_to_original_path(self) -> None:
        source = self.source_root / "episode.mkv"
        source.write_bytes(b"video")

        result = organizer.execute_organization(self._request(source, mode="move"))
        target = self.target_root / "Show" / "Season 01" / "Show S01E01.mkv"
        self.assertFalse(source.exists())
        self.assertTrue(target.exists())

        organizer.undo_task(str(result["task_id"]))

        self.assertTrue(source.exists())
        self.assertFalse(target.exists())

    def test_execution_failure_rolls_back_and_records_failure(self) -> None:
        first = self.source_root / "one.mkv"
        second = self.source_root / "two.mkv"
        first.write_bytes(b"one")
        second.write_bytes(b"two")
        request = self._request(first)
        request.items.append(
            organizer.LinkItem(
                source_path=str(second),
                target_parts=["Show", "Season 01"],
                target_name="Show S01E02.mkv",
            )
        )
        real_link = os.link
        call_count = 0

        def fail_second_link(source: Path, target: Path) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("simulated failure")
            real_link(source, target)

        with patch.object(organizer.os, "link", side_effect=fail_second_link):
            with self.assertRaises(HTTPException):
                organizer.execute_organization(request)

        self.assertFalse((self.target_root / "Show" / "Season 01" / "Show S01E01.mkv").exists())
        history = organizer.list_history(50)
        self.assertEqual(history["tasks"][0]["status"], "failed")
        self.assertIn("simulated failure", history["tasks"][0]["error"])


if __name__ == "__main__":
    unittest.main()
