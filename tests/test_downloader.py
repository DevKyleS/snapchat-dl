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
        os.makedirs(".test-data", exist_ok=True)
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

    @mock.patch("snapchat_dl.downloader.tqdm")
    @mock.patch("snapchat_dl.downloader.download_url")
    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_m3u8_progress_tracks_init_and_segments(self, get, download, progress):
        response = self._playlist_response(
            '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\nsegment_1.ts\nsegment_2.ts\n'
        )
        get.return_value = response
        with mock.patch("snapchat_dl.downloader.sys.stderr.isatty", return_value=True):
            with tempfile.TemporaryDirectory() as temp_dir:
                segments = download_m3u8_segments(
                    "https://cdn.example/list.m3u8", temp_dir, 0
                )

        self.assertEqual(len(segments), 2)
        self.assertEqual(progress.call_args.kwargs["total"], 3)
        self.assertEqual(progress.return_value.update.call_count, 3)
        progress.return_value.close.assert_called_once_with()

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_m3u8_master_without_video_returns_empty_list(self, get):
        get.return_value = self._playlist_response("#EXTM3U\n#EXT-X-STREAM-INF\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(
                download_m3u8_segments("https://cdn.example/master.m3u8", temp_dir, 0),
                [],
            )

    @mock.patch("snapchat_dl.downloader.download_url")
    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_master_playlist_handles_absolute_audio_and_bad_bandwidth(
        self, get, download
    ):
        get.side_effect = [
            self._playlist_response(
                '#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,URI="https://cdn.example/audio.m3u8"\n'
                "#EXT-X-STREAM-INF:BANDWIDTH=invalid\n"
                "https://cdn.example/video.m3u8\n"
            ),
            self._playlist_response("#EXTM3U\nvideo.ts\n"),
            self._playlist_response("#EXTM3U\n"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            segments = download_m3u8_segments(
                "https://cdn.example/path/master.m3u8", temp_dir, 0
            )

        self.assertEqual(segments, [os.path.join(temp_dir, "segment_0000.ts")])
        self.assertEqual(
            [call.args[0] for call in get.call_args_list],
            [
                "https://cdn.example/path/master.m3u8",
                "https://cdn.example/video.m3u8",
                "https://cdn.example/audio.m3u8",
            ],
        )
        self.assertEqual(download.call_count, 1)

    @mock.patch("snapchat_dl.downloader.download_url")
    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_media_playlist_handles_absolute_and_malformed_map_uris(
        self, get, download
    ):
        get.return_value = self._playlist_response(
            '#EXTM3U\n#EXT-X-MAP:URI="https://cdn.example/init.mp4"\n'
            "#EXT-X-MAP:URI=missing-quotes\nsegment.ts\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            segments = download_m3u8_segments(
                "https://cdn.example/path/list.m3u8", temp_dir, 0
            )

        self.assertEqual(segments, [os.path.join(temp_dir, "segment_0000.ts")])
        self.assertEqual(
            [call.args[:2] for call in download.call_args_list],
            [
                (
                    "https://cdn.example/init.mp4",
                    os.path.join(temp_dir, "https://cdn.example/init.mp4"),
                ),
                (
                    "https://cdn.example/path/segment.ts",
                    os.path.join(temp_dir, "segment_0000.ts"),
                ),
            ],
        )

    @mock.patch("snapchat_dl.downloader.download_url")
    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_media_playlist_keeps_existing_segments_and_skips_failed_downloads(
        self, get, download
    ):
        get.return_value = self._playlist_response(
            '#EXTM3U\n#EXT-X-MAP:URI="init-failed.mp4"\n'
            '#EXT-X-MAP:URI="init-existing.mp4"\nsegment-existing.ts\n'
            "segment-failed.ts\n"
        )

        def fail_selected_downloads(url, dest, sleep_interval):
            if dest.endswith("init-failed.mp4") or dest.endswith("segment_0001.ts"):
                raise RequestException("download failed")
            raise FileExistsError

        download.side_effect = fail_selected_downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            segments = download_m3u8_segments(
                "https://cdn.example/path/list.m3u8", temp_dir, 0
            )

        self.assertEqual(segments, [os.path.join(temp_dir, "segment_0000.ts")])
        self.assertEqual(download.call_count, 4)

    def test_combine_segments_rejects_empty_inputs(self):
        self.assertFalse(combine_segments_with_ffmpeg([], "out.mp4"))

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_rejects_dictionary_without_video(self, run):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)

        self.assertFalse(
            combine_segments_with_ffmpeg({"audio": ["audio.ts"]}, "out.mp4")
        )

    @mock.patch("snapchat_dl.downloader._combine_video_audio_segments")
    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_keeps_binary_and_unreadable_audio_video(
        self, run, combine
    ):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        combine.return_value = True
        with tempfile.TemporaryDirectory() as temp_dir:
            video_binary = os.path.join(temp_dir, "video.ts")
            audio_binary = os.path.join(temp_dir, "audio.ts")
            video_unreadable = os.path.join(temp_dir, "video_dir")
            audio_unreadable = os.path.join(temp_dir, "audio_dir")
            os.mkdir(video_unreadable)
            os.mkdir(audio_unreadable)
            with open(video_binary, "wb") as segment:
                segment.write(b"\xff")
            with open(audio_binary, "wb") as segment:
                segment.write(b"\xff")

            result = combine_segments_with_ffmpeg(
                {
                    "video": [video_binary, video_unreadable, "missing-video.ts"],
                    "audio": [audio_binary, audio_unreadable, "missing-audio.ts"],
                },
                "out.mp4",
            )

        self.assertTrue(result)
        combine.assert_called_once_with(
            [video_binary, video_unreadable],
            [audio_binary, audio_unreadable],
            "out.mp4",
        )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_rejects_playlist_only_input(self, run):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            playlist_path = os.path.join(temp_dir, "playlist.m3u8")
            with open(playlist_path, "w", encoding="utf-8") as playlist:
                playlist.write("#EXTM3U\n")

            self.assertFalse(combine_segments_with_ffmpeg([playlist_path], "out.mp4"))

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

    def test_process_byterange_returns_empty_for_missing_playlist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(
                _process_byterange_m3u8(
                    os.path.join(temp_dir, "missing.m3u8"),
                    temp_dir,
                    "https://cdn.example/path/",
                    0,
                ),
                [],
            )

    @mock.patch("snapchat_dl.downloader._download_byterange_segment")
    def test_process_byterange_continues_implicit_offset_for_same_resource(
        self, download
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            playlist_path = os.path.join(temp_dir, "playlist.m3u8")
            with open(playlist_path, "w", encoding="utf-8") as playlist:
                playlist.write(
                    "#EXTM3U\n#EXT-X-BYTERANGE:50@10\nshared.mp4\n"
                    "#EXT-X-BYTERANGE:60\nshared.mp4\n"
                )

            segments = _process_byterange_m3u8(
                playlist_path, temp_dir, "https://cdn.example/path/", 0
            )

        self.assertEqual(len(segments), 2)
        self.assertEqual(
            [call.args[2] for call in download.call_args_list],
            [(50, 10), (60, 60)],
        )

    @mock.patch("snapchat_dl.downloader._download_byterange_segment")
    def test_process_byterange_logs_failures_and_progress(self, download):
        download.side_effect = [
            RuntimeError("init failed"),
            RuntimeError("segment failed"),
        ] + [None] * 10
        with tempfile.TemporaryDirectory() as temp_dir:
            playlist_path = os.path.join(temp_dir, "playlist.m3u8")
            with open(playlist_path, "w", encoding="utf-8") as playlist:
                playlist.write(
                    '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n'
                    "#EXT-X-BYTERANGE:50\nhttps://cdn.example/first.ts\n"
                    + "\n".join(f"segment_{index}.ts" for index in range(10))
                )

            segments = _process_byterange_m3u8(
                playlist_path, temp_dir, "https://cdn.example/path/", 0
            )

        self.assertEqual(len(segments), 10)
        self.assertEqual(download.call_args_list[1].args[2], (50, 0))
        self.assertEqual(
            download.call_args_list[2].args[0], "https://cdn.example/path/segment_0.ts"
        )

    @mock.patch("snapchat_dl.downloader.requests.get")
    def test_download_byterange_skips_existing_file(self, get):
        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "segment.ts")
            with open(dest_path, "wb") as segment:
                segment.write(b"already downloaded")

            self.assertIsNone(
                _download_byterange_segment(
                    "https://cdn.example/video.mp4", dest_path, None, 0
                )
            )

        get.assert_not_called()

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_download_m3u8_direct_ffmpeg_returns_false_when_unavailable(self, run):
        for error in (
            subprocess.CalledProcessError(1, "ffmpeg"),
            FileNotFoundError("ffmpeg"),
            subprocess.TimeoutExpired("ffmpeg", 10),
        ):
            with self.subTest(error=type(error).__name__):
                run.side_effect = error
                self.assertFalse(
                    download_m3u8_direct_ffmpeg(
                        "https://cdn.example/list.m3u8", "out.mp4"
                    )
                )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_download_m3u8_direct_ffmpeg_handles_command_failure(self, run):
        run.side_effect = [
            subprocess.CompletedProcess(["ffmpeg", "-version"], 0),
            subprocess.CompletedProcess(["ffmpeg"], 1, stderr="bad playlist"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertFalse(
                download_m3u8_direct_ffmpeg(
                    "https://cdn.example/list.m3u8",
                    os.path.join(temp_dir, "out.mp4"),
                )
            )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_download_m3u8_direct_ffmpeg_handles_unexpected_error(self, run):
        run.side_effect = [
            subprocess.CompletedProcess(["ffmpeg", "-version"], 0),
            OSError("cannot execute ffmpeg"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertFalse(
                download_m3u8_direct_ffmpeg(
                    "https://cdn.example/list.m3u8",
                    os.path.join(temp_dir, "out.mp4"),
                )
            )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_returns_false_when_ffmpeg_missing(self, run):
        run.side_effect = FileNotFoundError

        self.assertFalse(combine_segments_with_ffmpeg(["segment.ts"], "out.mp4"))

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_returns_false_when_ffmpeg_check_fails(self, run):
        run.side_effect = subprocess.CalledProcessError(1, "ffmpeg")

        self.assertFalse(combine_segments_with_ffmpeg(["segment.ts"], "out.mp4"))

    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_filters_playlist_files(self, run, combine):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            playlist_path = os.path.join(temp_dir, "playlist.m3u8")
            text_segment_path = os.path.join(temp_dir, "text_segment.ts")
            segment_path = os.path.join(temp_dir, "segment.ts")
            with open(playlist_path, "w", encoding="utf-8") as playlist:
                playlist.write("#EXTM3U\n")
            with open(text_segment_path, "w", encoding="utf-8") as segment:
                segment.write("media")
            with open(segment_path, "wb") as segment:
                segment.write(b"\xff\x00")

            self.assertTrue(
                combine_segments_with_ffmpeg(
                    [playlist_path, text_segment_path, segment_path],
                    os.path.join(temp_dir, "out.mp4"),
                )
            )

        combine.assert_called_once_with(
            [text_segment_path, segment_path], os.path.join(temp_dir, "out.mp4")
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

    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_segments_keeps_unreadable_legacy_media(self, run, combine):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        combine.return_value = True
        with tempfile.TemporaryDirectory() as temp_dir:
            unreadable_path = os.path.join(temp_dir, "unreadable")
            os.mkdir(unreadable_path)

            self.assertTrue(combine_segments_with_ffmpeg([unreadable_path], "out.mp4"))

        combine.assert_called_once_with([unreadable_path], "out.mp4")

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_video_audio_rejects_missing_video(self, run):
        self.assertFalse(_combine_video_audio_segments([], ["audio.ts"], "out.mp4"))
        run.assert_not_called()

    @mock.patch(
        "snapchat_dl.downloader._combine_video_only_segments", return_value=False
    )
    def test_combine_video_audio_rejects_failed_video_combination(self, combine):
        self.assertFalse(_combine_video_audio_segments(["video.ts"], [], "out.mp4"))
        combine.assert_called_once()

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    def test_combine_video_audio_success_cleans_temp_files(self, combine, run):
        def create_temp_file(files, output_path):
            with open(output_path, "wb") as output:
                output.write(b"media")
            return True

        combine.side_effect = create_temp_file
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "story.mp4")

            self.assertTrue(
                _combine_video_audio_segments(["video.ts"], ["audio.ts"], output_path)
            )

            self.assertFalse(
                os.path.exists(output_path.replace(".mp4", "_video_temp.mp4"))
            )
            self.assertFalse(
                os.path.exists(output_path.replace(".mp4", "_audio_temp.mp4"))
            )

    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    def test_combine_video_audio_without_audio_moves_video(self, combine):
        def create_video(files, output_path):
            with open(output_path, "wb") as output:
                output.write(b"video")
            return True

        combine.side_effect = create_video
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "story.mp4")

            self.assertTrue(
                _combine_video_audio_segments(["video.ts"], [], output_path)
            )

            with open(output_path, "rb") as output:
                self.assertEqual(output.read(), b"video")

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    def test_audio_merge_failure_tolerates_audio_temp_cleanup_error(self, combine, run):
        def create_temp_media(files, output_path):
            content = b"audio" if "audio_temp" in output_path else b"video"
            with open(output_path, "wb") as output:
                output.write(content)
            return True

        combine.side_effect = create_temp_media
        run.return_value = subprocess.CompletedProcess(
            ["ffmpeg"], 1, stdout="", stderr="merge failed"
        )
        original_unlink = os.unlink

        def fail_audio_cleanup(path):
            if path.endswith("_audio_temp.mp4"):
                raise OSError("busy")
            return original_unlink(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "story.mp4")
            with mock.patch(
                "snapchat_dl.downloader.os.unlink", side_effect=fail_audio_cleanup
            ):
                self.assertTrue(
                    _combine_video_audio_segments(
                        ["video.ts"], ["audio.ts"], output_path
                    )
                )

            with open(output_path, "rb") as output:
                self.assertEqual(output.read(), b"video")

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    def test_combine_video_audio_success_tolerates_cleanup_errors(self, combine, run):
        def create_temp_file(files, output_path):
            with open(output_path, "wb") as output:
                output.write(b"media")
            return True

        combine.side_effect = create_temp_file
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        original_unlink = os.unlink

        def fail_temp_cleanup(path):
            if path.endswith(("_video_temp.mp4", "_audio_temp.mp4")):
                raise OSError("busy")
            return original_unlink(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "story.mp4")

            with mock.patch(
                "snapchat_dl.downloader.os.unlink", side_effect=fail_temp_cleanup
            ) as unlink:
                self.assertTrue(
                    _combine_video_audio_segments(
                        ["video.ts"], ["audio.ts"], output_path
                    )
                )

            self.assertEqual(unlink.call_count, 2)

    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    def test_combine_video_audio_uses_video_when_audio_combination_fails(self, combine):
        def create_video_only(files, output_path):
            if "audio_temp" in output_path:
                return False
            with open(output_path, "wb") as output:
                output.write(b"video")
            return True

        combine.side_effect = create_video_only
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "story.mp4")

            self.assertTrue(
                _combine_video_audio_segments(["video.ts"], ["audio.ts"], output_path)
            )

            with open(output_path, "rb") as output:
                self.assertEqual(output.read(), b"video")

    @mock.patch("snapchat_dl.downloader._combine_video_only_segments")
    def test_combine_video_audio_handles_unexpected_errors(self, combine):
        combine.side_effect = RuntimeError("combine failed")

        self.assertFalse(_combine_video_audio_segments(["video.ts"], [], "out.mp4"))

    def test_combine_video_only_rejects_empty_input(self):
        self.assertFalse(_combine_video_only_segments([], "out.mp4"))

    @mock.patch(
        "snapchat_dl.downloader.shutil.copy2", side_effect=OSError("copy failed")
    )
    def test_combine_video_only_handles_copy_errors(self, copy):
        self.assertFalse(_combine_video_only_segments(["segment.ts"], "out.mp4"))
        copy.assert_called_once_with("segment.ts", "out.mp4")

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
    def test_combine_video_only_returns_false_when_ffmpeg_fails(self, run):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 1, stderr="failed")
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = [os.path.join(temp_dir, f"{index}.ts") for index in range(2)]
            for path in paths:
                with open(path, "wb") as segment:
                    segment.write(b"media")

            self.assertFalse(
                _combine_video_only_segments(paths, os.path.join(temp_dir, "out.mp4"))
            )

    @mock.patch("snapchat_dl.downloader.subprocess.run")
    def test_combine_video_only_tolerates_concat_file_cleanup_error(self, run):
        run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)
        original_unlink = os.unlink

        def fail_concat_cleanup(path):
            if path.endswith(".txt"):
                raise OSError("busy")
            return original_unlink(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = [os.path.join(temp_dir, f"{index}.ts") for index in range(2)]
            for path in paths:
                with open(path, "wb") as segment:
                    segment.write(b"media")

            with mock.patch(
                "snapchat_dl.downloader.os.unlink", side_effect=fail_concat_cleanup
            ) as unlink:
                self.assertTrue(
                    _combine_video_only_segments(
                        paths, os.path.join(temp_dir, "out.mp4")
                    )
                )

            unlink.assert_called_once()

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
