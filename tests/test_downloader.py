"""Tests for `snapchat_dl` package."""

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from requests.exceptions import HTTPError, RequestException

from snapchat_dl.downloader import (
    _combine_video_only_segments,
    _combine_video_audio_segments,
    _download_byterange_segment,
    _process_byterange_m3u8,
    combine_segments_with_ffmpeg,
    download_m3u8_direct_ffmpeg,
    download_m3u8_segments,
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

    def _playlist_response(self, content):
        response = mock.Mock()
        response.text = content
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

    @mock.patch("snapchat_dl.downloader.download_url")
    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_m3u8_media_playlist_resolves_urls(self, get, download):
        get.return_value = self._playlist_response(
            '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\nsegment.ts\n'
            "https://cdn.example/second.ts\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            segments = download_m3u8_segments(
                "https://cdn.example/path/list.m3u8", temp_dir, 0
            )

        self.assertEqual(
            segments,
            [
                os.path.join(temp_dir, "segment_0000.ts"),
                os.path.join(temp_dir, "segment_0001.ts"),
            ],
        )
        self.assertEqual(
            [call.args[:2] for call in download.call_args_list],
            [
                (
                    "https://cdn.example/path/init.mp4",
                    os.path.join(temp_dir, "init.mp4"),
                ),
                (
                    "https://cdn.example/path/segment.ts",
                    os.path.join(temp_dir, "segment_0000.ts"),
                ),
                (
                    "https://cdn.example/second.ts",
                    os.path.join(temp_dir, "segment_0001.ts"),
                ),
            ],
        )

    @mock.patch("snapchat_dl.downloader.download_url")
    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_m3u8_master_selects_best_video_and_audio(self, get, download):
        get.side_effect = [
            self._playlist_response(
                '#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,URI="audio.m3u8"\n'
                "#EXT-X-STREAM-INF:BANDWIDTH=100\nlow.m3u8\n"
                "#EXT-X-STREAM-INF:BANDWIDTH=500\nhigh.m3u8\n"
            ),
            self._playlist_response("#EXTM3U\nvideo.ts\n"),
            self._playlist_response("#EXTM3U\naudio.ts\n"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            segments = download_m3u8_segments(
                "https://cdn.example/path/master.m3u8", temp_dir, 0
            )

        self.assertEqual(
            segments,
            {
                "video": [os.path.join(temp_dir, "segment_0000.ts")],
                "audio": [os.path.join(temp_dir, "audio", "segment_0000.ts")],
            },
        )
        self.assertEqual(
            [call.args[0] for call in get.call_args_list],
            [
                "https://cdn.example/path/master.m3u8",
                "https://cdn.example/path/high.m3u8",
                "https://cdn.example/path/audio.m3u8",
            ],
        )
        self.assertEqual(download.call_count, 2)

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_m3u8_request_error_returns_empty_list(self, get):
        get.side_effect = RequestException("unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(
                download_m3u8_segments("https://cdn.example/list.m3u8", temp_dir, 0),
                [],
            )

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_m3u8_master_without_video_returns_empty_list(self, get):
        get.return_value = self._playlist_response("#EXTM3U\n#EXT-X-STREAM-INF\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(
                download_m3u8_segments("https://cdn.example/master.m3u8", temp_dir, 0),
                [],
            )

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_byterange_segment_sends_range_header(self, get):
        response = mock.Mock(content=b"x" * 128)
        get.return_value = response
        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "nested", "segment.ts")
            _download_byterange_segment(
                "https://cdn.example/video.mp4", dest_path, (50, 100), 0
            )

            with open(dest_path, "rb") as segment:
                self.assertEqual(segment.read(), b"x" * 128)

        get.assert_called_once_with(
            "https://cdn.example/video.mp4",
            headers={"Range": "bytes=100-149"},
            timeout=10,
        )

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_byterange_segment_rejects_unavailable_content(self, get):
        response = mock.Mock(content=b"short")
        get.return_value = response

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "segment.ts")
            with self.assertRaises(RequestException):
                _download_byterange_segment(
                    "https://cdn.example/video.mp4", dest_path, None, 0
                )
            self.assertFalse(os.path.exists(dest_path))

    @mock.patch("snapchat_dl.downloader._download_byterange_segment")
    def test_process_byterange_playlist_downloads_init_and_media(self, download):
        with tempfile.TemporaryDirectory() as temp_dir:
            playlist_path = os.path.join(temp_dir, "playlist.m3u8")
            with open(playlist_path, "w", encoding="utf-8") as playlist:
                playlist.write(
                    '#EXTM3U\n#EXT-X-MAP:URI="init.mp4",BYTERANGE="40@0"\n'
                    "#EXT-X-BYTERANGE:50@10\nvideo.mp4\n"
                    "#EXT-X-BYTERANGE:60@70\nvideo.mp4\n"
                )

            segments = _process_byterange_m3u8(
                playlist_path, temp_dir, "https://cdn.example/path/", 0
            )

        self.assertEqual(
            segments,
            [
                os.path.join(temp_dir, "init_init.mp4"),
                os.path.join(temp_dir, "video_segment_0000.ts"),
                os.path.join(temp_dir, "video_segment_0001.ts"),
            ],
        )
        self.assertEqual(
            [call.args[:3] for call in download.call_args_list],
            [
                (
                    "https://cdn.example/path/init.mp4",
                    os.path.join(temp_dir, "init_init.mp4"),
                    (40, 0),
                ),
                (
                    "https://cdn.example/path/video.mp4",
                    os.path.join(temp_dir, "video_segment_0000.ts"),
                    (50, 10),
                ),
                (
                    "https://cdn.example/path/video.mp4",
                    os.path.join(temp_dir, "video_segment_0001.ts"),
                    (60, 70),
                ),
            ],
        )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_returns_false_when_ffmpeg_missing(self, run):
        run.side_effect = FileNotFoundError

        self.assertFalse(combine_segments_with_ffmpeg(["segment.ts"], "out.mp4"))

    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_filters_playlist_files(self, run, combine):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            playlist_path = os.path.join(temp_dir, "playlist.m3u8")
            segment_path = os.path.join(temp_dir, "segment.ts")
            with open(playlist_path, "w", encoding="utf-8") as playlist:
                playlist.write("#EXTM3U\n")
            with open(segment_path, "wb") as segment:
                segment.write(b"\xff\x00")

            self.assertTrue(
                combine_segments_with_ffmpeg(
                    [playlist_path, segment_path], os.path.join(temp_dir, "out.mp4")
                )
            )

        combine.assert_called_once_with(
            [segment_path], os.path.join(temp_dir, "out.mp4")
        )

    @mock.patch("snapchat_dl.downloader._combine_video_audio_segments")
    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_dict_delegates_video_and_audio(self, run, combine):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        combine.return_value = True
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, "video.ts")
            audio_path = os.path.join(temp_dir, "audio.ts")
            for path in (video_path, audio_path):
                with open(path, "w", encoding="utf-8") as segment:
                    segment.write("media")

            self.assertTrue(
                combine_segments_with_ffmpeg(
                    {"video": [video_path], "audio": [audio_path]}, "out.mp4"
                )
            )

        combine.assert_called_once_with([video_path], [audio_path], "out.mp4")

    def test_combine_video_only_copies_single_segment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_path = os.path.join(temp_dir, "segment.ts")
            output_path = os.path.join(temp_dir, "out.mp4")
            with open(segment_path, "wb") as segment:
                segment.write(b"media")

            self.assertTrue(_combine_video_only_segments([segment_path], output_path))

            with open(output_path, "rb") as output:
                self.assertEqual(output.read(), b"media")

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_video_only_uses_concat_demuxer(self, run):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_paths = [
                os.path.join(temp_dir, f"segment_{i}.ts") for i in range(2)
            ]
            for path in segment_paths:
                with open(path, "wb") as segment:
                    segment.write(b"media")

            self.assertTrue(
                _combine_video_only_segments(
                    segment_paths, os.path.join(temp_dir, "out.mp4")
                )
            )

        concat_path = run.call_args.args[0][7]
        self.assertFalse(os.path.exists(concat_path))

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_download_m3u8_direct_ffmpeg_returns_false_on_timeout(self, run):
        run.side_effect = [
            subprocess.CompletedProcess(["ffmpeg", "-version"], 0),
            subprocess.TimeoutExpired("ffmpeg", 600),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertFalse(
                download_m3u8_direct_ffmpeg(
                    "https://cdn.example/list.m3u8",
                    os.path.join(temp_dir, "out.mp4"),
                )
            )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_download_m3u8_direct_ffmpeg_returns_false_without_output(self, run):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertFalse(
                download_m3u8_direct_ffmpeg(
                    "https://cdn.example/list.m3u8",
                    os.path.join(temp_dir, "out.mp4"),
                )
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
