"""File Downloader for snapchat_dl."""

import os
import sys
import threading
import time
import urllib.parse
import subprocess
import tempfile
import shutil

import requests
from loguru import logger
from tqdm import tqdm

_progress_position_lock = threading.Lock()
_active_progress_positions = set()


def _reserve_progress_position():
    with _progress_position_lock:
        position = 0
        while position in _active_progress_positions:
            position += 1
        _active_progress_positions.add(position)
        return position


def _release_progress_position(position):
    with _progress_position_lock:
        _active_progress_positions.remove(position)


def download_url(url: str, dest: str, sleep_interval: int):
    """Download URL to destionation path.

    Args:
        url (str): url to download
        dest (str): absolute path to destination

    Raises:
        response.raise_for_status: if response is 4** or 50*
        FileExistsError: if file is already downloaded
    """
    if len(os.path.dirname(dest)) > 0:
        os.makedirs(os.path.dirname(dest), exist_ok=True)

    """Rate limiting."""
    time.sleep(sleep_interval)

    try:
        response = requests.get(url, stream=True, timeout=10)
    except requests.exceptions.ConnectTimeout:
        response = requests.get(url, stream=True, timeout=10)

    if response.status_code != requests.codes.get("ok"):
        raise response.raise_for_status()

    if os.path.isfile(dest) and os.path.getsize(dest) == response.headers.get(
        "content-length"
    ):
        raise FileExistsError

    if os.path.isfile(dest) and os.path.getsize(dest) == 0:
        os.remove(dest)
    try:
        with open(dest, "xb") as handle:
            try:
                for data in response.iter_content(chunk_size=4194304):
                    handle.write(data)
                handle.close()
            except requests.exceptions.RequestException as e:
                logger.error(e)
    except FileExistsError as e:
        pass


