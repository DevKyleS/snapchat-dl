"""Opt-in tests that exercise live public Snapchat media."""

from snapchat_dl.downloader import download_url
from snapchat_dl.snapchat_dl import SnapchatDL


TEAM_SNAPCHAT_SPOTLIGHT_URL = (
    "https://www.snapchat.com/p/8af53eee-e298-40c4-9d6e-af20cf881b61/spotlight/"
    "W7_EDlXWTBiXAEEniNoMPwAAYcGxsYWxldmNtAaFLLqK9AaFLLqKQAAAAAQ"
)


def test_download_live_team_snapchat_spotlight(tmp_path):
    downloader = SnapchatDL(quiet=True, sleep_interval=0)
    stories, publisher, *_ = downloader._web_fetch_story(TEAM_SNAPCHAT_SPOTLIGHT_URL)

    assert publisher["title"] == "Team Snapchat"
    assert stories

    media_url = stories[0]["snapUrls"]["mediaUrl"]
    output_path = tmp_path / "team-snapchat-spotlight.mp4"
    download_url(media_url, str(output_path), sleep_interval=0)

    assert output_path.is_file()
    assert output_path.stat().st_size > 0
