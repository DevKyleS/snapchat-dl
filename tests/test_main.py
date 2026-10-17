"""Tests for the ``python -m snapchat_dl`` entry point."""

import os
import importlib
import runpy
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from snapchat_dl import __main__ as module_main


class TestModuleMain(unittest.TestCase):
    def _args(self, **overrides):
        values = {
            "quiet": False,
            "save_prefix": ".",
            "max_workers": 2,
            "limit_story": -1,
            "sleep_interval": 0,
            "dump_json": False,
            "scan_clipboard": False,
            "check_update": False,
            "interval": 10,
            "username": [],
            "batch_file": None,
            "scan_prefix": False,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_missing_pyperclip_import_disables_clipboard(self):
        with mock.patch.dict(sys.modules, {"pyperclip": None}):
            importlib.reload(module_main)

        self.assertFalse(module_main.CLIPBOARD_AVAILABLE)
        importlib.reload(module_main)

    @mock.patch("snapchat_dl.__main__.logger.add")
    @mock.patch("snapchat_dl.__main__.logger.remove")
    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_quiet_mode_reconfigures_logging(
        self, parse_arguments, downloader_class, remove, add
    ):
        parse_arguments.return_value = self._args(quiet=True)

        module_main.main()

        remove.assert_called_once_with()
        add.assert_called_once_with(sys.stderr, level="ERROR")
        downloader_class.assert_called_once()

    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_regular_mode_combines_usernames_batch_and_prefix(
        self, parse_arguments, downloader_class
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = os.path.join(temp_dir, "users.txt")
            with open(batch_path, "w", encoding="utf-8") as batch_file:
                batch_file.write("batch_user\n\n")
            os.mkdir(os.path.join(temp_dir, "saved_user"))
            parse_arguments.return_value = self._args(
                username=["argument_user"],
                batch_file=batch_path,
                scan_prefix=True,
                save_prefix=temp_dir,
            )
            downloader = downloader_class.return_value

            module_main.main()

        self.assertEqual(
            [call.args[0] for call in downloader.download.call_args_list],
            ["argument_user", "batch_user", "saved_user"],
        )

    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_missing_batch_file_exits(self, parse_arguments, downloader_class):
        with tempfile.TemporaryDirectory() as temp_dir:
            parse_arguments.return_value = self._args(
                batch_file=os.path.join(temp_dir, "missing.txt")
            )

            with self.assertRaises(SystemExit) as raised:
                module_main.main()

        self.assertEqual(raised.exception.code, 1)
        downloader_class.assert_called_once()

    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_missing_prefix_directory_exits(self, parse_arguments, downloader_class):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_prefix = os.path.join(temp_dir, "missing")
            parse_arguments.return_value = self._args(
                scan_prefix=True, save_prefix=missing_prefix
            )

            with self.assertRaises(SystemExit) as raised:
                module_main.main()

        self.assertEqual(raised.exception.code, 1)
        downloader_class.assert_called_once()

    @mock.patch("snapchat_dl.__main__.pyperclip.paste")
    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_clipboard_mode_downloads_urls_and_handles_story_errors(
        self, parse_arguments, downloader_class, paste
    ):
        parse_arguments.return_value = self._args(scan_clipboard=True)
        paste.return_value = (
            "https://story.snapchat.com/publisher/one "
            "https://story.snapchat.com/publisher/two"
        )
        downloader = downloader_class.return_value
        downloader.download.side_effect = [
            module_main.NoStoriesFound("empty"),
            module_main.UserNotFoundError("missing"),
        ]

        with mock.patch("snapchat_dl.__main__.CLIPBOARD_AVAILABLE", True):
            module_main.main()

        self.assertEqual(
            [call.args[0] for call in downloader.download.call_args_list],
            [
                "https://story.snapchat.com/publisher/one",
                "https://story.snapchat.com/publisher/two",
            ],
        )

    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_clipboard_mode_exits_when_clipboard_support_is_missing(
        self, parse_arguments, downloader_class
    ):
        parse_arguments.return_value = self._args(scan_clipboard=True)

        with mock.patch("snapchat_dl.__main__.CLIPBOARD_AVAILABLE", False):
            with self.assertRaises(SystemExit) as raised:
                module_main.main()

        self.assertEqual(raised.exception.code, 1)
        downloader_class.assert_called_once()

    @mock.patch("snapchat_dl.__main__.pyperclip.paste")
    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_clipboard_mode_logs_when_no_story_url_is_found(
        self, parse_arguments, downloader_class, paste
    ):
        parse_arguments.return_value = self._args(scan_clipboard=True)
        paste.return_value = "story.snapchat.com but no URL"

        with mock.patch("snapchat_dl.__main__.CLIPBOARD_AVAILABLE", True):
            module_main.main()

        downloader_class.return_value.download.assert_not_called()

    @mock.patch("snapchat_dl.__main__.pyperclip.paste", return_value="plain text")
    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_clipboard_mode_logs_when_text_has_no_snapchat_domain(
        self, parse_arguments, downloader_class, paste
    ):
        parse_arguments.return_value = self._args(scan_clipboard=True)

        with mock.patch("snapchat_dl.__main__.CLIPBOARD_AVAILABLE", True):
            module_main.main()

        paste.assert_called_once_with()
        downloader_class.return_value.download.assert_not_called()

    @mock.patch(
        "snapchat_dl.__main__.pyperclip.paste", side_effect=RuntimeError("denied")
    )
    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_clipboard_mode_handles_clipboard_errors(
        self, parse_arguments, downloader_class, paste
    ):
        parse_arguments.return_value = self._args(scan_clipboard=True)

        with mock.patch("snapchat_dl.__main__.CLIPBOARD_AVAILABLE", True):
            module_main.main()

        paste.assert_called_once_with()
        downloader_class.return_value.download.assert_not_called()

    @mock.patch("snapchat_dl.__main__.time.sleep", side_effect=KeyboardInterrupt)
    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_update_mode_repeats_download_until_interrupted(
        self, parse_arguments, downloader_class, sleep
    ):
        parse_arguments.return_value = self._args(check_update=True, username=["user"])

        with self.assertRaises(KeyboardInterrupt):
            module_main.main()

        downloader_class.return_value.download.assert_called_once_with("user")
        sleep.assert_called_once_with(10)

    @mock.patch("snapchat_dl.__main__.time.sleep", side_effect=KeyboardInterrupt)
    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_update_mode_logs_download_errors(
        self, parse_arguments, downloader_class, sleep
    ):
        parse_arguments.return_value = self._args(check_update=True, username=["user"])
        downloader_class.return_value.download.side_effect = module_main.NoStoriesFound

        with self.assertRaises(KeyboardInterrupt):
            module_main.main()

        downloader_class.return_value.download.assert_called_once_with("user")
        sleep.assert_called_once_with(10)

    @mock.patch("snapchat_dl.__main__.SnapchatDL")
    @mock.patch("snapchat_dl.__main__.parse_arguments")
    def test_regular_mode_handles_download_errors(
        self, parse_arguments, downloader_class
    ):
        parse_arguments.return_value = self._args(username=["missing_user"])
        downloader_class.return_value.download.side_effect = (
            module_main.UserNotFoundError
        )

        module_main.main()

        downloader_class.return_value.download.assert_called_once_with("missing_user")

    @mock.patch("snapchat_dl.cli.parse_arguments")
    @mock.patch("snapchat_dl.snapchat_dl.SnapchatDL")
    def test_running_module_calls_main(self, downloader_class, parse_arguments):
        parse_arguments.return_value = self._args()

        runpy.run_path(module_main.__file__, run_name="__main__")

        downloader_class.assert_called_once()
