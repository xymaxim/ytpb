import glob
import os
import pickle
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

import av
import click

import platformdirs
import pytest
import responses
import toml

from freezegun import freeze_time

from ytpb.cli.config import DEFAULT_CONFIG
from ytpb.playback import RewindInterval, RewindMoment

from tests.conftest import TEST_DATA_PATH
from tests.helpers import assert_approx_duration


@pytest.mark.parametrize(
    "interval,output_subpath",
    [
        # Segments and corresponding ingestion start dates:
        #             7959120       21       22
        #                  |        |        |
        # 2023-03-25T23:33:54.491Z  56.490   58.492
        ("7959120/7959121", "233354+00.mp4"),
        ("7959120/2023-03-25T23:33:57+00", "233354+00.mp4"),
        ("7959120/PT3S", "233354+00.mp4"),
        ("2023-03-25T23:33:55+00/2023-03-25T23:33:57+00", "233355+00.mp4"),
        ("2023-03-25T23:33:55+00/PT3S", "233355+00.mp4"),
        ("2023-03-25T23:33:55+00/7959121", "233355+00.mp4"),
        ("PT3S/7959121", "233355+00.mp4"),
        ("PT3S/2023-03-25T23:33:58+00", "233355+00.mp4"),
    ],
)
@pytest.mark.expect_suffix(platform.system())
@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_within_interval(
    interval: str,
    output_subpath: str,
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
    expected_out,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                interval,
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    assert result.output == expected_out
    assert glob.glob(str(tmp_path / f"*{output_subpath}"))


@freeze_time("2023-03-26T00:00:00+00:00")
def test_providing_start_and_end_equals_now(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:

    # In this test the reference segment refers to a segment (7959122) next to
    # the end one (7959121).
    add_responses_callback_for_reference_base_url(7959122)
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/now",  # 'now' should refer to segment 7959121
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    expected_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00.mp4"
    assert os.path.exists(expected_path)
    assert_approx_duration(expected_path, 4.0)


@pytest.mark.parametrize(
    "interval",
    [
        "7959120/7959200",
        "2023-03-25T23:33:55+00/2023-03-26T00+00",
        "2023-03-25T23:33:55+00/PT1H",
        "2023-03-25T23:33:55+00/7959200",
        "PT3S/2023-03-25T23:33:58+00",
        "PT3S/7959121",
        "7959120/..",
    ],
)
@freeze_time("2023-03-26T00:00:00+00:00")
def test_preview_start_option(
    interval: str,
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, "sq/7959203"),
        urljoin(audio_base_url, "sq/7959120"),
        urljoin(audio_base_url, "sq/7959121"),
        urljoin(audio_base_url, "sq/7959122"),
    )

    DEFAULT_CONFIG["general"]["preview_duration"] = 4

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                interval,
                "--preview-start",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    if ".." not in interval:
        assert "~ Preview mode enabled, interval end is ignored." in result.output
    assert os.path.exists(tmp_path / "Webcam-Zurich-HB_kHwmzef842g_preview.mp4")


@pytest.mark.parametrize(
    "interval",
    [
        "7959000/7959122",
        "2023-03-24T00+00/2023-03-25T23:33:58.500+00",
        "PT1H/2023-03-25T23:33:58.500+00",
        "7959000/2023-03-25T23:33:58.500+00",
        "2023-03-25T23:33:55.500+00/PT3S",
        "7959121/PT3S",
    ],
)
@freeze_time("2023-03-26T00:00:00+00:00")
def test_preview_end_option(
    interval: str,
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, "sq/7959203"),
        urljoin(audio_base_url, "sq/7959120"),
        urljoin(audio_base_url, "sq/7959121"),
        urljoin(audio_base_url, "sq/7959122"),
    )

    DEFAULT_CONFIG["general"]["preview_duration"] = 4

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                interval,
                "--preview-end",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert "~ Preview mode enabled, interval start is ignored." in result.output
    assert os.path.exists(tmp_path / "Webcam-Zurich-HB_kHwmzef842g_preview.mp4")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_preview_and_output_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, "sq/7959203"),
        urljoin(audio_base_url, "sq/7959120"),
        urljoin(audio_base_url, "sq/7959121"),
        urljoin(audio_base_url, "sq/7959122"),
    )

    DEFAULT_CONFIG["general"]["preview_duration"] = 4

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959200",
                "--preview-start",
                "--output",
                "preview",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(tmp_path / "preview.mp4")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_save_segments_to_temp_in_preview_mode(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    run_temp_directory: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # We only have three test segments of 2 second duration.
    DEFAULT_CONFIG["general"]["preview_duration"] = 4

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--keep-temp",
                "--interval",
                "7959120/7959122",
                "--preview-start",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
            catch_exceptions=False,
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(run_temp_directory / "7959120.i140.mp4")
    assert os.path.exists(run_temp_directory / "7959121.i140.mp4")


@pytest.mark.parametrize(
    "audio_format,video_format",
    [("itag eq 140", "itag eq 244"), ("itag eq 140", "none"), ("none", "itag eq 244")],
)
@pytest.mark.expect_suffix(platform.system())
@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_audio_and_or_video(
    audio_format: str | None,
    video_format: str | None,
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    run_temp_directory: Path,
    expected_out,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
        urljoin(video_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                audio_format,
                "-vf",
                video_format,
                stream_url,
            ],
            catch_exceptions=False,
        )

    # Then:
    assert result.exit_code == 0
    assert expected_out == result.output


@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_to_custom_absolute_path(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "-o",
                tmp_path / "test" / "merged",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(tmp_path / "test" / "merged.mp4")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_to_user_relative_path(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "-o",
                "test/merged",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(tmp_path / "test" / "merged.mp4")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_to_user_template_output_path(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "-o",
                "{{ id }}",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert "kHwmzef842g.mp4" == str(next(tmp_path.glob("*.mp4")).name)


@freeze_time("2023-03-26T00:00:00+00:00")
def test_keep_temp_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--keep-temp",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(
        tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00.mp4"
    )
    assert os.path.exists(run_temp_directory / "7959120.i140.mp4")


@pytest.mark.expect_suffix(platform.system())
@freeze_time("2023-03-26T00:00:00+00:00")
def test_no_merge_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
    expected_out,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--no-merge",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert expected_out == result.output
    assert not os.path.exists(
        tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00.mp4"
    )
    assert not os.path.exists(run_temp_directory)


@pytest.mark.expect_suffix(platform.system())
@freeze_time("2023-03-26T00:00:00+00:00")
def test_dry_run_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
    expected_out,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--dry-run",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert result.output == expected_out
    assert not os.path.exists(
        tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233355+00.mp4"
    )
    assert not os.path.exists(run_temp_directory)


@pytest.mark.expect_suffix(platform.system())
@freeze_time("2023-03-26T00:00:00+00:00")
def test_cut_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
    expected_out,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "2023-03-25T23:33:55+00/2023-03-25T23:33:58+00",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--cut",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert result.output == expected_out
    expected_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233355+00.mp4"
    assert os.path.exists(expected_path)
    assert_approx_duration(expected_path, 3.0, abs=4.2e-2)


@freeze_time("2023-09-28T17:00:00+00:00")
def test_from_cache(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    create_cache_file: None,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
):
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert "Cache for the video doesn't exist" not in result.output


@freeze_time("2023-03-26T00:00:00+00:00")
def test_from_empty_cache(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
):
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    expected_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00.mp4"
    assert os.path.exists(expected_path)


@pytest.mark.parametrize(
    "audio_format,video_format",
    [
        ("format eq mp4", "quality gt 360p"),
        ("format eq mp4", "itag eq 244"),
        ("itag eq 140", "quality gt 360p"),
        ("format eq mp4", "none"),
        ("none", "quality gt 360p"),
    ],
)
@freeze_time("2023-03-26T00:00:00+00:00")
def test_ambiguous_format_specs(
    audio_format: str,
    video_format: str,
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
    # expected_out,
) -> None:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                audio_format,
                "-vf",
                video_format,
                stream_url,
            ],
        )

    assert result.exit_code == 1
    # assert result.output == expected_out


@freeze_time("2023-03-26T00:00:00+00:00")
def test_yt_dlp_option(
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
                "--no-config",
                "download",
                "--yt-dlp",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    assert result.exit_code == 0
    expected_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00.mp4"
    assert os.path.exists(expected_path)


@freeze_time("2023-03-26T00:00:00+00:00")
def test_with_default_config_file(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    """Tests loading of a configuration from the default path. Here two things
    are tested:

    1. The default values for options are loaded from the configuration file.
    2. The command options hold priority over the configuration.
    """

    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    config = {
        "options": {
            "download": {
                "audio-format": "NON-SENS",
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
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0


@freeze_time("2023-03-26T00:00:00+00:00")
def test_with_config_via_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    """Tests the --config option. The default config file should be ignored."""

    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    default_config = {
        "options": {
            "download": {
                "audio-format": "NON-SENS",
            }
        }
    }
    default_config_path = platformdirs.user_config_path() / "ytpb/config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w", encoding="utf-8") as f:
        toml.dump(default_config, f)

    test_config = {
        "options": {
            "download": {
                "audio-format": "itag eq 140",
            }
        }
    }
    test_config_path = platformdirs.user_config_path() / "test-config.toml"
    with test_config_path.open("w", encoding="utf-8") as f:
        toml.dump(test_config, f)

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--config",
                test_config_path,
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0


@freeze_time("2023-03-26T00:00:00+00:00")
def test_with_non_existent_config_file_via_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    default_config = {
        "options": {
            "download": {
                "audio_format": "NON-SENS",
            }
        }
    }
    default_config_path = platformdirs.user_config_path() / "ytpb" / "config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w", encoding="utf-8") as f:
        toml.dump(default_config, f)

    test_config_path = platformdirs.user_config_path() / "ytpb" / "test-config.toml"

    # Then:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        with pytest.raises(click.FileError) as exc_info:
            ytpb_cli_invoke(
                [
                    "--config",
                    test_config_path,
                    "download",
                    "--no-cache",
                    "--interval",
                    "7959120/7959121",
                    "-vf",
                    "none",
                    stream_url,
                ],
                catch_exceptions=False,
                standalone_mode=False,
            )


@freeze_time("2023-03-26T00:00:00+00:00")
def test_no_config_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    """Tests the --no-config option. Any configuration files should be ignored.

    In this test, the required -i/--interval option is intentionally
    omitted. Instead, it's defined in the created config file. Since the file
    should be ignored, a click.MissingParameter exception should be raised.
    """

    # Given:
    default_config = {
        "options": {
            "download": {
                "interval": "7959120/7959121",
            }
        }
    }
    default_config_path = platformdirs.user_config_path() / "ytpb/config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w", encoding="utf-8") as f:
        toml.dump(default_config, f)

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        with pytest.raises(click.MissingParameter) as exc_info:
            ytpb_cli_invoke(
                [
                    "--no-config",
                    "download",
                    "--no-cache",
                    # (The required -i/--interval option is intentionally omitted.)
                    "-af",
                    "itag eq 140",
                    "-vf",
                    "none",
                    stream_url,
                ],
                catch_exceptions=False,
                standalone_mode=False,
            )

    # Then:
    assert "Missing parameter: interval" in str(exc_info.value)


@freeze_time("2023-03-26T00:00:00+00:00")
def test_conflicting_config_and_no_config_options(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    default_config = {
        "options": {
            "download": {
                "audio_format": "NON-SENS",
            }
        }
    }
    default_config_path = platformdirs.user_config_path() / "ytpb/config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w", encoding="utf-8") as f:
        toml.dump(default_config, f)

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        with pytest.raises(click.UsageError) as exc_info:
            ytpb_cli_invoke(
                [
                    "--no-config",
                    "--config",
                    default_config_path,
                    "download",
                    "--no-cache",
                    "-vf",
                    "none",
                    stream_url,
                ],
                catch_exceptions=False,
                standalone_mode=False,
            )

    # Then:
    assert "Conflicting --config and --no-config options given" == str(exc_info.value)


@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_via_stream_id(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    run_temp_directory: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
        )

    # Then:
    assert result.exit_code == 0


@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_via_invalid_stream_id(
    ytpb_cli_invoke: Callable,
    run_temp_directory: Path,
) -> None:
    with pytest.raises(click.BadParameter):
        ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "INVALID",
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )


@freeze_time("2023-03-26T00:00:00+00:00")
def test_custom_alias(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    custom_config = {"general": {"aliases": {"custom": "itag eq 140"}}}
    config_path = platformdirs.user_config_path() / "ytpb/config.toml"
    config_path.parent.mkdir(parents=True)
    with config_path.open("w", encoding="utf-8") as f:
        toml.dump(custom_config, f)

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--config",
                config_path,
                "download",
                "--dry-run",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-vf",
                "none",
                "-af",
                "@custom",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "audio_format,video_format",
    [
        ("itag eq 140", "itag eq 0"),
        ("itag eq 0", "itag eq 244"),
    ],
)
@freeze_time("2023-03-26T00:00:00+00:00")
def test_empty_representations(
    audio_format: str,
    video_format: str,
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--dry-run",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                audio_format,
                "-vf",
                video_format,
                stream_url,
            ],
        )

    assert result.exit_code == 1
    assert "error: No streams found matching" in result.output


@freeze_time("2023-03-26T00:00:00+00:00")
def test_quiet_option(
    add_responses_callback_for_reference_base_url,
    add_responses_callback_for_segment_urls,
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "--quiet",
                "download",
                "--dry-run",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert result.output == ""


@freeze_time("2023-03-26T00:00:00+00:00")
def test_report_option(
    add_responses_callback_for_reference_base_url,
    add_responses_callback_for_segment_urls,
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "--report",
                "download",
                "--dry-run",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(tmp_path / "ytpb-20230326-000000.log")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_dump_base_urls_option(
    add_responses_callback_for_segment_urls,
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    tmp_path: Path,
) -> None:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "itag eq 244",
                "--dump-base-urls",
                stream_url,
            ],
        )

    assert result.exit_code == 0
    assert result.output == f"{audio_base_url}\n{video_base_url}\n"


@freeze_time("2023-03-26T00:00:00+00:00")
def test_dump_segment_urls_option(
    add_responses_callback_for_reference_base_url,
    add_responses_callback_for_segment_urls,
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    tmp_path: Path,
) -> None:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
        urljoin(video_base_url, r"sq/\w+"),
    )

    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "itag eq 244",
                "--dump-segment-urls",
                stream_url,
            ],
        )

    assert result.exit_code == 0
    assert result.output == (
        f"{audio_base_url.rstrip('/')}/sq/[7959120-7959121]\n"
        f"{video_base_url.rstrip('/')}/sq/[7959120-7959121]\n"
    )


