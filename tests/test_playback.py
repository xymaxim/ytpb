"""This module contains test cases for the Playback class.

Here are segments and corresponding ingestion start dates and timestamps
used in the tests:
             7959120       21       22
                  |        |        |
 2023-03-25T23:33:54.491Z  56.490Z  58.492Z
                  1679787234.491176
                           1679787236.489910
                                    1679787238.491916
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import pytest
import responses

from freezegun import freeze_time

from ytpb.errors import (
    BaseUrlExpiredError,
    CachedItemNotFoundError,
    SequenceLocatingError,
)
from ytpb.fetchers import YtpbInfoFetcher
from ytpb.info import YouTubeVideoInfo
from ytpb.playback import Playback, RewindInterval, RewindMoment
from ytpb.streams import AudioOrVideoStream
from ytpb.types import RelativeSegmentSequence, SegmentSequence

from .conftest import TEST_DATA_PATH


@pytest.fixture
def fake_stream(audio_base_url: str) -> "FakeStream":
    @dataclass
    class FakeStream:
        base_url: str

    return FakeStream(audio_base_url)


class TestLocateMoment:
    @pytest.fixture(autouse=True)
    def setup_method(
        self,
        fake_info_fetcher: "FakeInfoFetcher",
        add_responses_callback_for_segment_urls: Callable,
        mocked_responses: responses.RequestsMock,
        stream_url: str,
        active_live_video_info: YouTubeVideoInfo,
        audio_base_url: str,
        tmp_path: Path,
    ):
        add_responses_callback_for_segment_urls(urljoin(audio_base_url, r"sq/\w+"))
        self.playback = Playback(stream_url, fetcher=fake_info_fetcher)
        self.playback.fetch_and_set_essential()

    def test_start_sequence(self, fake_stream):
        sequence = 7959120
        date = datetime.fromtimestamp(1679787234.491176, tz=timezone.utc)
        expected = RewindMoment(date, sequence, 0, False)
        assert expected == self.playback.locate_moment(sequence, fake_stream)

    def test_end_sequence(self, fake_stream):
        sequence = 7959120
        date = datetime(2023, 3, 25, 23, 33, 56, 488092, tzinfo=timezone.utc)
        expected = RewindMoment(date, sequence, 0, True)
        assert expected == self.playback.locate_moment(sequence, fake_stream, True)

    def test_start_date(
        self, add_responses_callback_for_reference_base_url: Callable, fake_stream
    ):
        add_responses_callback_for_reference_base_url()
        date = datetime.fromisoformat("2023-03-25T23:33:55Z")
        expected = RewindMoment(date, 7959120, 0.508824, False, False)
        actual = self.playback.locate_moment(date, fake_stream)
        assert expected == RewindMoment(
            actual.date,
            actual.sequence,
            pytest.approx(actual.cut_at, 1e-6),
            actual.is_end,
            actual.falls_in_gap,
        )

    def test_end_date(
        self, add_responses_callback_for_reference_base_url: Callable, fake_stream
    ):
        add_responses_callback_for_reference_base_url()
        date = datetime.fromisoformat("2023-03-25T23:33:55Z")
        expected = RewindMoment(date, 7959120, 0.508824, True, False)
        actual = self.playback.locate_moment(date, fake_stream, True)
        assert expected == RewindMoment(
            actual.date,
            actual.sequence,
            pytest.approx(actual.cut_at, 1e-6),
            actual.is_end,
            actual.falls_in_gap,
        )


@pytest.mark.parametrize(
    "start,end",
    [
        (7959120, 7959121),
        (7959120, datetime.fromisoformat("2023-03-25T23:33:57Z")),
        (7959120, timedelta(seconds=3)),  # segment duration (2 s) + 1 s
        (7959120, RelativeSegmentSequence(1)),
        (datetime.fromisoformat("2023-03-25T23:33:55Z"), 7959121),
        (
            datetime.fromisoformat("2023-03-25T23:33:55Z"),
            datetime.fromisoformat("2023-03-25T23:33:57Z"),
        ),
        (datetime.fromisoformat("2023-03-25T23:33:55Z"), timedelta(seconds=2)),
        (datetime.fromisoformat("2023-03-25T23:33:55Z"), RelativeSegmentSequence(1)),
        (timedelta(seconds=3), 7959121),  # segment duration (2 s) + 1 s
        (timedelta(seconds=2), datetime.fromisoformat("2023-03-25T23:33:57Z")),
        (RelativeSegmentSequence(1), 7959121),
        (RelativeSegmentSequence(1), datetime.fromisoformat("2023-03-25T23:33:57Z")),
    ],
)
def test_locate_interval(
    start,
    end,
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    mocked_responses: responses.RequestsMock,
    stream_url: str,
    active_live_video_info: YouTubeVideoInfo,
    audio_base_url: str,
    fake_stream: "FakeStream",
    tmp_path: Path,
) -> None:
    # Given:
    any_datetime = isinstance(start, datetime) or isinstance(end, datetime)
    if type(start) is not SegmentSequence and any_datetime:
        add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(urljoin(audio_base_url, r"sq/\w+"))

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    interval = playback.locate_interval(start, end, fake_stream)

    # Then:
    assert interval.start.sequence == 7959120
    assert interval.end.sequence == 7959121


@pytest.mark.parametrize(
    "start,end",
    [
        (timedelta(seconds=2), timedelta(seconds=2)),
        (RelativeSegmentSequence(1), RelativeSegmentSequence(1)),
        (timedelta(seconds=2), RelativeSegmentSequence(1)),
        (RelativeSegmentSequence(1), timedelta(seconds=2)),
    ],
)
def test_local_interval_with_relative_start_and_end(
    start: timedelta | RelativeSegmentSequence,
    end: timedelta | RelativeSegmentSequence,
    stream_url: str,
    fake_info_fetcher: "FakeInfoFetcher",
    fake_stream: "FakeStream",
    tmp_path: Path,
):
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    with pytest.raises(ValueError):
        playback.locate_interval(start, end, fake_stream)


@pytest.mark.parametrize(
    "start,end",
    [
        (7959122, 7959121),
        (7959121, datetime.fromisoformat("2023-03-25T23:33:55Z")),
        (datetime.fromisoformat("2023-03-25T23:33:57Z"), 7959120),
        (
            datetime.fromisoformat("2023-03-25T23:33:57Z"),
            datetime.fromisoformat("2023-03-25T23:33:55Z"),
        ),
        (datetime.fromisoformat("2023-03-25T23:33:57Z"), RelativeSegmentSequence(-1)),
    ],
)
def test_locate_interval_with_swapped_start_and_end(
    start,
    end,
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    mocked_responses: responses.RequestsMock,
    stream_url: str,
    active_live_video_info: YouTubeVideoInfo,
    audio_base_url: str,
    fake_stream: "FakeStream",
    tmp_path: Path,
) -> None:
    # Given:
    if not isinstance(start, int):
        add_responses_callback_for_reference_base_url()
    add_responses_callback_for_segment_urls(urljoin(audio_base_url, r"sq/\w+"))

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()

    # Then:
    with pytest.raises((ValueError, SequenceLocatingError)):
        playback.locate_interval(start, end, fake_stream)


def test_insert_to_rewind_history(
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_reference_base_url: Callable,
    add_responses_callback_for_segment_urls: Callable,
    mocked_responses: responses.RequestsMock,
    stream_url: str,
    audio_base_url: str,
    fake_stream: "FakeStream",
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_segment_urls(urljoin(audio_base_url, r"sq/\w+"))

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    playback.locate_moment(7959120, fake_stream)
    playback.locate_moment(7959122, fake_stream)

    # Then:
    assert playback.rewind_history.closest(1679787234.491176).value == 7959120
    assert playback.rewind_history.closest(1679787238.491916).value == 7959122


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
    test_cache_directory.mkdir(parents=True, exist_ok=True)

    frozen_time = datetime.fromisoformat("2123-09-28T17:00:00+00:00").timestamp()
    expired_at = int(frozen_time - 10)
    with open(
        test_cache_directory / f"{expired_at}~{video_id}", "w", encoding="utf-8"
    ) as f:
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


def test_rewind_interval_properties():
    interval = RewindInterval(
        RewindMoment(datetime(2024, 1, 2, 10, 20, 0), 0, 0),
        RewindMoment(datetime(2024, 1, 2, 10, 20, 30), 1000, 0),
    )
    assert timedelta(seconds=30) == interval.duration
    assert 1001 == len(interval.sequences)
