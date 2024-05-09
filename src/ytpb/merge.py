"""Merge and cut media segments.

Note:
    The current implementation of segment merging is not optimal in terms of
    disk space, as it requires triple the amount of the total size of segments
    if cutting is requested (by default). Should be changed to use different
    techniques, without the need for intermediate files.
"""

import functools
import os
import shlex
from pathlib import Path
from typing import Any

import av

from ytpb.utils import ffmpeg

__all__ = ("merge_segments", "mux_and_cut_boundary_segment")


DEFAULT_VIDEO_ENCODING_SETTINGS = {
    "h264": "libx264 -crf 18",
    "vp9": "libvpx-vp9 -crf 31 -b:v 0",
    "av1": "libaom-av1 -crf 31",
}


def get_nth_or_none(iterable, n: int) -> Any | None:
    if not iterable:
        return None
    return iterable[n]


def mux_and_cut_boundary_segment(
    audio_segment_path: Path,
    video_segment_path: Path,
    output_path: Path,
    video_codec: str | None = None,
    **cut_kwargs,
) -> None:
    """Muxes and cuts a boundary segment.

    Args:
        audio_segment_path: A path to an audio segment.
        video_segment_path: A path to a video segment.
        output_path: An output path of the muxed segment.
        video_codec: A video codec name.
        cut_kwargs: Cut keyword arguments: ``cut_at_start`` and ``cut_at_end``.
    """

    def prepare_ffmpeg_input_options(
        segment_path: Path, cut_at_start: float = 0, cut_at_end: float = 0
    ):
        assert cut_at_start or cut_at_end
        if cut_at_start > 0:
            return ["-ss", f"{cut_at_start:.6f}s", "-i", segment_path]
        elif cut_at_end > 0:
            return ["-i", segment_path, "-to", f"{cut_at_end:.6f}s"]
        else:
            return ["-i", segment_path]

    if not {"cut_at_start", "cut_at_end"} > cut_kwargs.keys():
        raise ValueError(
            "only cut_at_start or cut_at_end keyword argument is accepted in cut_kwargs"
        )

    if video_segment_path and video_codec is None:
        with av.open(video_segment_path) as container:
            video_av_stream = container.streams.get({"video": 0})[0]
            video_codec = video_av_stream.codec_context.name

    ffmpeg_input_options = []
    ffmpeg_codecs_options = []

    should_cut = bool(
        cut_kwargs.get("cut_at_start", 0) or cut_kwargs.get("cut_at_end", 0)
    )
    if should_cut is False:
        if video_segment_path:
            ffmpeg_input_options += ["-i", video_segment_path]
        if audio_segment_path:
            ffmpeg_input_options += ["-i", audio_segment_path]
        ffmpeg.run_ffmpeg(ffmpeg_input_options + ["-c", "copy", output_path])
    else:
        if video_segment_path:
            ffmpeg_input_options += prepare_ffmpeg_input_options(
                video_segment_path, **cut_kwargs
            )

            user_encoding_settings = os.environ.get(
                f"YTPB_{video_codec.upper()}_ENCODING_SETTINGS", None
            )
            if user_encoding_settings:
                ffmpeg_codecs_options += ["-c:v"] + shlex.split(user_encoding_settings)
            else:
                try:
                    ffmpeg_codecs_options += ["-c:v"] + shlex.split(
                        DEFAULT_VIDEO_ENCODING_SETTINGS[video_codec]
                    )
                except KeyError:
                    raise ValueError(
                        "No encoding settings are availabe for "
                        f"'{video_codec}' video codec"
                    )

        if audio_segment_path:
            ffmpeg_input_options += prepare_ffmpeg_input_options(
                audio_segment_path, **cut_kwargs
            )
            ffmpeg_codecs_options += ["-c:a", "copy"]

        additional_options: list[str] = []
        if video_segment_path and video_codec == "h264":
            # Ensure to have the same tbn values after re-encoding of segments
            # and their concatenation (see the merge_segments() function).
            additional_options += ["-video_track_timescale", "1k"]

        ffmpeg.run_ffmpeg(
            [
                *ffmpeg_input_options,
                *additional_options,
                *ffmpeg_codecs_options,
                output_path,
            ]
        )


