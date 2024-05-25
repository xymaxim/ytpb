import io
import os
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

import av
import click
import pytest

from freezegun import freeze_time
from PIL import Image

from tests.conftest import TEST_DATA_PATH

IMAGE_SAVE_SETTINGS = {"format": "jpeg", "quality": 80}


def assert_two_images(
    actual_image_path: Path,
    segment_path: Path,
    expected_frame: int,
    save_settings: dict = IMAGE_SAVE_SETTINGS,
):
    def extract_nth_frame_image(segment_path: Path, n: int) -> Image:
        with av.open(str(segment_path)) as container:
            stream = container.streams.video[0]
            for i, frame in enumerate(container.decode(stream)):
                if i == n:
                    break
        assert frame
        return frame.to_image()

    expected_image = extract_nth_frame_image(segment_path, expected_frame)
    expected_buffer = io.BytesIO()
    expected_image.save(expected_buffer, **save_settings)

    expected_image_saved = Image.open(expected_buffer)
    actual_image = Image.open(actual_image_path)

    assert expected_image_saved.tobytes() == actual_image.tobytes()


@freeze_time("2023-03-26T00:00:00+00:00")
def test_capture_by_sequence_number(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    video_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
) -> None:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(video_base_url, r"sq/\w+"),
    )

    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "capture",
                "frame",
                "--no-cache",
                "--moment",
                "7959120",
                "-vf",
                "itag eq 244",
                stream_url,
            ],
        )

    assert result.exit_code == 0
    actual_image_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233354+00.jpg"
    assert os.path.exists(actual_image_path)

    segment_path = TEST_DATA_PATH / "segments" / "7959120.i244.webm"
    assert_two_images(actual_image_path, segment_path, expected_frame=0)


@freeze_time("2023-03-26T00:00:00+00:00")
def test_capture_by_date(
    ytpb_cli_invoke: Callable,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    fake_info_fetcher: MagicMock,
    stream_url: str,
    video_base_url: str,
    tmp_path: Path,
    run_temp_directory: Path,
) -> None:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(video_base_url, r"sq/\w+"),
    )
    with patch("ytpb.cli.common.YtpbInfoFetcher") as mock_fetcher:
        mock_fetcher.return_value = fake_info_fetcher
        result = ytpb_cli_invoke(
            [
                "--no-config",
                "capture",
                "frame",
                "--no-cache",
                "--moment",
                "2023-03-25T23:33:55+00",
                "-vf",
                "itag eq 244",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )
    assert result.exit_code == 0
    actual_image_path = tmp_path / "Webcam-Zurich-HB_kHwmzef842g_20230325T233355+00.jpg"
    assert os.path.exists(actual_image_path)

    segment_path = TEST_DATA_PATH / "segments" / "7959120.i244.webm"
    assert_two_images(actual_image_path, segment_path, expected_frame=15)


def test_unsupported_output_extension(
    ytpb_cli_invoke: Callable,
    stream_url: str,
) -> None:
    with pytest.raises(click.BadParameter) as exc_info:
        ytpb_cli_invoke(
            [
                "--no-config",
                "capture",
                "frame",
                "--moment",
                "2023-03-25T23:33:55+00",
                "--output",
                "test.unsupported",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )
    assert "Format '.unsupported' is not supported" in str(exc_info)


def test_not_provided_output_extension(
    ytpb_cli_invoke: Callable,
    stream_url: str,
) -> None:
    with pytest.raises(click.BadParameter) as exc_info:
        ytpb_cli_invoke(
            [
                "--no-config",
                "capture",
                "frame",
                "--moment",
                "2023-03-25T23:33:55+00",
                "--output",
                "test",
                stream_url,
            ],
            catch_exceptions=False,
            standalone_mode=False,
        )
    assert "Image extension must be provided" in str(exc_info)