@freeze_time("2023-03-26T00:00:00+00:00")
def test_dump_rewind_interval_option(
    add_responses_callback_for_reference_base_url,
    add_responses_callback_for_segment_urls,
    ytpb_cli_invoke: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--dump-rewind-interval",
                stream_url,
            ],
        )

    assert result.exit_code == 0
    assert result.output == "7959120-7959121\n"


@freeze_time("2023-03-26T00:00:00+00:00")
def test_metadata_tags_without_cutting_and_iso_dates(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "2023-03-25T23:33:55+00/2023-03-25T23:33:57+00",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    output_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233355+00.mp4"
    with av.open(output_path) as container:
        metadata_tags = container.metadata

    assert metadata_tags["title"] == "Webcam Zürich HB"
    assert metadata_tags["author"] == "David Gubler"
    assert metadata_tags["comment"] == stream_url
    assert metadata_tags["input_start_date"] == "2023-03-25T23:33:55.000000Z"
    assert metadata_tags["input_end_date"] == "2023-03-25T23:33:57.000000Z"
    assert metadata_tags["actual_start_date"] == "2023-03-25T23:33:54.491176Z"
    assert metadata_tags["actual_end_date"] == "2023-03-25T23:33:58.486826Z"
    assert metadata_tags["start_segment"] == "7959120"
    assert metadata_tags["end_segment"] == "7959121"


@freeze_time("2023-03-26T00:00:00+00:00")
def test_metadata_tags_with_cutting_and_iso_dates(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--cut",
                "--interval",
                "2023-03-25T23:33:55+00/2023-03-25T23:33:57+00",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    output_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233355+00.mp4"
    with av.open(output_path) as container:
        metadata_tags = container.metadata

    assert metadata_tags["title"] == "Webcam Zürich HB"
    assert metadata_tags["author"] == "David Gubler"
    assert metadata_tags["comment"] == stream_url
    assert metadata_tags["input_start_date"] == "2023-03-25T23:33:55.000000Z"
    assert metadata_tags["input_end_date"] == "2023-03-25T23:33:57.000000Z"
    assert metadata_tags["actual_start_date"] == "2023-03-25T23:33:55.000000Z"
    assert metadata_tags["actual_end_date"] == "2023-03-25T23:33:57.000000Z"
    assert metadata_tags["start_segment"] == "7959120"
    assert metadata_tags["end_segment"] == "7959121"


@freeze_time("2023-03-26T00:00:00+00:00")
def test_metadata_tags_without_cutting_and_unix_timestamps(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    custom_config = {
        "output": {
            "metadata": {
                "dates": "unix",
            }
        }
    }
    config_path = platformdirs.user_config_path() / "ytpb/config.toml"
    config_path.parent.mkdir(parents=True)
    with config_path.open("w", encoding="utf-8") as f:
        toml.dump(custom_config, f)

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "download",
                "--no-cache",
                "--interval",
                "2023-03-25T23:33:55+00/2023-03-25T23:33:57+00",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    output_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233355+00.mp4"
    with av.open(output_path) as container:
        metadata_tags = container.metadata

    assert metadata_tags["title"] == "Webcam Zürich HB"
    assert metadata_tags["author"] == "David Gubler"
    assert metadata_tags["comment"] == stream_url
    assert metadata_tags["input_start_date"] == "1679787235.000000"
    assert metadata_tags["input_end_date"] == "1679787237.000000"
    assert metadata_tags["actual_start_date"] == "1679787234.491176"
    assert metadata_tags["actual_end_date"] == "1679787238.486826"
    assert metadata_tags["start_segment"] == "7959120"
    assert metadata_tags["end_segment"] == "7959121"


@freeze_time("2023-03-26T00:00:00+00:00")
def test_resume_downloading(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    resume_file_stem = f"{video_id}-7959120-20230325T233359+00-140"
    with open(f"{resume_file_stem}.resume", "wb") as f:
        end_date = datetime.fromisoformat("2023-03-25T23:33:59+00")
        pickle.dump(
            {
                "interval": RewindInterval(
                    start=RewindMoment(
                        date=datetime.fromtimestamp(1679787234.491176, timezone.utc),
                        sequence=7959120,
                        cut_at=0,
                        is_end=False,
                    ),
                    end=RewindMoment(
                        date=end_date,
                        sequence=7959122,
                        cut_at=0,
                        is_end=True,
                    ),
                ),
                "segments_output_directory": Path(f"{resume_file_stem}"),
            },
            f,
        )
    segments_output_directory = tmp_path / f"{resume_file_stem}"
    segments_output_directory.mkdir()
    for segment in (7959120, 7959121):
        shutil.copy(
            TEST_DATA_PATH / f"segments/{segment}.i140.mp4",
            segments_output_directory / f"{segment}.i140.mp4",
        )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/2023-03-25T23:33:59+00",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    assert (
        f"~ Found unfinished download, continue from {resume_file_stem}.resume"
    ) in result.output
    expected_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00.mp4"
    assert os.path.exists(expected_path)
    assert_approx_duration(expected_path, 6)
    assert not os.path.exists(tmp_path / f"{resume_file_stem}")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_keep_segments(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--keep-segments",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    segments_directory = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00"
    assert os.path.exists(segments_directory / "7959120.i140.mp4")
    assert os.path.exists(segments_directory / "7959121.i140.mp4")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_remove_default_segments_output_directory(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    assert not os.path.exists(tmp_path / f"{video_id}-7959120-7959121-140")


@pytest.mark.parametrize("segments_output_dir_option", ["a", "a/b", "./a", "../a/b"])
@freeze_time("2023-03-26T00:00:00+00:00")
def test_remove_created_segments_output_directory(
    segments_output_dir_option: str,
    monkeypatch: pytest.MonkeyPatch,
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    sub_tmp_path = tmp_path / "sub"
    sub_tmp_path.mkdir()
    monkeypatch.chdir(sub_tmp_path)

    segments_output_directory = sub_tmp_path / segments_output_dir_option

    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--segments-output-dir",
                segments_output_dir_option,
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    if len(segments_output_directory.parts) > 1:
        assert not os.path.exists(segments_output_directory)
    else:
        assert not os.path.exists(segments_output_directory.parent)


def test_remove_only_rewound_segments(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    segments_directory = tmp_path / f"{video_id}-7959120-7959121-140"
    segments_directory.mkdir()
    open(segments_directory / "0.i140.mp4", "x")

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(segments_directory / "0.i140.mp4")
    assert not os.path.exists(segments_directory / "7959120.i140.mp4")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_do_not_remove_existing_directory(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    segments_directory = tmp_path / "existing"
    segments_directory.mkdir()

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--segments-output-dir",
                "existing",
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(segments_directory)
    assert not os.path.exists(segments_directory / "7959120.i140.mp4")


@freeze_time("2023-03-26T00:00:00+00:00")
def test_ignore_resume_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--ignore-resume",
                "--interval",
                "7959120/7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0


@freeze_time("2023-03-26T00:00:00+00:00")
def test_ignore_resume_option_after_unfinished_run(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    video_id: str,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    resume_file_stem = f"{video_id}-7959120-7959122-140"
    with open(f"{resume_file_stem}.resume", "wb") as f:
        pickle.dump(
            {
                "interval": RewindInterval(
                    start=RewindMoment(
                        date=datetime.fromtimestamp(1679787234.491176, timezone.utc),
                        sequence=7959120,
                        cut_at=0,
                        is_end=False,
                    ),
                    end=RewindMoment(
                        date=datetime.fromtimestamp(1679787238.491916, timezone.utc),
                        sequence=7959122,
                        cut_at=0,
                        is_end=True,
                    ),
                ),
                "segments_output_directory": Path(f"{resume_file_stem}"),
            },
            f,
        )
    segments_output_directory = tmp_path / f"{resume_file_stem}"
    segments_output_directory.mkdir()
    for segment in (7959120, 7959121):
        shutil.copy(
            TEST_DATA_PATH / f"segments/{segment}.i140.mp4",
            segments_output_directory / f"{segment}.i140.mp4",
        )

    # When:
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--ignore-resume",
                "--segments-output-dir",
                "segments",
                "--keep-segments",
                "--interval",
                "7959120/7959122",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                video_id,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(tmp_path / f"{video_id}-7959120-7959122-140")
    assert os.path.exists(tmp_path / "segments")
