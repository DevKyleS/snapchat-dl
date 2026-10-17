#!/usr/bin/env python3
"""Main module for snapchat-dl CLI."""

import sys
import time
from loguru import logger

from snapchat_dl.cli import parse_arguments
from snapchat_dl.snapchat_dl import SnapchatDL
from snapchat_dl.utils import NoStoriesFound, UserNotFoundError, APIResponseError

# Try to import clipboard functionality
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


def main():
    """Main entry point for snapchat-dl CLI."""
    args = parse_arguments()
    
    # Configure logging
    if args.quiet:
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    
    # Initialize downloader
    downloader = SnapchatDL(
        directory_prefix=args.save_prefix,
        max_workers=args.max_workers,
        limit_story=args.limit_story,
        sleep_interval=args.sleep_interval,
        quiet=args.quiet,
        dump_json=args.dump_json,
    )
    
    # Handle different modes
    if args.scan_clipboard:
        if not CLIPBOARD_AVAILABLE:
            logger.error("Clipboard functionality not available. Install pyperclip: pip install pyperclip")
            sys.exit(1)
        
        try:
            clipboard_content = pyperclip.paste()
            if clipboard_content and ("story.snapchat.com" in clipboard_content):
                # Extract URLs from clipboard
                import re
                urls = re.findall(r'https://story\.snapchat\.com/[^\s]+', clipboard_content)
                if urls:
                    for url in urls:
                        try:
                            downloader.download(url)
                        except (NoStoriesFound, UserNotFoundError, APIResponseError) as e:
                            logger.error(f"Failed to download {url}: {e}")
                else:
                    logger.error("No valid Snapchat story URLs found in clipboard")
            else:
                logger.error("No Snapchat story URLs found in clipboard")
        except Exception as e:
            logger.error(f"Error reading clipboard: {e}")
    
    elif args.check_update:
        # Periodic checking mode
        while True:
            for username_or_url in args.username:
                try:
                    downloader.download(username_or_url)
                except (NoStoriesFound, UserNotFoundError, APIResponseError) as e:
                    if not args.quiet:
                        logger.error(f"Failed to download {username_or_url}: {e}")
            
            logger.info(f"Waiting {args.interval} seconds before next check...")
            time.sleep(args.interval)
    
    else:
        # Regular download mode
        usernames_or_urls = args.username.copy()
        
        # Handle batch file
        if args.batch_file:
            try:
                with open(args.batch_file, 'r') as f:
                    batch_usernames = [line.strip() for line in f if line.strip()]
                    usernames_or_urls.extend(batch_usernames)
            except FileNotFoundError:
                logger.error(f"Batch file not found: {args.batch_file}")
                sys.exit(1)
        
        # Handle scan from prefix
        if args.scan_prefix:
            import os
            try:
                prefix_dirs = [d for d in os.listdir(args.save_prefix) 
                              if os.path.isdir(os.path.join(args.save_prefix, d))]
                usernames_or_urls.extend(prefix_dirs)
            except FileNotFoundError:
                logger.error(f"Prefix directory not found: {args.save_prefix}")
                sys.exit(1)
        
        # Download all requested usernames/URLs
        for username_or_url in usernames_or_urls:
            try:
                downloader.download(username_or_url)
            except (NoStoriesFound, UserNotFoundError, APIResponseError) as e:
                if not args.quiet:
                    logger.error(f"Failed to download {username_or_url}: {e}")


if __name__ == "__main__":
    main()