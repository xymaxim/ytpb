import os
from pathlib import Path

import pytest

from ytpb.merge import merge_segments

from tests.conftest import TEST_DATA_PATH
from tests.helpers import assert_approx_duration, assert_number_of_streams

SEGMENT_BASE_PATH = Path(TEST_DATA_PATH) / "segments"


def setup_function():
    os.environ["YTPB_VP9_ENCODING_SETTINGS"] = (
        "libvpx-vp9 -crf 63 -b:v 0 -deadline realtime -cpu-used 8 -row-mt 1 -s 1x1"
    )


def test_merge_with_default_encoding_settings(run_temp_directory: Path, tmp_path: Path):
    """Test with default video encoding settings."""
    os.environ["YTPB_VP9_ENCODING_SETTINGS"] = ""

    output_stem = tmp_path / "merged"

    merge_segments(
        audio_segment_paths=[SEGMENT_BASE_PATH / "7959120.i140.mp4"],
        video_segment_paths=[SEGMENT_BASE_PATH / "7959120.i244.webm"],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
        cut_at_start=0.5,
    )

    expected_output_path = output_stem.with_suffix(".mkv")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 2)
    assert_approx_duration(expected_output_path, 1.5)

    assert not any(run_temp_directory.iterdir())


def test_merge_without_cleaning_up(run_temp_directory: Path, tmp_path: Path):
    output_stem = tmp_path / "merged"

    merge_segments(
        audio_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i140.mp4",
            SEGMENT_BASE_PATH / "7959121.i140.mp4",
        ],
        video_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i244.webm",
            SEGMENT_BASE_PATH / "7959121.i244.webm",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
        cleanup=False,
    )

    assert any(run_temp_directory.iterdir())


def test_merge_one_audio_and_video_segments_without_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"

    merge_segments(
        audio_segment_paths=[SEGMENT_BASE_PATH / "7959120.i140.mp4"],
        video_segment_paths=[SEGMENT_BASE_PATH / "7959120.i244.webm"],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
    )

    expected_output_path = output_stem.with_suffix(".mkv")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 2)
    assert_approx_duration(expected_output_path, 2.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_one_audio_and_video_segments_with_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"

    merge_segments(
        audio_segment_paths=[SEGMENT_BASE_PATH / "7959120.i140.mp4"],
        video_segment_paths=[SEGMENT_BASE_PATH / "7959120.i244.webm"],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
        cut_at_start=0.5,
        cut_at_end=1.5,
    )

    expected_output_path = output_stem.with_suffix(".mkv")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 2)
    assert_approx_duration(expected_output_path, 1.5)

    assert not any(run_temp_directory.iterdir())


def test_merge_two_audio_and_video_segments_without_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"

    merge_segments(
        audio_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i140.mp4",
            SEGMENT_BASE_PATH / "7959121.i140.mp4",
        ],
        video_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i244.webm",
            SEGMENT_BASE_PATH / "7959121.i244.webm",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
    )

    expected_output_path = output_stem.with_suffix(".mkv")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 2)
    assert_approx_duration(expected_output_path, 4.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_two_audio_and_video_segments_with_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"

    merge_segments(
        audio_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i140.mp4",
            SEGMENT_BASE_PATH / "7959121.i140.mp4",
        ],
        video_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i244.webm",
            SEGMENT_BASE_PATH / "7959121.i244.webm",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
        cut_at_start=0.5,
        cut_at_end=1.5,
    )

    expected_output_path = output_stem.with_suffix(".mkv")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 2)
    assert_approx_duration(expected_output_path, 3.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_three_audio_and_video_segments_without_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"
    merge_segments(
        audio_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i140.mp4",
            SEGMENT_BASE_PATH / "7959121.i140.mp4",
            SEGMENT_BASE_PATH / "7959122.i140.mp4",
        ],
        video_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i244.webm",
            SEGMENT_BASE_PATH / "7959121.i244.webm",
            SEGMENT_BASE_PATH / "7959122.i244.webm",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
    )

    expected_output_path = output_stem.with_suffix(".mkv")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 2)
    assert_approx_duration(expected_output_path, 6.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_three_audio_and_video_segments_with_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"
    merge_segments(
        audio_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i140.mp4",
            SEGMENT_BASE_PATH / "7959121.i140.mp4",
            SEGMENT_BASE_PATH / "7959122.i140.mp4",
        ],
        video_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i244.webm",
            SEGMENT_BASE_PATH / "7959121.i244.webm",
            SEGMENT_BASE_PATH / "7959122.i244.webm",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
        cut_at_start=0.5,
        cut_at_end=1.5,
    )

    expected_output_path = output_stem.with_suffix(".mkv")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 2)
    assert_approx_duration(expected_output_path, 5.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_two_audio_segments_without_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"
    merge_segments(
        audio_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i140.mp4",
            SEGMENT_BASE_PATH / "7959121.i140.mp4",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
    )

    expected_output_path = output_stem.with_suffix(".mp4")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 1)
    assert_approx_duration(expected_output_path, 4.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_two_audio_segments_with_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"
    merge_segments(
        audio_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i140.mp4",
            SEGMENT_BASE_PATH / "7959121.i140.mp4",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
        cut_at_start=0.5,
        cut_at_end=1.5,
    )

    expected_output_path = output_stem.with_suffix(".mp4")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 1)
    assert_approx_duration(expected_output_path, 3.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_two_video_segments_without_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"
    merge_segments(
        video_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i244.webm",
            SEGMENT_BASE_PATH / "7959121.i244.webm",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
    )

    expected_output_path = output_stem.with_suffix(".webm")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 1)
    assert_approx_duration(expected_output_path, 4.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_two_video_segments_with_cutting(
    run_temp_directory: Path, tmp_path: Path
):
    output_stem = tmp_path / "merged"
    merge_segments(
        video_segment_paths=[
            SEGMENT_BASE_PATH / "7959120.i244.webm",
            SEGMENT_BASE_PATH / "7959121.i244.webm",
        ],
        output_stem=output_stem,
        temp_directory=run_temp_directory,
        cut_at_start=0.5,
        cut_at_end=1.5,
    )

    expected_output_path = output_stem.with_suffix(".webm")
    assert os.path.exists(expected_output_path)

    assert_number_of_streams(expected_output_path, 1)
    assert_approx_duration(expected_output_path, 3.0)

    assert not any(run_temp_directory.iterdir())


def test_merge_unequal_number_of_audio_and_video_segments(
    run_temp_directory: Path, tmp_path: Path
):
    with pytest.raises(ValueError) as e:
        merge_segments(
            audio_segment_paths=[
                SEGMENT_BASE_PATH / "7959120.i140.mp4",
                SEGMENT_BASE_PATH / "7959121.i140.mp4",
            ],
            video_segment_paths=[
                SEGMENT_BASE_PATH / "7959120.i244.webm",
            ],
            output_stem=tmp_path / "merged",
            temp_directory=run_temp_directory,
        )

    assert "of equal size" in str(e.value)
