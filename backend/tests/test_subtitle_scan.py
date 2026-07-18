import tempfile
import unittest
from pathlib import Path

from app.models import ScanRequest
from app.routers.files import SUBTITLE_EXTENSIONS, _detect_episode, scan_video_files


class SubtitleScanTests(unittest.TestCase):
    def test_common_subtitle_formats_and_name_suffixes_are_matched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Movie.mkv").write_bytes(b"video")
            expected_names = {
                "Movie.srt",
                "Movie.zh-CN.ass",
                "Movie_chs.ssa",
                "Movie-forced.vtt",
                "Movie [CHT].sup",
                "Movie.idx",
                "Movie.sub",
                "Movie(commentary).ttml",
            }
            for name in expected_names:
                (root / name).write_bytes(b"subtitle")

            (root / "Movie2.ass").write_bytes(b"not a match")
            (root / "Movie.nfo").write_bytes(b"not a subtitle")

            response = scan_video_files(ScanRequest(path=str(root), recursive=False))

            self.assertEqual(response.count, 1)
            self.assertEqual({item.name for item in response.files[0].subtitles}, expected_names)

    def test_supported_extensions_cover_text_and_graphic_subtitles(self) -> None:
        self.assertTrue(
            {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".sup", ".smi", ".ttml"}
            <= SUBTITLE_EXTENSIONS
        )

    def test_episode_detection_supports_common_names(self) -> None:
        self.assertEqual(_detect_episode("Show.S02E03.1080p.mkv"), (2, 3))
        self.assertEqual(_detect_episode("Show EP12.mp4"), (None, 12))
        self.assertEqual(_detect_episode("动画 第5集.mkv"), (None, 5))
        self.assertEqual(_detect_episode("Show Season 4 Special.mkv"), (4, None))

    def test_scan_uses_natural_filename_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("Show E10.mkv", "Show E2.mkv", "Show E1.mkv"):
                (root / name).write_bytes(b"video")

            response = scan_video_files(ScanRequest(path=str(root), recursive=False))

            self.assertEqual([item.name for item in response.files], ["Show E1.mkv", "Show E2.mkv", "Show E10.mkv"])
            self.assertEqual([item.detected_episode for item in response.files], [1, 2, 10])


if __name__ == "__main__":
    unittest.main()
