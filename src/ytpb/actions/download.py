"""Actions to download excerpts."""

from itertools import product
from pathlib import Path
from typing import Any, Callable, Iterable, NamedTuple, Protocol, Union

import structlog
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from ytpb.download import (
    compose_default_segment_filename,
    download_segment,
    iter_segments,
    save_segment_to_file,
)
from ytpb.merge import merge_segments
from ytpb.playback import Playback, RewindInterval
from ytpb.types import (
    AudioOrVideoStream,
    AudioStream,
    SegmentSequence,
    SetOfStreams,
    VideoStream,
)
from ytpb.utils.other import S_TO_MS

logger = structlog.get_logger(__name__)


class ProgressReporter(Protocol):
    def __enter__(self): ...

    def __exit__(self, exc_type, exc_value, traceback): ...

    def update(self, task: int): ...


class NullProgressReporter:
    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def update(self, task: int = 0) -> None:
        pass


class RichProgressReporter:
    def __init__(self, progress: Progress | None = None):
        if progress is None:
            progress = Progress(
                TextColumn("{task.description}"),
                BarColumn(bar_width=28),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TextColumn("eta"),
                TimeRemainingColumn(),
                console=Console(),
            )
        self.progress = progress

    def __enter__(self) -> None:
        self.progress.start()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.progress.stop()

    def update(self, task: int = 0) -> None:
        self.progress.advance(TaskID(task))


class ExcerptDownloadResult(NamedTuple):
    """Represents an excerpt download result."""

    #: An exception raised during downloading.
    exception: Exception | None
    #: A path of the merged excerpt file.
    merged_path: Path
    #: Paths of downloaded audio segments.
    audio_segment_paths: list[Path]
    #: Paths of downloaded video segments.
    video_segment_paths: list[Path]


def chained_zip(*iterables) -> Iterable[Any]:
    """Makes an iterator that returns elements from iterables in round robin fashion.

    Notes:
        The implementation assumes that the lengths of the iterables are the
        same. Otherwise, the iteration will stop after exhausting of the shortest
        iterable.

    Examples:
        >>> list(chained_zip(["A", "B"], [0, 1]))
        ["A", 0, "B", 1]
    """
    iterators = [iter(x) for x in iterables]
    while True:
        for it in iterators:
            try:
                yield next(it)
            except StopIteration:
                return


def download_segments(
    playback: Playback,
    rewind_interval: RewindInterval,
    streams: Union[SetOfStreams, list[AudioOrVideoStream]],
    output_directory: Path | None = None,
    output_filename: Callable[
        [SegmentSequence, str], str
    ] = compose_default_segment_filename,
    progress_reporter: ProgressReporter = NullProgressReporter(),
) -> list[Path]:
    """Downloads segments.

    Args:
        playback: A playback.
        rewind_interval: A rewound interval.
        streams: Streams to download.
        output_directory: A directory where to save downloaded segments.
        output_filename: A callable to compose segment filenames.
        progress_reporter: An instance of :class:`ProgressReporter`-like class
          to show downloading progress. Defaults to dummy progress reporter.

    Returns:
        A list of downloaded segment paths.
    """
    sequences_to_download = range(
        rewind_interval.start.sequence, rewind_interval.end.sequence + 1
    )

    if output_directory is None:
        output_directory = playback.get_temp_directory() / "segments"
        output_directory.mkdir(parents=True, exist_ok=True)

    base_urls: List[str] = [s.base_url for s in streams]
    download_generator = chained_zip(
        *[
            product(
                iter_segments(
                    sequences_to_download, base_url, session=playback.session
                ),
                [task],
            )
            for task, base_url in enumerate(base_urls)
        ]
    )

    downloaded_paths: list[list[Path]] = [[] for _ in base_urls]
    with progress_reporter:
        for (response, sequence, base_url), task in download_generator:
            downloaded_path = save_segment_to_file(
                response.content, sequence, base_url, output_directory, output_filename
            )
            downloaded_paths[task].append(downloaded_path)
            progress_reporter.update(task)

    return downloaded_paths


def download_excerpt(
    playback: Playback,
    rewind_interval: RewindInterval,
    output_stem: str | Path,
    audio_stream: AudioStream | None = None,
    video_stream: VideoStream | None = None,
    need_cut: bool = True,
    merge_kwargs: dict[str, Any] | None = None,
    progress_reporter: ProgressReporter = NullProgressReporter(),
) -> ExcerptDownloadResult:
    """Downloads and merges audio and/or video segments.

    Notes:
        Downloaded segments are not cleaned up after merging.

    Args:
        playback: A playback.
        rewind_interval: A rewound interval.
        output_stem: A full path stem of the merged excerpt file.
        audio_stream: An audio stream.
        video_stream: A video stream.
        need_cut: Whether to cut boundary segments to exact times.
        merge_kwargs: Arguments that :meth:`ytpb.merge.merge_segments` takes.
        progress_reporter: An instance of :class:`ProgressReporter`-like class
          to show downloading progress. Defaults to dummy progress reporter.

    Returns:
        An :class:`ExcerptDownloadResult` object.
    """
    if not (audio_stream or video_stream):
        raise AssertionError("At least audio or video stream should be provided")

    sequences_to_download = range(
        rewind_interval.start.sequence, rewind_interval.end.sequence + 1
    )

    all_streams = [x for x in [audio_stream, video_stream] if x is not None]

    segments_output_directory = playback.get_temp_directory() / "segments"
    segments_output_directory.mkdir(parents=True, exist_ok=True)

    _downloaded_paths: list[list[Path]] = download_segments(
        playback, rewind_interval, all_streams, segments_output_directory
    )
    downloaded_paths: list[list[Path]] = [[], []]
    if audio_stream:
        downloaded_paths[0] = _downloaded_paths[0]
    if video_stream:
        downloaded_paths[1] = _downloaded_paths[1]

    if need_cut:
        if video_stream:
            base_url = video_stream.base_url
        else:
            base_url = audio_stream.base_url
        end_segment = playback.get_segment(
            rewind_interval.end.sequence, base_url, "segments"
        )
        cut_at_kwargs = {"cut_at_start": rewind_interval.start.cut_at * S_TO_MS}
        if rewind_interval.end.cut_at != 0:
            cut_at_kwargs["cut_at_end"] = (
                end_segment.get_actual_duration() * S_TO_MS
                - rewind_interval.end.cut_at * S_TO_MS
            )
    else:
        cut_at_kwargs = {}

    merge_kwargs = {**cut_at_kwargs, **(merge_kwargs or {})}

    output_stem = Path(output_stem)
    merge_output_directory = output_stem.parent
    merge_output_stem = output_stem.name

    downloaded_audio_paths, downloaded_video_paths = downloaded_paths
    try:
        merged_path = merge_segments(
            downloaded_audio_paths,
            downloaded_video_paths,
            output_directory=merge_output_directory,
            output_stem=merge_output_stem,
            temp_directory=playback.get_temp_directory(),
            **merge_kwargs,
        )
        result = ExcerptDownloadResult(
            None, merged_path, downloaded_audio_paths, downloaded_video_paths
        )
    except Exception as exc:
        result = ExcerptDownloadResult(
            exc, None, downloaded_audio_paths, downloaded_video_paths
        )

    return result
