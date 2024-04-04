"""Actions to download excerpts."""

from pathlib import Path
from typing import Any, NamedTuple

import structlog
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from ytpb.download import download_segment
from ytpb.merge import merge_segments
from ytpb.playback import Playback, RewindInterval

logger = structlog.get_logger(__name__)


class ExcerptDownloadResult(NamedTuple):
    """Represents an excerpt download result."""

    #: An exception raised during downloading.
    exception: Exception | None
    #: A path of the merged excerpt file.
    merged_path: Path | None
    #: Paths of downloaded audio segments.
    audio_segment_paths: list[Path]
    #: Paths of downloaded video segments.
    video_segment_paths: list[Path]


def download_excerpt(
    playback: Playback,
    rewind_interval: RewindInterval,
    audio_format_spec: str | None = None,
    video_format_spec: str | None = None,
    output_directory: str | Path | None = None,
    output_stem: str | Path | None = None,
    no_merge: bool = False,
    merge_kwargs: dict[str, Any] | None = None,
) -> ExcerptDownloadResult:
    """Downloads and merges audio and/or video segments.

    Notes:
        Downloaded segments are not cleaned up after merging.

    Args:
        playback: A playback.
        rewind_interval: A rewound interval to download.
        audio_format_spec: An audio format spec.
        video_format_spec: A video format spec.
        output_stem: A path stem of the merged excerpt file.
        no_merge: Do not merge downloaded segments.
        merge_kwargs: Arguments that :meth:`ytpb.merge.merge_segments` takes.

    Returns:
        An :class:`ExcerptDownloadResult` object.
    """
    sequences_to_download = range(
        rewind_interval.start.sequence, rewind_interval.end.sequence + 1
    )

    download_progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=28),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("eta"),
        TimeRemainingColumn(),
        console=Console(),
    )

    if audio_format_spec:
        if queried := playback.streams.query(audio_format_spec):
            audio_base_url = queried[0].base_url
            audio_download_task = download_progress.add_task(
                "   - Audio", total=len(sequences_to_download)
            )
        else:
            raise AssertionError

    if video_format_spec:
        if queried := playback.streams.query(video_format_spec):
            video_base_url = queried[0].base_url
            video_download_task = download_progress.add_task(
                "   - Video", total=len(sequences_to_download)
            )
        else:
            raise AssertionError

    segments_output_directory = playback.get_temp_directory() / "segments"
    segments_output_directory.mkdir(parents=True, exist_ok=True)
    download_segment_kwargs = {
        "output_directory": segments_output_directory,
        "session": playback.session,
    }

    downloaded_audio_paths: list[Path] = []
    downloaded_video_paths: list[Path] = []

    with download_progress:
        for sequence in sequences_to_download:
            if audio_format_spec:
                downloaded_path = download_segment(
                    sequence, audio_base_url, **download_segment_kwargs
                )
                downloaded_audio_paths.append(downloaded_path)
                download_progress.advance(audio_download_task)
            if video_format_spec:
                downloaded_path = download_segment(
                    sequence, video_base_url, **download_segment_kwargs
                )
                downloaded_video_paths.append(downloaded_path)
                download_progress.advance(video_download_task)

    if no_merge:
        result = ExcerptDownloadResult(
            None,
            None,
            downloaded_audio_paths,
            downloaded_video_paths,
        )
    else:
        try:
            merged_path = merge_segments(
                downloaded_audio_paths,
                downloaded_video_paths,
                output_directory=output_directory,
                output_stem=output_stem,
                temp_directory=playback.get_temp_directory(),
                **(merge_kwargs or {}),
            )
            result = ExcerptDownloadResult(
                None, merged_path, downloaded_audio_paths, downloaded_video_paths
            )
        except Exception as exc:
            result = ExcerptDownloadResult(
                exc, None, downloaded_audio_paths, downloaded_video_paths
            )

    return result
