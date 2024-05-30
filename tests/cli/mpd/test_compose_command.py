import os
import platform
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

import platformdirs
import pytest
import toml
from freezegun import freeze_time


@pytest.mark.parametrize(
    "audio_formats,video_formats",
    [
        ("itag eq 140", "itag eq 243 or itag eq 244"),
        ("itag eq 140", "none"),
        ("none", "itag eq 243 or itag eq 244"),
    ],
)
@pytest.mark.expect_suffix(platform.system())
def test_compose_mpd(
    audio_formats,
    video_formats,
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    tmp_path: Path,
    expected_out,
) -> None:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        r"https://.+\.googlevideo\.com/videoplayback/.+/sq/\w+"
    )
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "mpd",
                "compose",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                audio_formats,
                "-vf",
                video_formats,
                stream_url,
            ],
        )
    assert result.exit_code == 0
    assert result.output == expected_out


@pytest.mark.expect_suffix(platform.system())
@freeze_time("2023-03-26T00:00:00+00:00")
def test_compose_mpd_with_no_streams(
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    video_id: str,
    audio_base_url: str,
    video_base_url: str,
    tmp_path: Path,
    expected_out,
) -> None:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "mpd",
                "compose",
                "--no-cache",
                "--interval",
                "2023-03-25T23:33:55+00:00/2023-03-25T23:33:58+00:00",
                "-af",
                "itag eq 0",
                "-vf",
                "itag eq 0",
                stream_url,
            ],
        )

    assert result.exit_code == 1
    assert result.output == expected_out


def test_compose_mpd_using_yt_dlp(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    video_id: str,
    audio_base_url: str,
    video_base_url: str,
    tmp_path: Path,
) -> None:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    with patch("ytpb.cli.common.YoutubeDLInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "mpd",
                "compose",
                "--yt-dlp",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "",
                stream_url,
            ],
        )

    assert result.exit_code == 0


def test_with_default_config(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        r"https://.+\.googlevideo\.com/videoplayback/.+/sq/\w+"
    )

    config = {
        "options": {
            "mpd": {
                "compose": {
                    "audio-formats": "NON-SENS",
                }
            }
        }
    }
    config_path = platformdirs.user_config_path() / "ytpb/config.toml"
    config_path.parent.mkdir(parents=True)
    with config_path.open("w", encoding="utf-8") as f:
        toml.dump(config, f)

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "mpd",
                "compose",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "itag eq 243",
                stream_url,
            ],
        )

    # Then:
    print(result.output)
    assert result.exit_code == 0


def test_compose_to_user_output_path(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    tmp_path: Path,
):
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        r"https://.+\.googlevideo\.com/videoplayback/.+/sq/\w+"
    )
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "mpd",
                "compose",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "itag eq 243",
                "-o",
                "manifest.xml",
                stream_url,
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    assert os.path.exists("manifest.xml")


def test_compose_to_user_template_output_path(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    video_id: str,
    tmp_path: Path,
):
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        r"https://.+\.googlevideo\.com/videoplayback/.+/sq/\w+"
    )
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "mpd",
                "compose",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "itag eq 243",
                "-o",
                "{{ id }}.xml",
                stream_url,
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    assert os.path.exists(f"{video_id}.xml")
