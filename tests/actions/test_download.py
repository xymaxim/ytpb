import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import responses

from ytpb import actions
from ytpb.playback import Playback


@dataclass
class FakeRewindMoment:
    sequence: int


@dataclass
class FakeRewindInterval:
    start: FakeRewindMoment
    end: FakeRewindMoment


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
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()
    _, *output_paths = actions.download.download_excerpt(
        playback,
        FakeRewindInterval(FakeRewindMoment(7959120), FakeRewindMoment(7959121)),
        "itag eq 140",
        "itag eq 244",
        no_merge=True,
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
    _, *output_paths = actions.download.download_excerpt(
        playback,
        FakeRewindInterval(FakeRewindMoment(7959120), FakeRewindMoment(7959121)),
        "itag eq 140",
        no_merge=True,
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

    rewind_interval = playback.locate_interval(start_date, end_date, itag="140")
    _, *output_paths = actions.download.download_excerpt(
        playback, rewind_interval, "itag eq 140", "itag eq 244", no_merge=True
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
