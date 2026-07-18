import tempfile
import unittest
from pathlib import Path

from app.models import ScanRequest
from app.routers.files import SUBTITLE_EXTENSIONS, scan_video_files


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


if __name__ == "__main__":
    unittest.main()
