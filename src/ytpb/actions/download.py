"""Actions to download excerpts."""

from itertools import repeat
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
    sequence_numbers: Iterable[SegmentSequence],
    streams: Union[SetOfStreams, list[AudioOrVideoStream]],
    output_directory: Path | None = None,
    output_filename: Callable[
        [SegmentSequence, str], str
    ] = compose_default_segment_filename,
    progress_reporter: ProgressReporter | None = None,
) -> list[Path]:
    """Downloads segments.

    Args:
        playback: A playback.
        sequence_numbers: Segment sequence numbers to rewind.
        streams: Streams to download.
        output_directory: A directory where to save downloaded segments.
        output_filename: A callable to compose segment filenames.
        progress_reporter: An instance of :class:`ProgressReporter`-like class
          to show downloading progress. Defaults to dummy progress reporter.

    Returns:
        A list of downloaded segment paths.
    """
    if progress_reporter is None:
        progress_reporter = NullProgressReporter()

    if output_directory is None:
        output_directory = playback.locations["segments"]
        output_directory.mkdir(parents=True, exist_ok=True)

    base_urls: list[str] = [s.base_url for s in streams]
    download_generator = chained_zip(
        *[
            zip(
                iter_segments(sequence_numbers, base_url, session=playback.session),
                repeat(task, len(sequence_numbers)),
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
    segments_directory: Path,
    audio_stream: AudioStream | None = None,
    video_stream: VideoStream | None = None,
    need_cut: bool = True,
    merge_kwargs: dict[str, Any] | None = None,
    progress_reporter: ProgressReporter | None = None,
) -> ExcerptDownloadResult:
    """Downloads and merges audio and/or video segments.

    Notes:
        Downloaded segments are not cleaned up after merging.

    Args:
        playback: A playback.
        rewind_interval: A rewind interval.
        output_stem: A full path stem of the merged excerpt file.
        audio_stream: An audio stream.
        video_stream: A video stream.
        segments_directory: A directory where to store downloaded segments.
        need_cut: Whether to cut boundary segments to exact times.
        merge_kwargs: Arguments that :meth:`ytpb.merge.merge_segments` takes.
        progress_reporter: An instance of :class:`ProgressReporter`-like class
          to show downloading progress. Defaults to dummy progress reporter.

    Returns:
        An :class:`ExcerptDownloadResult` object.
    """
    if not (audio_stream or video_stream):
        raise AssertionError("At least audio or video stream should be provided")

    if progress_reporter is None:
        progress_reporter = NullProgressReporter()

    all_streams = [x for x in [audio_stream, video_stream] if x is not None]

    segments_directory.mkdir(parents=True, exist_ok=True)

    _downloaded_paths: list[list[Path]] = download_segments(
        playback, rewind_interval.sequences, all_streams, segments_directory
    )
    downloaded_paths: list[list[Path]] = [[], []]
    if audio_stream:
        downloaded_paths[0] = _downloaded_paths[0]
    if video_stream:
        downloaded_paths[1] = _downloaded_paths[1]

    cut_at_kwargs: dict[str, float] = {}
    if need_cut:
        cut_at_kwargs = {
            "cut_at_start": rewind_interval.start.cut_at,
            "cut_at_end": rewind_interval.end.cut_at,
        }

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
