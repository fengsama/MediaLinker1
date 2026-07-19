import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.models import ScanRequest
from app.routers.auth import LoginRequest, login
from app.routers.files import browse_server_directory, scan_video_files
from app.server_config import allowed_roots, path_is_allowed


class ServerModeTests(unittest.TestCase):
    def server_environment(self, root: Path, password: str = "test-password"):
        return patch.dict(
            os.environ,
            {
                "MEDIALINKER_SERVER_MODE": "1",
                "MEDIALINKER_ACCESS_TOKEN": password,
                "MEDIALINKER_ALLOWED_ROOTS": json.dumps([str(root)]),
            },
            clear=False,
        )

    def test_allowed_roots_limit_filesystem_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "nas"
            root.mkdir()
            inside = root / "downloads"
            inside.mkdir()
            outside = Path(directory) / "private"
            outside.mkdir()

            with self.server_environment(root):
                self.assertEqual(allowed_roots(), [root.resolve()])
                self.assertTrue(path_is_allowed(inside))
                self.assertFalse(path_is_allowed(outside))

    def test_browser_lists_directories_and_cannot_walk_above_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "nas"
            root.mkdir()
            (root / "Season 10").mkdir()
            (root / "Season 2").mkdir()
            (root / "video.mkv").write_bytes(b"video")

            with self.server_environment(root):
                virtual_root = browse_server_directory("")
                self.assertEqual(virtual_root["entries"][0]["path"], str(root.resolve()))

                listing = browse_server_directory(str(root))
                self.assertEqual(
                    [entry["name"] for entry in listing["entries"]],
                    ["Season 2", "Season 10"],
                )
                self.assertEqual(listing["parent_path"], "")

                with self.assertRaises(HTTPException) as error:
                    browse_server_directory(str(root.parent))
                self.assertEqual(error.exception.status_code, 403)

    def test_scan_rejects_directory_outside_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "nas"
            root.mkdir()
            outside = Path(directory) / "outside"
            outside.mkdir()
            (outside / "Movie.mkv").write_bytes(b"video")

            with self.server_environment(root):
                with self.assertRaises(HTTPException) as error:
                    scan_video_files(ScanRequest(path=str(outside), recursive=False))
                self.assertEqual(error.exception.status_code, 403)

    def test_login_accepts_only_configured_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.server_environment(Path(directory), "correct-password"):
                success = asyncio.run(login(LoginRequest(password="correct-password")))
                self.assertTrue(success["success"])

                with self.assertRaises(HTTPException) as error:
                    asyncio.run(login(LoginRequest(password="wrong-password")))
                self.assertEqual(error.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
