#!/usr/bin/env python
"""Tests for `snapchat_dl` package."""

import json
import os
import shutil
import unittest
from unittest import mock

from snapchat_dl.snapchat_dl import SnapchatDL
from snapchat_dl.utils import APIResponseError
from snapchat_dl.utils import NoStoriesFound
from snapchat_dl.utils import UserNotFoundError


def teardown_module(module):
    shutil.rmtree(".test-data", ignore_errors=True)


class TestSnapchat_dl(unittest.TestCase):
    """Tests for `snapchat_dl` package."""

    def setUp(self):
        """Set up test fixtures."""
        os.makedirs(".test-data", exist_ok=True)
        self.snapchat_dl = SnapchatDL(
            limit_story=10,
            quiet=True,
            directory_prefix=".test-data",
            dump_json=True,
        )
        self.test_url = "https://example.invalid/video.mp4"
        self.test_url404 = "https://example.invalid/not-found.mp4"
        self.username = "invalidusername"
        self.html = open(
            "tests/mock_data/invalidusername.html", "r", encoding="utf8"
        ).read()
        self.html_api_error = open(
            "tests/mock_data/api-error.html", "r", encoding="utf8"
        ).read()
        self.html_nostories = open(
            "tests/mock_data/invalidusername-nostories.html", "r", encoding="utf8"
        ).read()

    def test_class_init(self):
        """Test snapchat_dl init."""
        self.assertTrue(self.snapchat_dl)

    def test_invalid_username(self):
        """Test snapchat_dl Stories are not available."""
        with self.assertRaises(UserNotFoundError):
            self.snapchat_dl.download("use=rname")

    @mock.patch("snapchat_dl.snapchat_dl.SnapchatDL._web_fetch_story")
    def test_download_username_keyword_compatibility(self, web_fetch_story):
        web_fetch_story.return_value = ([], {})

        with self.assertRaises(NoStoriesFound):
            self.snapchat_dl.download(username=self.username)

    @mock.patch("snapchat_dl.snapchat_dl.SnapchatDL._api_response")
    def test_api_error(self, api_response):
        """Test snapchat_dl Download."""
        api_response.return_value = self.html_api_error
        with self.assertRaises(APIResponseError):
            self.snapchat_dl.download(self.username)

    @mock.patch("snapchat_dl.snapchat_dl.SnapchatDL._api_response")
    @mock.patch("snapchat_dl.snapchat_dl.download_url")
    def test_get_stories(self, download_url, api_response):
        """Test snapchat_dl Download."""
        api_response.return_value = self.html
        self.snapchat_dl.download(self.username)

    @mock.patch("snapchat_dl.snapchat_dl.SnapchatDL._api_response")
    def test_no_stories(self, api_response):
        """Test snapchat_dl Download."""
        api_response.return_value = self.html_nostories
        with self.assertRaises(NoStoriesFound):
            self.snapchat_dl.download(self.username)

    def test_extract_publisher_requested_story(self):
        response_json = {
            "props": {
                "pageProps": {
                    "publicProfileInfo": {"title": "Publisher"},
                    "preselectedStory": {
                        "premiumStory": {
                            "playerStory": {
                                "storyId": {"value": "other-story"},
                                "snapList": [
                                    {
                                        "snapUrls": {
                                            "mediaUrl": "https://example.com/wrong.m3u8"
                                        }
                                    }
                                ],
                            },
                            "timestampInSec": {"value": "100"},
                        }
                    },
                    "premiumStoryList": [
                        {
                            "playerStory": {
                                "storyId": {"value": "requested-story"},
                                "videoTrackUrl": {
                                    "value": "https://example.com/right.m3u8"
                                },
                                "storyTitle": {"value": "Requested"},
                            },
                            "timestampInSec": {"value": "200"},
                        }
                    ],
                }
            }
        }

        stories, publisher, _, _, timestamp = self.snapchat_dl._extract_publisher_data(
            response_json, "requested-story"
        )

        self.assertEqual(publisher["title"], "Publisher")
        self.assertEqual(
            stories[0]["snapUrls"]["mediaUrl"], "https://example.com/right.m3u8"
        )
        self.assertEqual(stories[0]["snapId"]["value"], "requested-story")
        self.assertEqual(timestamp, "200")

    def test_extract_publisher_missing_story(self):
        response_json = {
            "props": {
                "pageProps": {
                    "publicProfileInfo": {"title": "Publisher"},
                    "premiumStoryList": [
                        {
                            "playerStory": {
                                "storyId": {"value": "another-story"},
                                "videoTrackUrl": {
                                    "value": "https://example.com/other.m3u8"
                                },
                            }
                        }
                    ],
                }
            }
        }

        stories, _, _, _, _ = self.snapchat_dl._extract_publisher_data(
            response_json, "missing-story"
        )

        self.assertEqual(stories, [])

    def test_publisher_highlight_url_and_data(self):
        highlight_id = "00000000-0000-4000-8000-000000000001"
        highlight_url = (
            "https://www.snapchat.com/@testpublisher/highlight/" + highlight_id
        )
        self.assertTrue(self.snapchat_dl._is_publisher_url(highlight_url))
        self.assertEqual(
            self.snapchat_dl._parse_publisher_url(highlight_url),
            ("testpublisher", highlight_id),
        )

        response_json = {
            "props": {
                "pageProps": {
                    "publicUserProfile": {"title": "Test Publisher"},
                    "highlight": {
                        "highlightId": {"value": highlight_id},
                        "snapList": [
                            {
                                "snapIndex": index,
                                "snapId": {"value": ""},
                                "snapMediaType": 1,
                                "timestampInSec": {"value": "1791387926"},
                                "snapUrls": {
                                    "mediaUrl": "https://cdn.example/{}.mp4".format(
                                        index
                                    )
                                },
                            }
                            for index in range(3)
                        ],
                    },
                }
            }
        }

        stories, publisher, _, _, timestamp = self.snapchat_dl._extract_publisher_data(
            response_json, highlight_id
        )

        self.assertEqual(publisher["title"], "Test Publisher")
        self.assertEqual(len(stories), 3)
        self.assertEqual(
            [story["snapId"]["value"] for story in stories],
            [
                "{}_0".format(highlight_id),
                "{}_1".format(highlight_id),
                "{}_2".format(highlight_id),
            ],
        )
        self.assertEqual(timestamp, "1791387926")

    def test_official_team_snapchat_publisher_url(self):
        publisher_id = "8af53eee-e298-40c4-9d6e-af20cf881b61"
        story_id = "3137373287454720"
        publisher_url = "https://story.snapchat.com/p/" + publisher_id
        story_url = "https://www.snapchat.com/p/{}/{}".format(publisher_id, story_id)

        self.assertTrue(self.snapchat_dl._is_publisher_url(publisher_url))
        self.assertTrue(self.snapchat_dl._is_publisher_url(story_url))
        self.assertEqual(
            self.snapchat_dl._parse_publisher_url(publisher_url),
            (publisher_id, None),
        )
        self.assertEqual(
            self.snapchat_dl._parse_publisher_url(story_url),
            (publisher_id, story_id),
        )

        response_json = {
            "props": {
                "pageProps": {
                    "publicProfileInfo": {"title": "Team Snapchat"},
                    "preselectedStory": {
                        "premiumStory": {
                            "playerStory": {
                                "storyId": {"value": story_id},
                                "storyTitle": {
                                    "value": "Turn it up with Chantel Jeffries"
                                },
                                "snapList": [
                                    {
                                        "snapIndex": 0,
                                        "snapId": {"value": "official-snap-0"},
                                        "snapMediaType": 1,
                                        "snapUrls": {
                                            "mediaUrl": "https://cdn.example/official-snap.mp4"
                                        },
                                    }
                                ],
                            },
                            "timestampInSec": {"value": "1774430820"},
                        }
                    },
                }
            }
        }

        stories, publisher, _, _, timestamp = self.snapchat_dl._extract_publisher_data(
            response_json, None
        )

        self.assertEqual(publisher["title"], "Team Snapchat")
        self.assertEqual(stories[0]["snapId"]["value"], "official-snap-0")
        self.assertEqual(timestamp, "1774430820")

    def test_official_team_snapchat_spotlight_url(self):
        publisher_id = "8af53eee-e298-40c4-9d6e-af20cf881b61"
        spotlight_id = "W7_EDlXWTBiXAEEniNoMPwAAYcGxsYWxldmNtAaFLLqK9AaFLLqKQAAAAAQ"
        spotlight_url = "https://www.snapchat.com/p/{}/spotlight/{}".format(
            publisher_id, spotlight_id
        )

        self.assertTrue(self.snapchat_dl._is_publisher_url(spotlight_url))
        self.assertEqual(
            self.snapchat_dl._parse_publisher_url(spotlight_url),
            (publisher_id, spotlight_id),
        )

        response_json = {
            "props": {
                "pageProps": {
                    "spotlightFeed": {
                        "spotlightStories": [
                            {
                                "story": {
                                    "storyId": {"value": spotlight_id},
                                    "snapList": [
                                        {
                                            "snapIndex": 0,
                                            "snapId": {"value": spotlight_id},
                                            "snapMediaType": 1,
                                            "timestampInSec": {"value": "1792262709"},
                                            "snapUrls": {
                                                "mediaUrl": "https://cdn.example/spotlight.mp4"
                                            },
                                        }
                                    ],
                                },
                                "metadata": {
                                    "videoMetadata": {
                                        "creator": {
                                            "$case": "personCreator",
                                            "personCreator": {"name": "Team Snapchat"},
                                        }
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        }

        stories, publisher, _, _, timestamp = self.snapchat_dl._extract_publisher_data(
            response_json, spotlight_id
        )

        self.assertEqual(publisher["title"], "Team Snapchat")
        self.assertEqual(
            stories[0]["snapUrls"]["mediaUrl"], "https://cdn.example/spotlight.mp4"
        )
        self.assertEqual(timestamp, "1792262709")

    @mock.patch("snapchat_dl.snapchat_dl.download_url")
    @mock.patch("snapchat_dl.snapchat_dl.download_m3u8_direct_ffmpeg")
    def test_m3u8_story_saves_playlist_after_direct_download(self, direct, download):
        direct.return_value = True
        output_path = os.path.join(self.snapchat_dl.directory_prefix, "story.m3u8")

        self.snapchat_dl._download_m3u8_story(
            "https://cdn.example/story.m3u8",
            os.path.join(self.snapchat_dl.directory_prefix, "segments"),
            output_path,
            0,
        )

        direct.assert_called_once_with(
            "https://cdn.example/story.m3u8", output_path.replace(".m3u8", ".mp4")
        )
        download.assert_called_once_with(
            "https://cdn.example/story.m3u8", output_path, 0
        )

    @mock.patch("snapchat_dl.snapchat_dl.download_url")
    @mock.patch("snapchat_dl.snapchat_dl.combine_segments_with_ffmpeg")
    @mock.patch("snapchat_dl.snapchat_dl.download_m3u8_segments")
    @mock.patch("snapchat_dl.snapchat_dl.download_m3u8_direct_ffmpeg")
    def test_m3u8_story_falls_back_to_segments(
        self, direct, download_segments, combine, download_playlist
    ):
        direct.return_value = False
        download_segments.return_value = ["segment.ts"]
        combine.return_value = True
        output_path = os.path.join(self.snapchat_dl.directory_prefix, "story.m3u8")
        segments_dir = os.path.join(self.snapchat_dl.directory_prefix, "segments")

        self.snapchat_dl._download_m3u8_story(
            "https://cdn.example/story.m3u8", segments_dir, output_path, 0
        )

        download_segments.assert_called_once_with(
            "https://cdn.example/story.m3u8", segments_dir, 0
        )
        combine.assert_called_once_with(
            ["segment.ts"], output_path.replace(".m3u8", ".mp4")
        )
        download_playlist.assert_called_once_with(
            "https://cdn.example/story.m3u8", output_path, 0
        )

    @mock.patch("snapchat_dl.snapchat_dl.download_m3u8_segments", return_value=[])
    @mock.patch(
        "snapchat_dl.snapchat_dl.download_m3u8_direct_ffmpeg", return_value=False
    )
    def test_m3u8_story_logs_when_fallback_has_no_segments(
        self, direct, download_segments
    ):
        self.snapchat_dl._download_m3u8_story(
            "https://cdn.example/story.m3u8",
            os.path.join(self.snapchat_dl.directory_prefix, "segments"),
            os.path.join(self.snapchat_dl.directory_prefix, "story.m3u8"),
            0,
        )

        direct.assert_called_once()
        download_segments.assert_called_once()
