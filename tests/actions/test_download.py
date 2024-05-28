from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

from ytpb import actions
from ytpb.playback import Playback, RewindInterval

from tests.helpers import assert_approx_duration


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
    tmp_path: Path,
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
        sequence_numbers=range(7959120, 7959122),
        streams=[FakeStream(audio_base_url)],
        output_directory=tmp_path,
    )

    # Then:
    assert output_paths == [
        [
            tmp_path / "7959120.i140.mp4",
            tmp_path / "7959121.i140.mp4",
        ]
    ]


def test_download_audio_and_video_segments(
    fake_info_fetcher: "FakeInfoFetcher",
    add_responses_callback_for_segment_urls: Callable,
    stream_url: str,
    audio_base_url: str,
    video_base_url: str,
    tmp_path: Path,
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
        sequence_numbers=range(7959120, 7959122),
        streams=[FakeStream(audio_base_url), FakeStream(video_base_url)],
        output_directory=tmp_path,
    )

    # Then:
    assert output_paths == [
        [
            tmp_path / "7959120.i140.mp4",
            tmp_path / "7959121.i140.mp4",
        ],
        [
            tmp_path / "7959120.i244.webm",
            tmp_path / "7959121.i244.webm",
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
        rewind_interval=FakeRewindInterval(
            FakeRewindMoment(7959120, cut_at=0.5), FakeRewindMoment(7959121, cut_at=1.5)
        ),
        output_stem=tmp_path / "output",
        audio_stream=FakeStream(audio_base_url),
        segments_directory=tmp_path / "segments",
    )

    # Then:
    assert output_result == (
        None,
        tmp_path / "output.mp4",
        [
            tmp_path / "segments/7959120.i140.mp4",
            tmp_path / "segments/7959121.i140.mp4",
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
        rewind_interval=FakeRewindInterval(
            FakeRewindMoment(7959120, cut_at=0.5),
            FakeRewindMoment(7959121, cut_at=1.5),
        ),
        output_stem=tmp_path / "output",
        audio_stream=FakeStream(audio_base_url),
        video_stream=FakeStream(video_base_url),
        segments_directory=tmp_path / "segments",
        need_cut=False,
    )

    # Then:
    assert output_result == (
        None,
        tmp_path / "output.mkv",
        [
            tmp_path / "segments/7959120.i140.mp4",
            tmp_path / "segments/7959121.i140.mp4",
        ],
        [
            tmp_path / "segments/7959120.i244.webm",
            tmp_path / "segments/7959121.i244.webm",
        ],
    )
    assert_approx_duration(output_result[1], 4)
