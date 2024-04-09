import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import responses

from helpers import assert_approx_duration

from ytpb import actions
from ytpb.playback import Playback, RewindInterval


@dataclass
class FakeRewindMoment:
    sequence: int
    cut_at: float = 0


@dataclass
class FakeRewindInterval:
    start: FakeRewindMoment
    end: FakeRewindMoment
    sequences = RewindInterval.sequences


@dataclass
class FakeStream:
    base_url: str


def test_download_audio_segments(
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
    output_paths = actions.download.download_segments(
        playback,
        FakeRewindInterval(FakeRewindMoment(7959120), FakeRewindMoment(7959121)),
        [FakeStream(audio_base_url)],
    )

    # Then:
    assert output_paths == [
        [
            run_temp_directory / "segments/7959120.i140.mp4",
            run_temp_directory / "segments/7959121.i140.mp4",
        ]
    ]


def test_download_audio_and_video_segments(
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_segment_urls: Callable,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    run_temp_directory: Path,
) -> None:
    # Given:
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"),
        urljoin(video_base_url, r"sq/\w+"),
    )

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    output_paths = actions.download.download_segments(
        playback,
        FakeRewindInterval(FakeRewindMoment(7959120), FakeRewindMoment(7959121)),
        [FakeStream(audio_base_url), FakeStream(video_base_url)],
    )

    # Then:
    assert output_paths == [
        [
            run_temp_directory / "segments/7959120.i140.mp4",
            run_temp_directory / "segments/7959121.i140.mp4",
        ],
        [
            run_temp_directory / "segments/7959120.i244.webm",
            run_temp_directory / "segments/7959121.i244.webm",
        ],
    ]


def test_download_audio_excerpt_with_cutting(
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_segment_urls: Callable,
    stream_url: str,
    audio_base_url: str,
    run_temp_directory: Path,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_segment_urls(urljoin(audio_base_url, r"sq/\w+"))

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    output_result = actions.download.download_excerpt(
        playback,
        FakeRewindInterval(
            FakeRewindMoment(7959120, cut_at=0.5),
            FakeRewindMoment(7959121, cut_at=1.5),
        ),
        tmp_path / "output",
        FakeStream(audio_base_url),
    )

    # Then:
    assert output_result == (
        None,
        tmp_path / "output.mp4",
        [
            run_temp_directory / "segments/7959120.i140.mp4",
            run_temp_directory / "segments/7959121.i140.mp4",
        ],
        [],
    )
    assert_approx_duration(output_result[1], 3)


def test_download_audio_and_video_excerpt_without_cutting(
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_segment_urls: Callable,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    run_temp_directory: Path,
    tmp_path: Path,
) -> None:
    # Given:
    add_responses_callback_for_segment_urls(
        urljoin(audio_base_url, r"sq/\w+"), urljoin(video_base_url, r"sq/\w+")
    )

    # When:
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    output_result = actions.download.download_excerpt(
        playback,
        FakeRewindInterval(
            FakeRewindMoment(7959120, cut_at=0.5),
            FakeRewindMoment(7959121, cut_at=1.5),
        ),
        tmp_path / "output",
        FakeStream(audio_base_url),
        FakeStream(video_base_url),
        need_cut=False,
    )

    # Then:
    assert output_result == (
        None,
        tmp_path / "output.mkv",
        [
            run_temp_directory / "segments/7959120.i140.mp4",
            run_temp_directory / "segments/7959121.i140.mp4",
        ],
        [
            run_temp_directory / "segments/7959120.i244.webm",
            run_temp_directory / "segments/7959121.i244.webm",
        ],
    )
    assert_approx_duration(output_result[1], 4)
