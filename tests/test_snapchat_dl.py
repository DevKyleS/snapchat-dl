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
    shutil.rmtree(".test-data")


class TestSnapchat_dl(unittest.TestCase):
    """Tests for `snapchat_dl` package."""

    def setUp(self):
        """Set up test fixtures."""
        self.snapchat_dl = SnapchatDL(
            limit_story=10,
            quiet=True,
            directory_prefix=".test-data",
            dump_json=True,
        )
        self.test_url = (
            "https://sample-videos.com/video321/mp4/240/big_buck_bunny_240p_1mb.mp4"
        )
        self.test_url404 = "https://google.com/error.html"
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

    @mock.patch("snapchat_dl.snapchat_dl.SnapchatDL._api_response")
    def test_api_error(self, api_response):
        """Test snapchat_dl Download."""
        api_response.return_value = self.html_api_error
        with self.assertRaises(APIResponseError):
            self.snapchat_dl.download(self.username)

    @mock.patch("snapchat_dl.snapchat_dl.SnapchatDL._api_response")
    def test_get_stories(self, api_response):
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
                                    {"snapUrls": {"mediaUrl": "https://example.com/wrong.m3u8"}}
                                ],
                            },
                            "timestampInSec": {"value": "100"},
                        }
                    },
                    "premiumStoryList": [
                        {
                            "playerStory": {
                                "storyId": {"value": "requested-story"},
                                "videoTrackUrl": {"value": "https://example.com/right.m3u8"},
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
        self.assertEqual(stories[0]["snapUrls"]["mediaUrl"], "https://example.com/right.m3u8")
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
                                "videoTrackUrl": {"value": "https://example.com/other.m3u8"},
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
