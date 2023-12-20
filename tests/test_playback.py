import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import pytest
import responses

from conftest import TEST_DATA_PATH
from freezegun import freeze_time

from ytpb.exceptions import BaseUrlExpiredError, CachedItemNotFoundError
from ytpb.fetchers import YtpbInfoFetcher
from ytpb.info import YouTubeVideoInfo
from ytpb.playback import Playback, SequenceRange
from ytpb.streams import AudioOrVideoStream


@pytest.mark.parametrize(
    "input_dates",
    [
        # Segments and corresponding ingestion start dates:
        # Segment 7959120: 2023-03-25T23:33:54.491Z,
        # Segment 7959121: 2023-03-25T23:33:56.490Z,
        # Segment 7959122: 2023-03-25T23:33:58.492Z.
        ("2023-03-25T20:33:55-03:00", "2023-03-25T20:33:57-03:00"),
        ("2023-03-25T20:33:55-03", "2023-03-25T20:33:57-03"),
        ("2023-03-25T23:33:55Z", "2023-03-25T23:33:57Z"),
        ("2023-03-25T23:33:55.001Z", "2023-03-25T23:33:57.001Z"),
        ("2023-03-25T23:33:55,001Z", "2023-03-25T23:33:57,001Z"),
        ("20230325T203355-0300", "20230325T203357-0300"),
        ("20230325T203355-03", "20230325T203357-03"),
        ("20230325T233355Z", "20230325T233357Z"),
    ],
)
def test_locate_rewind_range(
    input_dates: tuple[str, str],
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    mocked_responses: responses.RequestsMock,
    stream_url: str,
    active_live_video_info: YouTubeVideoInfo,
    audio_base_url: str,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(urljoin(audio_base_url, r"sq/\w+"))

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()

    sequences = playback.locate_rewind_range(
        datetime.fromisoformat(input_dates[0]),
        datetime.fromisoformat(input_dates[1]),
        itag="140",
    )

    # Then:
    assert sequences == SequenceRange(7959120, 7959121)


def test_download_excerpt_between_sequences_without_merging(
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_segment_urls: Callable,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    run_temp_directory: Path,
) -> None:
    # Given:
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"), urljoin(video_base_url, r"sq/\w+")
    )

    # When:
    playback = Playback(
        stream_url, temp_directory=run_temp_directory, fetcher=fake_info_fetcher
    )
    playback.fetch_and_set_essential()
    _, *output_paths = playback.download_excerpt(
        SequenceRange(7959120, 7959121), "itag eq 140", "itag eq 244", no_merge=True
    )

    # Then:
    assert output_paths == [
        None,
        [
            run_temp_directory / "segments/7959120.i140.mp4",
            run_temp_directory / "segments/7959121.i140.mp4",
        ],
        [
            run_temp_directory / "segments/7959120.i244.webm",
            run_temp_directory / "segments/7959121.i244.webm",
        ],
    ]
    assert os.path.exists(run_temp_directory / "segments/7959120.i140.mp4")
    assert os.path.exists(run_temp_directory / "segments/7959121.i140.mp4")
    assert os.path.exists(run_temp_directory / "segments/7959120.i244.webm")
    assert os.path.exists(run_temp_directory / "segments/7959121.i244.webm")


def test_download_audio_excerpt_between_sequences_without_merging(
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_segment_urls: Callable,
    stream_url: str,
    audio_base_url: str,
    run_temp_directory: Path,
) -> None:
    # Given:
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
    )

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    _, *output_paths = playback.download_excerpt(
        SequenceRange(7959120, 7959121), "itag eq 140", no_merge=True
    )

    # Then:
    assert output_paths == [
        None,
        [
            run_temp_directory / "segments/7959120.i140.mp4",
            run_temp_directory / "segments/7959121.i140.mp4",
        ],
        [],
    ]
    assert os.path.exists(run_temp_directory / "segments/7959120.i140.mp4")
    assert os.path.exists(run_temp_directory / "segments/7959121.i140.mp4")


def test_download_excerpt_between_dates_without_merging(
    fake_info_fetcher: "FakeInfoFetcher",
    mocked_responses: responses.RequestsMock,
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    run_temp_directory: Path,
) -> None:
    # Given:
    add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"), urljoin(video_base_url, r"sq/\w+")
    )

    # When:
    start_date = datetime.fromisoformat("2023-03-25T23:33:55+00:00")
    end_date = datetime.fromisoformat("2023-03-25T23:33:57+00:00")

    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()

    rewind_range = playback.locate_rewind_range(start_date, end_date, itag="140")
    _, *output_paths = playback.download_excerpt(
        rewind_range, "itag eq 140", "itag eq 244", no_merge=True
    )

    # Then:
    assert output_paths == [
        None,
        [
            run_temp_directory / "segments/7959120.i140.mp4",
            run_temp_directory / "segments/7959121.i140.mp4",
        ],
        [
            run_temp_directory / "segments/7959120.i244.webm",
            run_temp_directory / "segments/7959121.i244.webm",
        ],
    ]

    assert os.path.exists(run_temp_directory / "segments/7959120.i140.mp4")
    assert os.path.exists(run_temp_directory / "segments/7959121.i140.mp4")
    assert os.path.exists(run_temp_directory / "segments/7959120.i244.webm")
    assert os.path.exists(run_temp_directory / "segments/7959121.i244.webm")


def test_create_playback_from_url(
    fake_info_fetcher: "FakeInfoFetcher",
    active_live_video_info: YouTubeVideoInfo,
    streams_in_list: list[AudioOrVideoStream],
    stream_url: str,
    audio_base_url: str,
    run_temp_directory,
):
    playback = Playback.from_url(stream_url, fetcher=fake_info_fetcher)
    assert playback.info == active_live_video_info
    assert len(playback.streams) == len(streams_in_list)


@freeze_time("2023-09-28T17:00:00+00:00")
def test_create_playback_from_manifest(
    fake_info_fetcher: "FakeInfoFetcher",
    active_live_video_info: YouTubeVideoInfo,
    streams_in_list: list[AudioOrVideoStream],
    audio_base_url: str,
    run_temp_directory: Path,
):
    playback = Playback.from_manifest(
        TEST_DATA_PATH / "manifest-1695928670.mpd", fetcher=fake_info_fetcher
    )
    assert playback.info == active_live_video_info
    assert len(playback.streams) == len(streams_in_list)


@freeze_time("2123-09-28T17:00:00+00:00")
def test_create_playback_from_expired_manifest():
    with pytest.raises(BaseUrlExpiredError):
        Playback.from_manifest(TEST_DATA_PATH / "manifest-1695928670.mpd")


@freeze_time("2023-09-28T17:00:00+00:00")
def test_create_playback_from_cache(
    create_cache_file: None,
    stream_url: str,
    active_live_video_info: YouTubeVideoInfo,
    streams_in_list: list[AudioOrVideoStream],
):
    playback = Playback.from_cache(stream_url)
    assert playback.info == active_live_video_info
    assert len(playback.streams) == len(streams_in_list)


@freeze_time("2123-09-28T17:00:00+00:00")
def test_create_playback_from_expired_cache(
    active_live_video_info: YouTubeVideoInfo,
    streams_in_list: list[AudioOrVideoStream],
    video_id: str,
    stream_url: str,
    tmp_path: Path,
):
    # Given:
    test_cache_directory = Playback.get_cache_directory()
    test_cache_directory.mkdir(parents=True)

    frozen_time = datetime.fromisoformat("2123-09-28T17:00:00+00:00").timestamp()
    expired_at = int(frozen_time - 10)
    with open(test_cache_directory / f"{expired_at}~{video_id}", "w") as f:
        test_cache = {
            "info": asdict(active_live_video_info),
            "streams": [asdict(stream) for stream in streams_in_list],
        }
        json.dump(test_cache, f)

    # When:
    with pytest.raises(CachedItemNotFoundError):
        Playback.from_cache(stream_url)


def test_create_playback_from_not_found_cache(stream_url: str, tmp_path: Path):
    with pytest.raises(CachedItemNotFoundError):
        Playback.from_cache(stream_url)


def test_type_of_playback_default_fetcher(stream_url: str):
    playback = Playback(stream_url)
    assert isinstance(playback.fetcher, YtpbInfoFetcher)
