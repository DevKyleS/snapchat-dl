"""Tests for `snapchat_dl` package."""

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from requests.exceptions import HTTPError

from snapchat_dl.downloader import (
    _combine_video_audio_segments,
    download_m3u8_direct_ffmpeg,
    download_url,
)


def teardown_module(module):
    shutil.rmtree(".test-data")


class Test_downloader(unittest.TestCase):
    """Tests for `snapchat_dl.downloader.download_url` package."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_url = "https://example.invalid/video.mp4"
        self.test_url404 = "https://example.invalid/not-found.mp4"

    def _mock_response(self, status_code=200, content=b"video"):
        response = mock.Mock()
        response.status_code = status_code
        response.headers = {"content-length": str(len(content))}
        response.iter_content.return_value = [content]
        return response

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_url(self, get):
        """Test snapchat_dl download_url."""
        get.return_value = self._mock_response()

        download_url(self.test_url, ".test-data/test_dl_23.mp4", sleep_interval=0)

        with open(".test-data/test_dl_23.mp4", "rb") as downloaded_file:
            self.assertEqual(downloaded_file.read(), b"video")

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_empty_download(self, get):
        """Test snapchat_dl download_url."""
        get.return_value = self._mock_response()
        with open(".test-data/test_dl_23.mp4", "wb"):
            pass

        download_url(self.test_url, ".test-data/test_dl_23.mp4", sleep_interval=0)

        with open(".test-data/test_dl_23.mp4", "rb") as downloaded_file:
            self.assertEqual(downloaded_file.read(), b"video")

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_url_raise(self, get):
        """Test snapchat_dl download_url with invalid url."""
        response = self._mock_response(status_code=404, content=b"")
        response.raise_for_status.side_effect = HTTPError("404 Not Found")
        get.return_value = response

        with self.assertRaises(HTTPError):
            download_url(
                self.test_url404, ".test-data/test_dl_23.mp4", sleep_interval=0
            )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_download_m3u8_direct_ffmpeg_runs(self, run):
        def run_ffmpeg(command, **kwargs):
            if command[1] != "-version":
                with open(command[-1], "wb") as output_file:
                    output_file.write(b"video")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        run.side_effect = run_ffmpeg
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "video.mp4")

            self.assertTrue(
                download_m3u8_direct_ffmpeg(
                    "https://example.com/video.m3u8", output_path
                )
            )

            self.assertEqual(os.path.getsize(output_path), 5)
        self.assertEqual(run.call_count, 2)

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    def test_audio_merge_failure_keeps_video(self, combine_video, run):
        def create_temp_media(files, output_path):
            content = b"audio" if "audio_temp" in output_path else b"video"
            with open(output_path, "wb") as output_file:
                output_file.write(content)
            return True

        combine_video.side_effect = create_temp_media
        run.return_value = subprocess.CompletedProcess(
            ["ffmpeg"], 1, stdout="", stderr="merge failed"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "story.mp4")

            self.assertTrue(
                _combine_video_audio_segments(["video.ts"], ["audio.ts"], output_path)
            )

            with open(output_path, "rb") as output_file:
                self.assertEqual(output_file.read(), b"video")
