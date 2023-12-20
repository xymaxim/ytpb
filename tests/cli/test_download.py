import glob
import os
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

import click

import pytest
import responses

import toml
from freezegun import freeze_time

from utils import assert_approx_duration


@pytest.mark.parametrize(
    "start,end,output_subpath",
    [
        ("2023-03-25T23:33:55+00", "2023-03-25T23:33:58+00", "233355+00.mp4"),
        ("2023-03-25T23:33:55+00", "7959121", "233355+00.mp4"),
        ("7959120", "2023-03-25T23:33:58+00", "233354+00.mp4"),
        ("7959120", "7959121", "233354+00.mp4"),
    ],
)
@freeze_time("2023-03-26T00:00:00+00:00")
def test_providing_start_and_end(
    start: str,
    end: str,
    output_subpath: str,
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                start,
                "-e",
                end,
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "now",  # should refer to segment 7959121
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    expected_path = tmp_path / "kHwmzef842g_20230325T233354+00.mp4"
    assert os.path.exists(expected_path)
    assert_approx_duration(expected_path, 4.0)


@pytest.mark.parametrize(
    "start,duration,output_subpath",
    [
        ("2023-03-25T23:33:55+00", "2s", "233355+00.mp4"),
        ("7959120", "2s", "233354+00.mp4"),
    ],
)
@freeze_time("2023-03-26T00:00:00+00:00")
def test_providing_start_and_duration(
    start: str,
    duration: str,
    output_subpath: str,
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url,
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cut",
                "--no-cache",
                "-s",
                start,
                "-d",
                duration,
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert glob.glob(str(tmp_path / f"*{output_subpath}"))


@freeze_time("2023-03-26T00:00:00+00:00")
def test_providing_end_and_preview(ytpb_cli_invoke: Callable, stream_url: str):
    with pytest.raises(click.UsageError) as exc_info:
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "2023-03-25T23:33:55+00:00",
                "-e",
                "2023-03-25T23:33:58+00:00",
                "-p",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )
    message = "Option '-e' / '--end' is conflicting with '-p' / '--preview'."
    assert message == str(exc_info.value)

    
@freeze_time("2023-03-26T00:00:00+00:00")
def test_providing_no_end_and_duration(ytpb_cli_invoke: Callable, stream_url: str):
    with pytest.raises(click.UsageError):
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "2023-03-25T23:33:55+00:00",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )


@pytest.mark.parametrize(
    "audio_format,video_format",
    [("itag eq 140", "itag eq 244"), ("itag eq 140", "none"), ("none", "itag eq 244")],
)
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--no-cut",
                "-s",
                "7959120",
                "-e",
                "7959121",
                "-af",
                audio_format,
                "-vf",
                video_format,
                "--no-cleanup",
                stream_url,
            ],
            catch_exceptions=False,
        )

    # Then:
    assert result.exit_code == 0
    expected = expected_out._pattern_filename.read_text()
    expected = expected.replace("{TEMP_DIRECTORY}", str(run_temp_directory))
    assert result.output == expected


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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
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
def test_download_to_custom_relative_path(
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
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


@pytest.mark.parametrize(
    "output_path,expected",
    [
        (
            "<title>_<input_start_date>_<duration>",
            "Webcam-Zurich-HB_20230325T233354+00_PT4S.mp4",
        ),
    ],
)
@freeze_time("2023-03-26T00:00:00+00:00")
def test_download_to_template_output_path(
    output_path: str,
    expected: str,
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "-o",
                output_path,
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert expected == str(next(tmp_path.glob("*.mp4")).name)


@freeze_time("2023-03-26T00:00:00+00:00")
def test_no_cleanup_option(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--no-cleanup",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    assert os.path.exists(tmp_path / "kHwmzef842g_20230325T233354+00.mp4")
    assert os.path.exists(run_temp_directory / "7959120.i140.mp4")

    
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
    """The expected output file for this test contains a template variable, and
    needs to be updated manually."""

    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
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
    assert not os.path.exists(tmp_path / "kHwmzef842g_20230325T233354+00.mp4")
    assert os.path.exists(run_temp_directory / "7959120.i140.mp4")

    expected = expected_out._pattern_filename.read_text()
    expected = expected.replace("{SAVED_TO}", str(run_temp_directory / "segments"))
    expected = expected.replace("{TEMP_DIRECTORY}", str(run_temp_directory))
    assert result.output == expected


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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
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
    assert not os.path.exists(tmp_path / "kHwmzef842g_20230325T233355+00.mp4")
    assert not os.path.exists(run_temp_directory)


@freeze_time("2023-03-26T00:00:00+00:00")
def test_no_cut_option(
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "2023-03-25T23:33:55+00:00",
                "-e",
                "2023-03-25T23:33:58+00:00",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "--no-cut",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    expected_path = tmp_path / "kHwmzef842g_20230325T233355+00.mp4"
    assert os.path.exists(expected_path)
    assert_approx_duration(expected_path, 4.0)

    assert result.output == expected_out


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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cut",
                "-s",
                "7959120",
                "-e",
                "7959121",
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cut",
                "-s",
                "7959120",
                "-e",
                "7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    # Then:
    assert result.exit_code == 0
    expected_path = tmp_path / "kHwmzef842g_20230325T233354+00.mp4"
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cut",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
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

    with patch("ytpb.cli.commands.download.YoutubeDLInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--yt-dlp",
                "--no-cut",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                stream_url,
            ],
        )

    assert result.exit_code == 0
    expected_path = tmp_path / "kHwmzef842g_20230325T233354+00.mp4"
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
                "end": "2023-03-25T23:33:58+00",
                "audio_format": "NON-SENS",
            }
        }
    }
    config_path = Path(os.getenv("XDG_CONFIG_HOME")) / "ytpb/config.toml"
    config_path.parent.mkdir(parents=True)
    with config_path.open("w") as f:
        toml.dump(config, f)

    # When:
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "download",
                "--no-cache",
                "-s",
                "2023-03-25T23:33:55+00",
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
                "audio_format": "NON-SENS",
            }
        }
    }
    default_config_path = Path(os.getenv("XDG_CONFIG_HOME")) / "ytpb/config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w") as f:
        toml.dump(default_config, f)

    test_config = {
        "options": {
            "download": {
                "audio_format": "itag eq 140",
            }
        }
    }
    test_config_path = Path(os.getenv("XDG_CONFIG_HOME")) / "test-config.toml"
    with test_config_path.open("w") as f:
        toml.dump(test_config, f)

    # When:
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--config",
                test_config_path,
                "download",
                "--no-cache",
                "-s",
                "2023-03-25T23:33:55+00",
                "-e",
                "2023-03-25T23:33:58+00",
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
    default_config_path = Path(os.getenv("XDG_CONFIG_HOME")) / "ytpb/config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w") as f:
        toml.dump(default_config, f)

    test_config_path = Path(os.getenv("XDG_CONFIG_HOME")) / "test-config.toml"

    # When:
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        with pytest.raises(click.FileError) as exc_info:
            result = ytpb_cli_invoke(
                [
                    "--config",
                    test_config_path,
                    "download",
                    "--no-cache",
                    "-s",
                    "2023-03-25T23:33:55+00",
                    "-e",
                    "2023-03-25T23:33:58+00",
                    "-vf",
                    "none",
                    stream_url,
                ],
                catch_exceptions=False,
                standalone_mode=False,
            )

    assert str(test_config_path) in str(exc_info)


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
    """Tests the --no-config option. Any configuration files should be ignored."""

    # Given:
    default_config = {
        "options": {
            "download": {
                "start": "NON-SENS",
            }
        }
    }
    default_config_path = Path(os.getenv("XDG_CONFIG_HOME")) / "ytpb/config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w") as f:
        toml.dump(default_config, f)

    # When:
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        with pytest.raises(click.MissingParameter) as exc_info:
            result = ytpb_cli_invoke(
                [
                    "--no-config",
                    "download",
                    "--no-cache",
                    # (The -s/--start option is intentionally omitted.)
                    "-e",
                    "2023-03-25T23:33:58+00",
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
    assert "Missing parameter: start" in str(exc_info.value)


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
                "start": "NON-SENS",
            }
        }
    }
    default_config_path = Path(os.getenv("XDG_CONFIG_HOME")) / "ytpb/config.toml"
    default_config_path.parent.mkdir(parents=True)
    with default_config_path.open("w") as f:
        toml.dump(default_config, f)

    # When:
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        with pytest.raises(click.UsageError) as exc_info:
            result = ytpb_cli_invoke(
                [
                    "--no-config",
                    "--config",
                    default_config_path,
                    "download",
                    "--no-cache",
                    # (The -s/--start option is intentionally omitted).
                    "-e",
                    "2023-03-25T23:33:58+00",
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
    with patch("ytpb.cli.commands.download.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "--no-cut",
                "-s",
                "7959120",
                "-e",
                "7959121",
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
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "download",
                "--no-cache",
                "-s",
                "7959120",
                "-e",
                "7959121",
                "-af",
                "itag eq 140",
                "-vf",
                "none",
                "INVALID",
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )
