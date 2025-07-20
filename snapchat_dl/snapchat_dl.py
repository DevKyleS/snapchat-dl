"""The Main Snapchat Downloader Class."""

import concurrent.futures
import json
import os
import re

import requests
from loguru import logger

from snapchat_dl.downloader import download_url, download_m3u8_segments, combine_segments_with_ffmpeg
from snapchat_dl.utils import APIResponseError
from snapchat_dl.utils import dump_response
from snapchat_dl.utils import MEDIA_TYPE
from snapchat_dl.utils import NoStoriesFound
from snapchat_dl.utils import strf_time
from snapchat_dl.utils import UserNotFoundError


class SnapchatDL:
    """Interact with Snapchat API to download story."""

    def __init__(
        self,
        directory_prefix=".",
        max_workers=2,
        limit_story=-1,
        sleep_interval=1,
        quiet=False,
        dump_json=False,
    ):
        self.directory_prefix = os.path.abspath(os.path.normpath(directory_prefix))
        self.max_workers = max_workers
        self.limit_story = limit_story
        self.sleep_interval = sleep_interval
        self.quiet = quiet
        self.dump_json = dump_json
        self.endpoint_web = "https://www.snapchat.com/add/{}/"
        self.regexp_web_json = (
            r'<script\s*id="__NEXT_DATA__"\s*type="application\/json">([^<]+)<\/script>'
        )
        self.reaponse_ok = requests.codes.get("ok")

    def _api_response(self, username):
        web_url = self.endpoint_web.format(username)
        return requests.get(
            web_url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            },
        ).text
        return url_or_username.startswith("https://story.snapchat.com/p/")

    def _web_fetch_story(self, username):
            web_url = self.endpoint_web.format(username_or_url)
            return requests.get(
                web_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                },
            ).text

    def _web_fetch_story(self, username_or_url):
        """Download user stories from Web.

        Args:
            username_or_url (str): Snapchat `username` or publisher URL

        Raises:
            APIResponseError: API Error

        Returns:
            (dict, dict): user_info, stories
        """
        response = self._api_response(username_or_url)
        response_json_raw = re.findall(self.regexp_web_json, response)

        try:
            response_json = json.loads(response_json_raw[0])

            # Check if this is a publisher profile
            if self._is_publisher_url(username_or_url):
                publisher_id, story_id = self._parse_publisher_url(username_or_url)
                return self._extract_publisher_data(response_json, story_id)
            else:
                return self._extract_user_data(response_json)
        except (IndexError, KeyError, ValueError):
            raise APIResponseError

    def _extract_user_data(self, response_json):
        """Extract data for regular user profiles."""
        def util_web_user_info(content: dict):
            if "userProfile" in content["props"]["pageProps"]:
                user_profile = content["props"]["pageProps"]["userProfile"]
                field_id = user_profile["$case"]
                return user_profile[field_id]
            else:
                raise UserNotFoundError

        def util_web_story(content: dict):
            if "story" in content["props"]["pageProps"]:
                return content["props"]["pageProps"]["story"]["snapList"]
            return list()

        def util_web_extract(content: dict):
            if "curatedHighlights" in content["props"]["pageProps"]:
                return content["props"]["pageProps"]["curatedHighlights"]
            return list()

        user_info = util_web_user_info(response_json)
        stories = util_web_story(response_json)
        curatedHighlights = util_web_extract(response_json)
        spotHighlights = util_web_extract(response_json)
        return stories, user_info, curatedHighlights, spotHighlights

    def _extract_publisher_data(self, response_json, story_id):
        """Extract data for publisher profiles."""
        def util_publisher_info(content: dict):
            if "publicProfileInfo" in content["props"]["pageProps"]:
                return content["props"]["pageProps"]["publicProfileInfo"]
            raise UserNotFoundError

        def util_publisher_story(content: dict, story_id: str):
            # First check preselectedStory
            page_props = content["props"]["pageProps"]
            if "preselectedStory" in page_props and "premiumStory" in page_props["preselectedStory"]:
                premium_story = page_props["preselectedStory"]["premiumStory"]
                if "playerStory" in premium_story:
                    player_story = premium_story["playerStory"]
                    story_timestamp = premium_story.get("timestampInSec", {}).get("value", "0")
                    
                    # Check if there's a videoTrackUrl (HLS manifest) for the full story
                    if "videoTrackUrl" in player_story and player_story["videoTrackUrl"].get("value"):
                        # Create a single "snap" entry for the full video
                        video_url = player_story["videoTrackUrl"]["value"]
                        story_title = player_story.get("storyTitle", {}).get("value", "story")
                        story_id_value = player_story.get("storyId", {}).get("value", story_timestamp)
                        
                        full_video_snap = {
                            "snapIndex": 0,
                            "snapId": {"value": story_id_value},
                            "snapMediaType": 1,  # Video
                            "snapUrls": {"mediaUrl": video_url},
                            "storyTitle": story_title
                        }
                        return [full_video_snap], story_timestamp
                    
                    # If no videoTrackUrl, fall back to individual snaps with valid URLs
                    snap_list = player_story.get("snapList", [])
                    valid_snaps = [snap for snap in snap_list if snap.get("snapUrls", {}).get("mediaUrl")]
                    if valid_snaps:
                        return valid_snaps, story_timestamp
                        
            # Then check premiumStoryList for specific story ID
            if "premiumStoryList" in page_props:
                premium_stories = page_props["premiumStoryList"]
                for story in premium_stories:
                    if "playerStory" in story:
                        player_story = story["playerStory"]
                        if player_story.get("storyId", {}).get("value") == story_id:
                            story_timestamp = story.get("timestampInSec", {}).get("value", "0")
                            
                            # Check for videoTrackUrl first
                            if "videoTrackUrl" in player_story and player_story["videoTrackUrl"].get("value"):
                                video_url = player_story["videoTrackUrl"]["value"]
                                story_title = player_story.get("storyTitle", {}).get("value", "story")
                                story_id_value = player_story.get("storyId", {}).get("value", story_timestamp)
                                
                                full_video_snap = {
                                    "snapIndex": 0,
                                    "snapId": {"value": story_id_value},
                                    "snapMediaType": 1,
                                    "snapUrls": {"mediaUrl": video_url},
                                    "storyTitle": story_title
                                }
                                return [full_video_snap], story_timestamp
                            
                            # Fall back to valid individual snaps
                            snap_list = player_story.get("snapList", [])
                            valid_snaps = [snap for snap in snap_list if snap.get("snapUrls", {}).get("mediaUrl")]
                            if valid_snaps:
                                return valid_snaps, story_timestamp
                            
            # Fallback: find any story with snaps
            if "premiumStoryList" in page_props:
                premium_stories = page_props["premiumStoryList"]
                for story in premium_stories:
                    if "playerStory" in story:
                        player_story = story["playerStory"]
                        story_timestamp = story.get("timestampInSec", {}).get("value", "0")
                        
                        # Check for videoTrackUrl first
                        if "videoTrackUrl" in player_story and player_story["videoTrackUrl"].get("value"):
                            video_url = player_story["videoTrackUrl"]["value"]
                            story_title = player_story.get("storyTitle", {}).get("value", "story")
                            story_id_value = player_story.get("storyId", {}).get("value", story_timestamp)
                            
                            full_video_snap = {
                                "snapIndex": 0,
                                "snapId": {"value": story_id_value},
                                "snapMediaType": 1,
                                "snapUrls": {"mediaUrl": video_url},
                                "storyTitle": story_title
                            }
                            return [full_video_snap], story_timestamp
                        
                        # Fall back to valid individual snaps
                        snap_list = player_story.get("snapList", [])
                        valid_snaps = [snap for snap in snap_list if snap.get("snapUrls", {}).get("mediaUrl")]
                        if valid_snaps:
                            return valid_snaps, story_timestamp
                            
            return list(), "0"

        publisher_info = util_publisher_info(response_json)
        stories, story_timestamp = util_publisher_story(response_json, story_id)
        
        return stories, publisher_info, [], [], story_timestamp

    def download(self, username_or_url):
        """Download Snapchat Story for `username` or publisher URL.

        Args:
            username_or_url (str): Snapchat `username` or publisher URL

        Returns:
            [bool]: story downloader
        """
        result = self._web_fetch_story(username_or_url)
        
        # Handle different return formats (user stories vs publisher stories)
        if self._is_publisher_url(username_or_url):
            stories, snap_user, _, _, story_timestamp = result
            story_timestamp_int = int(story_timestamp)
        else:
            stories, snap_user, *_ = result
            story_timestamp_int = None

        # Determine display name for logging
        if self._is_publisher_url(username_or_url):
            display_name = snap_user.get("title", "Unknown Publisher")
            # Extract a clean identifier for directory naming
            publisher_id, story_id = self._parse_publisher_url(username_or_url)
            dir_identifier = f"publisher_{publisher_id}"
        else:
            display_name = username_or_url
            dir_identifier = username_or_url

        if len(stories) == 0:
            if self.quiet is False:
                logger.info("\033[91m{}\033[0m has no stories".format(display_name))

            raise NoStoriesFound

        if self.limit_story > -1:
            stories = stories[0 : self.limit_story]

        logger.info("[+] {} has {} stories".format(display_name, len(stories)))

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            for media in stories:
                snap_id = media["snapId"]["value"]
                media_url = media["snapUrls"]["mediaUrl"]
                media_type = media["snapMediaType"]
                
                # Handle timestamp differently for publisher vs user stories
                if self._is_publisher_url(username_or_url):
                    # For publisher stories, use the story timestamp for all snaps
                    timestamp = story_timestamp_int
                else:
                    # For user stories, use the individual snap timestamp
                    timestamp = int(media["timestampInSec"]["value"])
                    
                date_str = strf_time(timestamp, "%Y-%m-%d")

                dir_name = os.path.join(self.directory_prefix, dir_identifier, date_str)

                # Determine file extension based on URL and media type
                if '.m3u8' in media_url:
                    file_extension = 'm3u8'
                else:
                    file_extension = MEDIA_TYPE[media_type]

                filename = strf_time(timestamp, "%Y-%m-%d_%H-%M-%S {} {}.{}").format(
                    snap_id, dir_identifier, file_extension
                )

                if self.dump_json:
                    filename_json = os.path.join(dir_name, filename + ".json")
                    media_json = dict(media)
                    media_json["snapUser"] = snap_user
                    dump_response(media_json, filename_json)

                media_output = os.path.join(dir_name, filename)
                
                # Handle M3U8 files differently - download segments and combine
                if file_extension == 'm3u8':
                    # Create a subdirectory for the segments
                    segments_dir = os.path.join(dir_name, f"segments_{snap_id}")
                    
                    # Download M3U8 segments
                    executor.submit(
                        self._download_m3u8_story, media_url, segments_dir, media_output, 
                        self.sleep_interval
                    )
                else:
                    # Regular file download
                    executor.submit(
                        download_url, media_url, media_output, self.sleep_interval
                    )

        except KeyboardInterrupt:
            executor.shutdown(wait=False)

        logger.info("[✔] {} stories downloaded".format(display_name, len(stories)))

    def _download_m3u8_story(self, media_url: str, segments_dir: str, output_path: str, sleep_interval: int):
        """Download M3U8 story with all segments.

        Args:
            media_url (str): M3U8 playlist URL
            segments_dir (str): directory to save segments
            output_path (str): final output file path
            sleep_interval (int): sleep between downloads
        """
        try:
            # Download all video segments (and audio if it's a master playlist)
            segment_files = download_m3u8_segments(media_url, segments_dir, sleep_interval)
            
            if segment_files:
                # Try to combine segments into a single video file
                video_output = output_path.replace('.m3u8', '.mp4')
                success = combine_segments_with_ffmpeg(segment_files, video_output)
                
                if success:
                    logger.info(f"Video combined successfully: {video_output}")
                    if not self.quiet:
                        logger.info(f"Segments saved in: {segments_dir}")
                else:
                    logger.warning(f"Could not combine segments. Individual segments saved in: {segments_dir}")
                    
                # Also save the original M3U8 file for reference
                try:
                    download_url(media_url, output_path, 0)
                except Exception as e:
                    logger.warning(f"Could not save M3U8 file: {e}")
            else:
                logger.error(f"No segments downloaded for M3U8: {media_url}")
                
        except Exception as e:
            logger.error(f"Failed to download M3U8 story: {e}")
