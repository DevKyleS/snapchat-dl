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
        self.test_url = (
            "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
        )
        self.test_url404 = "https://google.com/error.html"

    def test_download_url(self):
        """Test snapchat_dl download_url."""
        download_url(self.test_url, ".test-data/test_dl_23.mp4", sleep_interval=0)

    def test_empty_download(self):
        """Test snapchat_dl download_url."""
        open(".test-data/test_dl_23.mp4", "w").close()
        download_url(self.test_url, ".test-data/test_dl_23.mp4", sleep_interval=0)

    def test_download_url_raise(self):
        """Test snapchat_dl download_url with invalid url."""
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
                download_m3u8_direct_ffmpeg("https://example.com/video.m3u8", output_path)
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