def download_m3u8_segments(
    url: str,
    dest_dir: str,
    sleep_interval: int,
    show_progress: bool = True,
):
    """Download M3U8 playlist and all its video segments.

    This function serves as a fallback when direct FFmpeg download fails.
    Handles both master playlists and individual stream playlists.

    Args:
        url (str): M3U8 playlist URL
        dest_dir (str): directory to save segments
        sleep_interval (int): sleep between downloads

    Returns:
        list or dict: paths to downloaded segment files, or dict with video/audio keys
    """
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    # Download the M3U8 playlist first
    try:
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            },
        )
        response.raise_for_status()
        playlist_content = response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download M3U8 playlist: {e}")
        return []

    base_url = url.rsplit("/", 1)[0] + "/"

    # Check if this is a master playlist (contains EXT-X-STREAM-INF)
    if "#EXT-X-STREAM-INF" in playlist_content:
        logger.info("Detected master playlist, looking for video and audio streams...")

        # Find the best quality video stream and audio stream
        lines = playlist_content.split("\n")
        best_bandwidth = 0
        best_stream_url = None
        audio_stream_url = None

        # First pass: find audio stream
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("#EXT-X-MEDIA:TYPE=AUDIO"):
                if 'URI="' in line:
                    uri_start = line.find('URI="') + 5
                    uri_end = line.find('"', uri_start)
                    if uri_start > 4 and uri_end > uri_start:
                        audio_uri = line[uri_start:uri_end]
                        if audio_uri.startswith("http"):
                            audio_stream_url = audio_uri
                        else:
                            audio_stream_url = urllib.parse.urljoin(base_url, audio_uri)
                        logger.info(f"Found audio stream: {audio_stream_url}")

        # Second pass: find best video stream
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("#EXT-X-STREAM-INF"):
                # Extract bandwidth
                bandwidth = 0
                if "BANDWIDTH=" in line:
                    bandwidth_str = line.split("BANDWIDTH=")[1].split(",")[0]
                    try:
                        bandwidth = int(bandwidth_str)
                    except ValueError:
                        pass

                # Check next line for stream URL
                if i + 1 < len(lines):
                    stream_url = lines[i + 1].strip()
                    if stream_url and not stream_url.startswith("#"):
                        if not stream_url.startswith("http"):
                            stream_url = urllib.parse.urljoin(base_url, stream_url)

                        if bandwidth >= best_bandwidth:
                            best_bandwidth = bandwidth
                            best_stream_url = stream_url

        if best_stream_url:
            logger.info(
                f"Selected video stream with bandwidth {best_bandwidth}: {best_stream_url}"
            )

            # Download video segments
            video_segments = download_m3u8_segments(
                best_stream_url, dest_dir, sleep_interval, show_progress
            )

            # Download audio segments if audio stream exists
            audio_segments = []
            if audio_stream_url:
                audio_dest_dir = os.path.join(dest_dir, "audio")
                logger.info(f"Downloading audio stream to: {audio_dest_dir}")
                audio_segments = download_m3u8_segments(
                    audio_stream_url, audio_dest_dir, sleep_interval, show_progress
                )

            # Return both video and audio segments for merging
            if audio_segments:
                return {"video": video_segments, "audio": audio_segments}
            else:
                return video_segments
        else:
            logger.error("No video stream found in master playlist")
            return []

    # This is a media playlist, process segments normally
    segment_urls = []
    segment_files = []
    init_files = []

    lines = playlist_content.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()

        # Check for EXT-X-MAP (initialization segment)
        if line.startswith("#EXT-X-MAP:"):
            # Extract URI from EXT-X-MAP:URI="filename"
            uri_start = line.find('URI="') + 5
            uri_end = line.find('"', uri_start)
            if uri_start > 4 and uri_end > uri_start:
                init_uri = line[uri_start:uri_end]
                if init_uri.startswith("http"):
                    init_url = init_uri
                else:
                    init_url = urllib.parse.urljoin(base_url, init_uri)
                init_files.append((init_uri, init_url))

        # Regular segment URLs
        elif line and not line.startswith("#"):
            # This is a segment URL
            if line.startswith("http"):
                segment_url = line
            else:
                # Relative URL, combine with base URL
                segment_url = urllib.parse.urljoin(base_url, line)
            segment_urls.append(segment_url)

    logger.info(
        f"Found {len(init_files)} initialization files and {len(segment_urls)} video segments to download"
    )

    progress_visible = show_progress and sys.stderr.isatty()
    progress_position = _reserve_progress_position() if progress_visible else 0
    playlist_name = os.path.basename(urllib.parse.urlparse(url).path) or "HLS"
    progress = tqdm(
        total=len(init_files) + len(segment_urls),
        desc=f"Downloading {playlist_name}",
        unit="segment",
        position=progress_position,
        leave=False,
        disable=not progress_visible,
    )
    try:
        # Download initialization files first (needed for byte-range M3U8 playlists).
        for init_filename, init_url in init_files:
            init_path = os.path.join(dest_dir, init_filename)
            try:
                download_url(init_url, init_path, sleep_interval)
                if not progress_visible and show_progress:
                    logger.info(f"Downloaded initialization file: {init_filename}")
            except (requests.exceptions.RequestException, FileExistsError) as e:
                if isinstance(e, FileExistsError):
                    logger.info(f"Initialization file already exists: {init_filename}")
                else:
                    logger.error(
                        f"Failed to download initialization file {init_filename}: {e}"
                    )
            finally:
                progress.update(1)

        # Download each segment.
        for i, segment_url in enumerate(segment_urls):
            segment_filename = f"segment_{i:04d}.ts"
            segment_path = os.path.join(dest_dir, segment_filename)

            try:
                download_url(segment_url, segment_path, sleep_interval)
                if not progress_visible and show_progress:
                    logger.info(
                        f"Downloaded segment {i+1}/{len(segment_urls)}: {segment_filename}"
                    )
                segment_files.append(segment_path)
            except (requests.exceptions.RequestException, FileExistsError) as e:
                if isinstance(e, FileExistsError):
                    logger.info(
                        f"Segment {i+1}/{len(segment_urls)} already exists: {segment_filename}"
                    )
                    segment_files.append(segment_path)
                else:
                    logger.error(f"Failed to download segment {i+1}: {e}")
            finally:
                progress.update(1)
    finally:
        progress.close()
        if progress_visible:
            _release_progress_position(progress_position)

    return segment_files


