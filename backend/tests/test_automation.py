import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import automation
from app.automation import AutomationConfig, WatchRule
from app.routers import organizer


class AutomationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "downloads"
        self.target = self.root / "media"
        self.source.mkdir()
        self.target.mkdir()
        self.config_file = self.root / "config" / "automation.json"
        self.state_file = self.root / "config" / "automation-state.json"
        self.history_file = self.root / "config" / "task-history.json"
        self.patches = [
            patch.object(automation, "CONFIG_FILE", self.config_file),
            patch.object(automation, "STATE_FILE", self.state_file),
            patch.object(automation, "_is_stable", return_value=True),
            patch.object(organizer, "HISTORY_FILE", self.history_file),
        ]
        for item in self.patches:
            item.start()
        automation._seen.clear()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def _save_tv_rule(self) -> None:
        automation.save_config(AutomationConfig(
            enabled=True,
            scan_interval_seconds=15,
            settle_seconds=10,
            rules=[WatchRule(
                name="测试剧集",
                source_path=str(self.source),
                target_root=str(self.target),
                media_type="tv",
                title="进击的巨人",
                year="2013",
                season=1,
                include_subtitles=True,
            )],
        ))

    def test_tv_episode_and_subtitle_are_hardlinked(self) -> None:
        video = self.source / "Attack.on.Titan.S02E03.mkv"
        subtitle = self.source / "Attack.on.Titan.S02E03.zh-CN.srt"
        video.write_bytes(b"video")
        subtitle.write_text("subtitle", encoding="utf-8")
        self._save_tv_rule()

        result = automation.scan_once()

        video_target = self.target / "进击的巨人 (2013)" / "Season 02" / "进击的巨人 S02E03.mkv"
        subtitle_target = self.target / "进击的巨人 (2013)" / "Season 02" / "进击的巨人 S02E03.zh-CN.srt"
        self.assertEqual(result["completed_count"], 2)
        self.assertTrue(video_target.exists())
        self.assertTrue(subtitle_target.exists())
        self.assertTrue(os.path.samefile(video, video_target))
        self.assertTrue(os.path.samefile(subtitle, subtitle_target))

        second = automation.scan_once()
        self.assertEqual(second["completed_count"], 0)

    def test_unrecognized_tv_episode_waits_for_user(self) -> None:
        (self.source / "unknown.mkv").write_bytes(b"video")
        self._save_tv_rule()

        result = automation.scan_once()
        state = json.loads(self.state_file.read_text(encoding="utf-8"))

        self.assertEqual(result["completed_count"], 0)
        self.assertEqual(result["pending_count"], 1)
        self.assertEqual(state["events"][0]["level"], "warning")
        self.assertIn("未识别到集数", state["events"][0]["message"])

    def test_target_inside_source_is_rejected(self) -> None:
        nested_target = self.source / "media"
        nested_target.mkdir()
        with self.assertRaises(ValueError):
            WatchRule(
                source_path=str(self.source),
                target_root=str(nested_target),
                media_type="movie",
                title="电影",
            )


if __name__ == "__main__":
    unittest.main()
