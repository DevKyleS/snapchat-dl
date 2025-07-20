"""Commandline setup for snapchat_dl."""
import sys
import time

import pyperclip
from loguru import logger

import cli
import snapchat_dl
import utils


def main():
    """Download user stories from Snapchat."""
    args = cli.parse_arguments()
    usernames = args.username + utils.use_batch_file(args) + utils.use_prefix_dir(args)

    downloader = snapchat_dl.SnapchatDL(
        directory_prefix=args.save_prefix,
        max_workers=args.max_workers,
        limit_story=args.limit_story,
        sleep_interval=args.sleep_interval,
        quiet=args.quiet,
        dump_json=args.dump_json,
    )

    history = list()
    print(usernames)

    def download_users(users: list, respect_history=False):
        """Download user story from usernames.

        Args:
            users (list): List of usernames to download.
            respect_history (bool, optional): append username to history. Defaults to False.
            log_str (str, optional): Log log_str to terminal. Defaults to None.
        """
        for username in users:
            print("download_users: user found: " + username)
            time.sleep(args.sleep_interval)

            if respect_history is True:
                if username not in history:
                    history.append(username)
                    try:
                        downloader.download(username)
                    except (utils.NoStoriesFound, utils.UserNotFoundError):
                        pass
            else:
                try:
                    downloader.download(username)
                except (utils.NoStoriesFound, utils.UserNotFoundError):
                    pass

    try:
        download_users(usernames)
        if args.scan_clipboard is True:
            if args.quiet is False:
                logger.info("Listening for clipboard change")

            while True:
                usernames_clip = utils.search_usernames(pyperclip.paste())
                if len(usernames_clip) > 0:
                    download_users(usernames_clip, respect_history=True)

                time.sleep(1)

        if args.check_update is True:
            if args.quiet is False:
                logger.info(
                    "Scheduling story updates for {} users".format(len(usernames))
                )

            while True:
                started_at = int(time.time())
                download_users(usernames)
                if started_at < args.interval:
                    time.sleep(args.interval - started_at)

    except KeyboardInterrupt:
        exit(0)


if __name__ == "__main__":
    sys.exit(main())