def combine_segments_with_ffmpeg(segment_files, output_path: str):
    """Combine video segments into a single file using ffmpeg (if available).

    Args:
        segment_files: list of segment file paths OR dict with 'video' and 'audio' keys
        output_path (str): path for the combined output file

    Returns:
        bool: True if successful, False otherwise
    """
    if not segment_files:
        logger.warning("No segments to combine")
        return False

    try:
        # Check if ffmpeg is available
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("FFmpeg not found. Cannot combine segments.")
        return False

    # Handle both old format (list) and new format (dict with video/audio)
    if isinstance(segment_files, dict):
        video_files = segment_files.get("video", [])
        audio_files = segment_files.get("audio", [])

        if not video_files:
            logger.warning("No video files found for combination")
            return False

        # Filter to only actual media files for video
        video_media_files = []
        for f in video_files:
            if os.path.exists(f):
                try:
                    with open(f, "r", encoding="utf-8") as test_file:
                        first_line = test_file.readline().strip()
                    if first_line != "#EXTM3U":
                        video_media_files.append(f)
                except UnicodeDecodeError:
                    # Binary file, keep it
                    video_media_files.append(f)
                except Exception:
                    # If we can't read it, assume it's a media file
                    video_media_files.append(f)

        # Filter to only actual media files for audio
        audio_media_files = []
        for f in audio_files:
            if os.path.exists(f):
                try:
                    with open(f, "r", encoding="utf-8") as test_file:
                        first_line = test_file.readline().strip()
                    if first_line != "#EXTM3U":
                        audio_media_files.append(f)
                except UnicodeDecodeError:
                    # Binary file, keep it
                    audio_media_files.append(f)
                except Exception:
                    # If we can't read it, assume it's a media file
                    audio_media_files.append(f)

        return _combine_video_audio_segments(
            video_media_files, audio_media_files, output_path
        )
    else:
        # Legacy format - just video segments
        media_files = []
        for f in segment_files:
            if os.path.exists(f):
                try:
                    with open(f, "r", encoding="utf-8") as test_file:
                        first_line = test_file.readline().strip()
                    if first_line != "#EXTM3U":
                        media_files.append(f)
                except UnicodeDecodeError:
                    # Binary file, keep it
                    media_files.append(f)
                except Exception:
                    # If we can't read it, assume it's a media file
                    media_files.append(f)

        if not media_files:
            logger.warning("No valid media files found for concatenation")
            return False

        return _combine_video_only_segments(media_files, output_path)