def _compose_concat_file(segment_paths, temp_directory, suffix: str = ""):
    if suffix:
        concat_file_path = Path(temp_directory, f"concat_{suffix}")
    else:
        concat_file_path = Path(temp_directory, "concat")

    concat_file_lines = [f"file '{path}'\n" for path in segment_paths]

    with open(concat_file_path, "w") as f:
        f.writelines(concat_file_lines)

    return concat_file_path


def ensure_cleanup_if_needed(f):
    @functools.wraps(f)
    def g(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        finally:
            if kwargs.get("cleanup", True):
                assert getattr(g, "paths_to_cleanup", None) is not None
                for path in g.paths_to_cleanup:
                    path.unlink(missing_ok=True)

    return g


@ensure_cleanup_if_needed
def merge_segments(
    audio_segment_paths: list[Path] | None = None,
    video_segment_paths: list[Path] | None = None,
    output_directory: str | Path | None = None,
    output_stem: str | Path | None = None,
    temp_directory: str | Path | None = None,
    cut_at_start: float = 0,
    cut_at_end: float = 0,
    metadata_tags: dict[str, str] = None,
    cleanup: bool = True,
) -> Path:
    """Merges and cuts media segments.

    The ``cut_at_start`` and ``cut_at_end`` arguments define the values to be
    passed to FFmpeg: ``-ss <cut_at_start>s`` and ``-to <cut_at_end>s``,
    respectively.

    Args:
        audio_segment_paths: Paths to audio segments.
        video_segment_paths: Paths to video segments.
        output_directory: Where to output the merged file.
        output_stem: An output stem of the merged file.
        temp_directory: Where to store intermediate files.
        cut_at_start: An offset (in seconds) to cut at start.
        cut_at_end: An offset (in seconds) to cut at end.
        metadata_tags: Metadata tags to write to the merged file.
        cleanup: Whether to cleanup intermediate files.

    Returns:
        A path of the merged file.
    """
    merge_segments.paths_to_cleanup = []

    if audio_segment_paths is None and video_segment_paths is None:
        raise ValueError("Audio or/and video paths should be provided")

    audio_segment_paths = audio_segment_paths or []
    video_segment_paths = video_segment_paths or []

    if audio_segment_paths and video_segment_paths:
        if len(audio_segment_paths) != len(video_segment_paths):
            raise ValueError("Audio and video paths are not of equal size")
        output_extension = ".mkv"
    elif audio_segment_paths:
        output_extension = os.path.splitext(audio_segment_paths[0])[1]
    elif video_segment_paths:
        output_extension = os.path.splitext(video_segment_paths[0])[1]

    if output_directory:
        output_directory = Path(output_directory)
    else:
        output_directory = Path.cwd()
    output_path = output_directory / f"{output_stem}{output_extension}"

    metadata_options: list[str] = []
    if metadata_tags:
        metadata_options = ["-movflags", "use_metadata_tags", "-map_metadata", "0"]
        for k, v in metadata_tags.items():
            metadata_options.extend(["-metadata", f"{k}={v}"])

    safe_concat_options = ["-safe", "0", "-f", "concat"]

    should_cut = bool(cut_at_start or cut_at_end)
    if should_cut is False:
        no_cut_concat_options = []
        if video_segment_paths:
            concat_file_path = _compose_concat_file(
                video_segment_paths, temp_directory, suffix="video"
            )
            merge_segments.paths_to_cleanup.append(concat_file_path)
            no_cut_concat_options += safe_concat_options + ["-i", concat_file_path]
        if audio_segment_paths:
            concat_file_path = _compose_concat_file(
                audio_segment_paths, temp_directory, suffix="audio"
            )
            merge_segments.paths_to_cleanup.append(concat_file_path)
            no_cut_concat_options += safe_concat_options + ["-i", concat_file_path]
        ffmpeg.run_ffmpeg(
            [*no_cut_concat_options, "-c", "copy", *metadata_options, output_path]
        )
    else:
        num_of_segments = len(audio_segment_paths or video_segment_paths)

        start_audio_segment_path = get_nth_or_none(audio_segment_paths, 0)
        start_video_segment_path = get_nth_or_none(video_segment_paths, 0)

        end_audio_segment_path = get_nth_or_none(audio_segment_paths, -1)
        end_video_segment_path = get_nth_or_none(video_segment_paths, -1)

        video_codec: str | None = None
        if video_segment_paths:
            with av.open(video_segment_paths[0]) as container:
                video_av_stream = container.streams.get({"video": 0})[0]
                video_codec = video_av_stream.codec_context.name

        if num_of_segments == 1:
            segment_trimmed_path = Path(temp_directory, "a.a" + output_extension)
            mux_and_cut_boundary_segment(
                start_audio_segment_path,
                start_video_segment_path,
                segment_trimmed_path,
                video_codec,
                cut_at_start=cut_at_start,
            )
            parts_to_merge = [segment_trimmed_path]
        elif num_of_segments == 2:
            start_trimmed_path = Path(temp_directory, "ab.a" + output_extension)
            mux_and_cut_boundary_segment(
                start_audio_segment_path,
                start_video_segment_path,
                start_trimmed_path,
                video_codec,
                cut_at_start=cut_at_start,
            )

            end_trimmed_path = start_trimmed_path.with_stem("ab.b")
            mux_and_cut_boundary_segment(
                end_audio_segment_path,
                end_video_segment_path,
                end_trimmed_path,
                video_codec,
                cut_at_end=cut_at_end,
            )

            parts_to_merge = [start_trimmed_path, end_trimmed_path]
        else:
            start_trimmed_path = Path(temp_directory, "abc.a" + output_extension)
            mux_and_cut_boundary_segment(
                start_audio_segment_path,
                start_video_segment_path,
                start_trimmed_path,
                video_codec,
                cut_at_start=cut_at_start,
            )

            middle_concatenated_path = start_trimmed_path.with_stem("abc.b")

            end_trimmed_path = start_trimmed_path.with_stem("abc.c")
            mux_and_cut_boundary_segment(
                end_audio_segment_path,
                end_video_segment_path,
                end_trimmed_path,
                video_codec,
                cut_at_end=cut_at_end,
            )

            bounds_slice = slice(1, -1)
            concat_filter_options = []

            if video_segment_paths:
                concat_file_path = _compose_concat_file(
                    video_segment_paths[bounds_slice],
                    temp_directory,
                    suffix="video",
                )
                concat_filter_options += safe_concat_options + ["-i", concat_file_path]
                merge_segments.paths_to_cleanup.append(concat_file_path)

            if audio_segment_paths:
                concat_file_path = _compose_concat_file(
                    audio_segment_paths[bounds_slice],
                    temp_directory,
                    suffix="audio",
                )
                concat_filter_options += safe_concat_options + ["-i", concat_file_path]
                merge_segments.paths_to_cleanup.append(concat_file_path)

            additional_options: list[str] = []
            if video_segment_paths and video_codec == "h264":
                additional_options += ["-video_track_timescale", "1k"]

            ffmpeg.run_ffmpeg(
                [
                    *concat_filter_options,
                    *additional_options,
                    "-c",
                    "copy",
                    middle_concatenated_path,
                ],
                capture_output=True,
                check=True,
            )

            parts_to_merge = [
                start_trimmed_path,
                middle_concatenated_path,
                end_trimmed_path,
            ]

        merge_segments.paths_to_cleanup.extend(parts_to_merge)

        if num_of_segments == 1:
            ffmpeg.run_ffmpeg(
                [
                    "-i",
                    parts_to_merge[0],
                    "-c",
                    "copy",
                    *metadata_options,
                    output_path,
                ]
            )
        else:
            concat_file_path = _compose_concat_file(parts_to_merge, temp_directory)
            ffmpeg.run_ffmpeg(
                [
                    *safe_concat_options,
                    "-i",
                    concat_file_path,
                    "-c",
                    "copy",
                    *metadata_options,
                    output_path,
                ]
            )
            merge_segments.paths_to_cleanup.append(concat_file_path)

    return output_path
