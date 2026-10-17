"""Utility functions for snapchat_dl."""

import json
import os
import re
from argparse import Namespace
from datetime import datetime, timezone

from loguru import logger

MEDIA_TYPE = ["jpg", "mp4"]


class NoStoriesFound(Exception):
    """No stories found."""

    pass


class APIResponseError(Exception):
    """Invalid API Response"""

    pass


class UserNotFoundError(Exception):
    """User not found"""

    pass


def strf_time(timestamp, format_str):
    """Format unix timestamp to custom format.

    Args:
        timestamp (int): unix timestamp
        format_str (str): valid python date time format

    Returns:
        str: timestamp formatted to custom format.
    """
    utc_time = datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
    return utc_time.strftime(format_str)


def valid_username(username):
    """Validate Username.

    Args:
        username (str): Snapchat Username

    Returns:
        bool: True if username is valid.
    """
    match = re.match(r"(?P<username>^[\-\w\.\_]{3,15}$)", username)
    if match is None:
        return False

    return match and match.groupdict()["username"] == username


def search_usernames(string: str) -> list:
    """Return list of usernames found in a string.

    Args:
        string (str): string to search for usernames

    Returns:
        list: usernames found in string
    """
    return list(
        sorted(
            set(
                username
                for username in re.findall(
                    r"https?://(?:story|www).snapchat.com/(?:[suad]+/|@)([\-\w\.\_]{3,15})",
                    string,
                )
                if valid_username(username)
            )
        )
    )


def search_publisher_urls(string: str) -> list:
    """Return publisher story and highlight URLs found in a string."""
    publisher_urls = re.findall(
        r"https://(?:story\.snapchat\.com|(?:www\.)?snapchat\.com)/p/"
        r"[a-f0-9-]+(?:/[0-9]+|/spotlight/[A-Za-z0-9_-]+)?"
        r"|https://(?:www\.)?snapchat\.com/@[\w.-]+/highlight/[a-f0-9-]+",
        string,
    )
    return list(sorted(set(publisher_urls)))


def use_batch_file(args: Namespace) -> list:
    """Return list of usernames and publisher URLs from file args.batch_file.

    Args:
        args (Namespace): argparse Namespace

    Raises:
        os.error: raises if batch_file not found

    Returns:
        list: usernames and publisher URLs read from batch_file
    """
    usernames = list()
    if args.batch_file is not None:
        if os.path.isfile(args.batch_file) is False:
            error_msg = "Invalid Batch File at {}".format(args.batch_file)
            logger.error(error_msg)
            raise Exception(error_msg)

        with open(args.batch_file, "r") as f:
            for u in f.read().split("\n"):
                username = u.strip()
                # Check if it's a valid username or a publisher URL
                if (
                    valid_username(username)
                    or username.startswith("https://story.snapchat.com/p/")
                ) and username not in usernames:
                    usernames.append(username)

    return usernames


def use_prefix_dir(args: Namespace):
    """Return dirnames as username from file args.scan_prefix.

    Args:
        args (Namespace): argparse Namespace

    Returns:
        list: usernames read from scan_prefix
    """
    usernames = list()
    if args.scan_prefix:
        for username in [
            o
            for o in os.listdir(args.save_prefix)
            if os.path.isdir(os.path.join(args.save_prefix, o))
        ]:
            if username not in usernames and valid_username(username):
                usernames.append(username)

        if args.quiet is False:
            logger.info(
                "Added {} usernames from {}".format(len(usernames), args.save_prefix)
            )

    return list(sorted(set(usernames)))


def dump_text_file(content: str, filepath: str):
    """Write content to filepath using `tx` mode.

    Args:
        content (str): File content to write.
        filepath (str): Filepath.

    This will overwrite the file.
    """
    dirpath = os.path.dirname(filepath)

    os.makedirs(dirpath, exist_ok=True)

    if not os.path.isfile(filepath):
        with open(filepath, "w+") as f:
            f.write(content)


def dump_response(content: dict, path: str):
    """Save JSON file

    Args:
        content: JSON data
        path: Path to save json

    Returns:
        None
    """
    dump_text_file(json.dumps(content), path)