def _combine_video_audio_segments(
    video_files: list, audio_files: list, output_path: str
):
    """Combine video and audio segments using FFmpeg."""
    try:
        if not video_files:
            logger.error("No video files to combine")
            return False

        # Create temporary video file first
        video_temp_path = output_path.replace(".mp4", "_video_temp.mp4")

        if not _combine_video_only_segments(video_files, video_temp_path):
            logger.error("Failed to combine video segments")
            return False

        # If we have audio files, combine them and merge with video
        if audio_files:
            audio_temp_path = output_path.replace(".mp4", "_audio_temp.mp4")

            if _combine_video_only_segments(audio_files, audio_temp_path):
                # Merge video and audio
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    video_temp_path,
                    "-i",
                    audio_temp_path,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-shortest",  # Use shortest stream duration
                    output_path,
                ]

                logger.info(f"Merging video and audio: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    for temp_path in (video_temp_path, audio_temp_path):
                        try:
                            os.unlink(temp_path)
                        except OSError:
                            pass
                    logger.info(
                        f"Successfully merged video and audio into: {output_path}"
                    )
                    return True
                else:
                    logger.error(f"Audio/video merge failed: {result.stderr}")
                    try:
                        os.unlink(audio_temp_path)
                    except OSError:
                        pass
                    shutil.move(video_temp_path, output_path)
                    return True
            else:
                logger.warning("Failed to combine audio segments, using video-only")
                shutil.move(video_temp_path, output_path)
                return True
        else:
            # No audio files, just use video
            shutil.move(video_temp_path, output_path)
            logger.info(f"Video-only file created: {output_path}")
            return True

    except Exception as e:
        logger.error(f"Failed to combine video/audio segments: {e}")
        return False


def _combine_video_only_segments(media_files: list, output_path: str):
    """Combine video segments only using FFmpeg concat demuxer."""
    try:
        if not media_files:
            return False

        # For actual TS/media files, try simple concatenation first
        if len(media_files) == 1:
            # Single file, just copy it
            logger.info(f"Single media file, copying to output: {media_files[0]}")
            shutil.copy2(media_files[0], output_path)
            return True

        # Multiple files, use concat demuxer (more reliable for TS files)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as concat_file:
            for media_file in media_files:
                if os.path.exists(media_file):
                    # Use absolute paths and escape for concat demuxer
                    abs_path = os.path.abspath(media_file)
                    concat_file.write(f"file '{abs_path}'\n")
            concat_file_path = concat_file.name

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file_path,
            "-c",
            "copy",
            output_path,
        ]

        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Clean up temp file
        try:
            os.unlink(concat_file_path)
        except OSError:
            pass

        if result.returncode == 0:
            logger.info(
                f"Successfully combined {len(media_files)} segments into: {output_path}"
            )
            return True
        else:
            logger.error(f"FFmpeg failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Failed to combine segments: {e}")
        return False


def _process_byterange_m3u8(
    m3u8_path: str, dest_dir: str, base_url: str, sleep_interval: int
):
    """Process M3U8 playlist that contains byte-range segments.

    Args:
        m3u8_path (str): path to the M3U8 playlist file
        dest_dir (str): directory to save segments
        base_url (str): base URL for resolving relative URLs
        sleep_interval (int): sleep between downloads

    Returns:
        list: paths to downloaded segment files
    """
    segment_files = []

    try:
        with open(m3u8_path, "r", encoding="utf-8") as f:
            playlist_content = f.read()
    except Exception as e:
        logger.error(f"Failed to read M3U8 file {m3u8_path}: {e}")
        return []

    lines = playlist_content.split("\n")
    current_byterange = None
    previous_byterange = None
    previous_segment_url = None
    segment_count = 0

    for i, line in enumerate(lines):
        line = line.strip()

        # Parse EXT-X-BYTERANGE directive
        if line.startswith("#EXT-X-BYTERANGE:"):
            # Format: #EXT-X-BYTERANGE:length@offset or #EXT-X-BYTERANGE:length
            byterange_part = line.split(":", 1)[1]
            if "@" in byterange_part:
                length, offset = byterange_part.split("@")
                current_byterange = (int(length), int(offset))
            else:
                # Only length provided, offset continues from previous segment
                length = int(byterange_part)
                next_uri = lines[i + 1].strip() if i + 1 < len(lines) else ""
                next_url = urllib.parse.urljoin(base_url, next_uri)
                if previous_byterange and next_url == previous_segment_url:
                    prev_length, prev_offset = previous_byterange
                    current_byterange = (length, prev_offset + prev_length)
                else:
                    current_byterange = (length, 0)

        # Parse EXT-X-MAP directive for initialization segment
        elif line.startswith("#EXT-X-MAP:"):
            # Extract URI and optional byterange
            if 'URI="' in line:
                uri_start = line.find('URI="') + 5
                uri_end = line.find('"', uri_start)
                if uri_start > 4 and uri_end > uri_start:
                    map_uri = line[uri_start:uri_end]
                    map_url = urllib.parse.urljoin(base_url, map_uri)

                    # Check for byterange in EXT-X-MAP
                    map_byterange = None
                    if 'BYTERANGE="' in line:
                        br_start = line.find('BYTERANGE="') + 11
                        br_end = line.find('"', br_start)
                        if br_start > 10 and br_end > br_start:
                            br_part = line[br_start:br_end]
                            if "@" in br_part:
                                length, offset = br_part.split("@")
                                map_byterange = (int(length), int(offset))

                    # Download initialization segment
                    init_filename = f"init_{map_uri}"
                    init_path = os.path.join(dest_dir, init_filename)
                    try:
                        _download_byterange_segment(
                            map_url, init_path, map_byterange, sleep_interval
                        )
                        segment_files.append(init_path)
                        logger.info(
                            f"Downloaded initialization segment: {init_filename}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to download initialization segment: {e}")

        # Regular segment URLs
        elif line and not line.startswith("#"):
            # This is a segment URL that should use the current byte range
            if line.startswith("http"):
                segment_url = line
            else:
                segment_url = urllib.parse.urljoin(base_url, line)

            # Download the segment with byte range
            segment_filename = f"video_segment_{segment_count:04d}.ts"
            segment_path = os.path.join(dest_dir, segment_filename)

            try:
                _download_byterange_segment(
                    segment_url, segment_path, current_byterange, sleep_interval
                )
                segment_files.append(segment_path)
                segment_count += 1
                if current_byterange:
                    previous_byterange = current_byterange
                    previous_segment_url = segment_url

                if segment_count % 10 == 0:  # Log progress every 10 segments
                    logger.info(f"Downloaded {segment_count} video segments...")

            except Exception as e:
                logger.error(f"Failed to download segment {segment_count}: {e}")

            # Reset byterange for next segment (will be set by next EXT-X-BYTERANGE if needed)
            current_byterange = None

    logger.info(f"Downloaded {segment_count} total video segments from byterange M3U8")
    return segment_files


def _download_byterange_segment(
    url: str, dest_path: str, byterange: tuple, sleep_interval: int
):
    """Download a segment with byte range request.

    Args:
        url (str): URL to download from
        dest_path (str): destination file path
        byterange (tuple): (length, offset) or None for full file
        sleep_interval (int): sleep between requests
    """
    if os.path.exists(dest_path):
        return  # Already downloaded

    headers = {}
    if byterange:
        length, offset = byterange
        headers["Range"] = f"bytes={offset}-{offset + length - 1}"

    time.sleep(sleep_interval)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Check if the response contains "This content is not available"
        content = response.content
        if b"This content is not available" in content or len(content) < 100:
            logger.warning(f"Content not available for {url}")
            raise requests.exceptions.RequestException("Content not available")

        # Create directory if needed
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        with open(dest_path, "wb") as f:
            f.write(content)

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download byte-range segment from {url}: {e}")
        raise


def download_m3u8_direct_ffmpeg(m3u8_url: str, output_path: str) -> bool:
    """Download M3U8 directly using FFmpeg without processing individual segments.

    This is the optimal approach for downloading HLS streams as FFmpeg handles
    the entire M3U8 protocol natively with better error recovery and performance.

    Args:
        m3u8_url (str): M3U8 playlist URL
        output_path (str): final output file path

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Verify FFmpeg availability
        subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, check=True, timeout=10
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        logger.warning("FFmpeg not available for direct M3U8 download")
        return False

    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # FFmpeg command with protocol whitelist for security
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output files
            "-protocol_whitelist",
            "file,http,https,tcp,tls,crypto",
            "-user_agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "-i",
            m3u8_url,
            "-c",
            "copy",  # Copy streams without re-encoding for speed
            "-bsf:a",
            "aac_adtstoasc",  # Fix AAC stream compatibility if present
            "-f",
            "mp4",  # Force MP4 container format
            output_path,
        ]

        logger.info(f"Downloading M3U8 directly with FFmpeg: {m3u8_url}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for large files
        )

        if result.returncode == 0:
            # Verify output file was created and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully downloaded M3U8 to: {output_path}")
                return True
            else:
                logger.warning("FFmpeg completed but output file is empty or missing")
                return False
        else:
            logger.warning(f"FFmpeg direct download failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg download timed out after 10 minutes")
        return False
    except Exception as e:
        logger.warning(f"Failed to download M3U8 directly: {e}")
        return False
