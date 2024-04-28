import os
import pickle
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

import click
import cloup
import structlog
from cloup.constraints import constraint, require_any

from ytpb import actions
from ytpb.cli.common import (
    create_playback,
    get_parameter_by_name,
    print_summary_info,
    query_streams_or_exit,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    resolve_output_path,
    stream_argument,
    suppress_output,
)
from ytpb.cli.options import (
    cache_options,
    interval_option,
    keep_temp_option,
    preview_option,
    validate_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType, InputRewindInterval
from ytpb.download import compose_default_segment_filename
from ytpb.errors import SequenceLocatingError
from ytpb.merge import merge_segments
from ytpb.types import (
    AddressableMappingProtocol,
    AudioOrVideoStream,
    DateInterval,
    RelativeSegmentSequence,
    SegmentSequence,
)
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.path import (
    expand_template_output_path,
    IntervalOutputPathContext,
    MinimalOutputPathContext,
    OUTPUT_PATH_PLACEHOLDER_RE,
    remove_directories_between,
    render_interval_output_path_context,
    render_minimal_output_path_context,
    try_get_relative_path,
)
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.url import build_segment_url, extract_parameter_from_url

logger = structlog.get_logger(__name__)


class DownloadOutputPathContext(
    MinimalOutputPathContext, IntervalOutputPathContext
): ...


def compose_resume_filename(
    video_id: str, streams: list[AudioOrVideoStream | None]
) -> str:
    for i, arg in enumerate(sys.argv):
        if arg in ("--interval", "-i"):
            interval_option_value = sys.argv[i + 1]
            break

    interval_part = interval_option_value
    for char in "-:@":
        interval_part = interval_part.replace(char, "")
    interval_part = interval_part.replace("/", "-")

    itag_part = "+".join([stream.itag for stream in streams if stream])

    return f"{video_id}~{interval_part}-{itag_part}.resume"


def render_download_output_path_context(
    context: DownloadOutputPathContext,
    config_settings: AddressableMappingProtocol,
) -> DownloadOutputPathContext:
    output = context
    output.update(render_minimal_output_path_context(context, config_settings))
    output.update(render_interval_output_path_context(context, config_settings))
    return output


@cloup.command("download", short_help="Download excerpts.", help="Download an excerpt.")
@cloup.option_group(
    "Input options",
    interval_option,
    cloup.option(
        "-af",
        "--audio-format",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.AUDIO),
        help="Audio format to download.",
    ),
    cloup.option(
        "-vf",
        "--video-format",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.VIDEO),
        help="Video format to download.",
    ),
    preview_option,
)
@cloup.option_group(
    "Dump options",
    cloup.option(
        "--dump-base-urls",
        is_flag=True,
        help="Print base URLs and exit.",
    ),
    cloup.option(
        "--dump-segment-urls",
        is_flag=True,
        help="Print segment URLs and exit.",
    ),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Output path (without extension).",
    callback=validate_output_path(DownloadOutputPathContext),
)
@click.option(
    "-m",
    "--from-manifest",
    metavar="PATH",
    type=click.Path(path_type=Path),
    help="Path to a MPEG-DASH manifest.",
)
@click.option(
    "-X",
    "--dry-run",
    is_flag=True,
    help="Run without downloading.",
)
@yt_dlp_option
@click.option(
    "--segments-output-dir",
    "segments_output_dir_option",
    type=click.Path(path_type=Path),
    help="Location where to download segments to.",
)
@click.option("-S", "--keep-segments", is_flag=True, help="Keep downloaded segments.")
@click.option("--no-metadata", is_flag=True, help="Do not write metadata tags.")
@click.option("--no-cut", is_flag=True, help="Do not perform excerpt cutting.")
@click.option(
    "--no-merge",
    is_flag=True,
    help="Only download segments, without merging.",
)
@click.option("--no-resume", is_flag=True, help="Avoid resuming unfinished downloads.")
@cache_options
@keep_temp_option
@stream_argument
@constraint(require_any, ["audio_format", "video_format"])
@click.pass_context
def download_command(
    ctx: click.Context,
    interval: InputRewindInterval,
    audio_format: str,
    video_format: str,
    preview: bool,
    dump_base_urls: bool,
    dump_segment_urls: bool,
    output_path: Path,
    from_manifest: Path,
    dry_run: bool,
    yt_dlp: bool,
    segments_output_dir_option: Path,
    keep_segments: bool,
    no_metadata: bool,
    no_cut: bool,
    no_merge: bool,
    no_resume: bool,
    force_update_cache: bool,
    no_cache: bool,
    keep_temp: bool,
    stream_url: str,
) -> int:
    if dump_base_urls or dump_segment_urls:
        suppress_output()

    if no_merge:
        keep_segments = True

    playback = create_playback(ctx)

    queried_audio_streams = []
    if audio_format:
        logger.debug("Query audio stream by format spec", spec=audio_format)
        queried_audio_streams = query_streams_or_exit(
            playback.streams, audio_format, "--audio-format", allow_many=False
        )

    queried_video_streams = []
    if video_format:
        logger.debug("Query video stream by format spec", spec=video_format)
        queried_video_streams = query_streams_or_exit(
            playback.streams, video_format, "--video-format", allow_many=False
        )

    if queried_audio_streams and queried_video_streams:
        click.echo("These representations will be downloaded:")
    else:
        click.echo("This representation will be downloaded:")

    audio_stream, video_stream = None, None
    if audio_format:
        (audio_stream,) = queried_audio_streams
        click.echo(
            f"   - Audio: itag {audio_stream.itag}, "
            f"{audio_stream.format} ({audio_stream.codecs}), "
            f"{audio_stream.audio_sampling_rate} Hz"
        )
        logger.info("Queried audio stream", base_url=audio_stream.base_url)

    if video_format:
        (video_stream,) = queried_video_streams
        click.echo(
            f"   - Video: itag {video_stream.itag}, "
            f"{video_stream.format} ({video_stream.codecs}), "
            f"{video_stream.width}x{video_stream.height}, "
            f"{video_stream.frame_rate} fps"
        )
        logger.info("Queried video stream", base_url=video_stream.base_url)

    if dump_base_urls:
        if audio_format:
            click.echo(audio_stream.base_url, ctx.obj.original_stdout)
        if video_format:
            click.echo(video_stream.base_url, ctx.obj.original_stdout)
        sys.exit()

    click.echo()

    click.echo("(<<) Locating start and end in the stream... ", nl=False)

    reference_stream = video_stream or audio_stream
    reference_base_url = reference_stream.base_url
    head_sequence = request_reference_sequence(reference_base_url, playback.session)

    requested_start, requested_end = resolve_relativity_in_interval(*interval)

    if isinstance(requested_start, SegmentSequence):
        raise_for_too_far_sequence(
            requested_start, head_sequence, reference_base_url, ctx, "interval"
        )
        raise_for_sequence_ahead_of_current(
            requested_start, head_sequence, ctx, "interval"
        )

    match requested_end:
        case SegmentSequence() as x:
            raise_for_sequence_ahead_of_current(x, head_sequence, ctx, "interval")
        case "now":
            requested_end = head_sequence - 1
        case "..":
            if not preview:
                raise click.BadParameter(
                    "Open interval is only valid in the preview mode",
                    param=get_parameter_by_name("interval", ctx),
                )

    if preview:
        no_resume = True
        preview_duration_value = ctx.obj.config.traverse("general.preview_duration")
        segment_duration = float(extract_parameter_from_url("dur", reference_base_url))
        number_of_segments = round(preview_duration_value / segment_duration)
        requested_end = RelativeSegmentSequence(number_of_segments)

    resume_run: bool = False
    resume_file_path = Path.cwd() / compose_resume_filename(
        playback.video_id, (audio_stream, video_stream)
    )

    if not no_resume and resume_file_path.exists():
        logger.debug("Load resume file from %s", resume_file_path)
        with open(resume_file_path, "rb") as f:
            resume_run = True
            pickled = pickle.load(f)
            rewind_interval = pickled["interval"]
            previous_segments_output_directory = Path.absolute(
                pickled["segments_output_directory"]
            )

    if not resume_run:
        try:
            rewind_interval = playback.locate_interval(
                requested_start,
                requested_end,
                reference_stream,
            )
        except SequenceLocatingError:
            message = "\nerror: An error occured during segment locating, exit."
            click.echo(message, err=True)

    click.echo("done.")

    if dump_segment_urls:
        range_part = "[{start}-{end}]".format(
            start=rewind_interval.start.sequence, end=rewind_interval.end.sequence
        )
        build_dump_url = lambda base_url: build_segment_url(base_url, range_part)
        if audio_format:
            click.echo(build_dump_url(audio_stream.base_url), ctx.obj.original_stdout)
        if video_format:
            click.echo(build_dump_url(video_stream.base_url), ctx.obj.original_stdout)
        sys.exit()

    if preview and interval[1] != "..":
        click.echo("info: The preview mode is enabled, interval end is ignored.")

    start_segment = playback.get_segment(
        rewind_interval.start.sequence, reference_stream
    )
    end_segment = playback.get_segment(rewind_interval.end.sequence, reference_stream)

    requested_start_date: datetime
    match requested_start:
        case SegmentSequence():
            requested_start_date = start_segment.ingestion_start_date
        case datetime():
            requested_start_date = requested_start
        case timedelta() as delta:
            requested_start_date = end_segment.ingestion_end_date - delta

    requested_end_date: datetime
    match requested_end:
        case SegmentSequence():
            requested_end_date = end_segment.ingestion_end_date
        case datetime():
            requested_end_date = requested_end
        case timedelta() as delta:
            requested_end_date = start_segment.ingestion_start_date + delta

    requested_date_interval = DateInterval(requested_start_date, requested_end_date)
    actual_date_interval = DateInterval(
        start_segment.ingestion_start_date,
        end_segment.ingestion_end_date,
    )

    cut_kwargs: dict[str, float] = {}
    if not no_cut:
        cut_at_start = rewind_interval.start.cut_at
        if preview:
            cut_at_end = 0
        else:
            cut_at_end = rewind_interval.end.cut_at
        cut_kwargs.update(
            {
                "cut_at_start": cut_at_start,
                "cut_at_end": cut_at_end,
            }
        )
        actual_date_interval = DateInterval(
            rewind_interval.start.date, rewind_interval.end.date
        )

    print_summary_info(requested_date_interval, actual_date_interval, rewind_interval)
    click.echo()

    if preview:
        segments_output_directory = playback.get_temp_directory()
    else:
        segments_output_directory = (
            segments_output_dir_option
            or resume_file_path.with_name(f"{resume_file_path.stem}-segments")
        )
    segments_output_directory = segments_output_directory.absolute()
    logger.debug("Segments output directory set to %s", segments_output_directory)

    if resume_run:
        click.echo(
            f"~ Found unfinished download, continue from {resume_file_path.name}\n"
        )
        if segments_output_directory != previous_segments_output_directory:
            click.echo(
                "fatal: The previous segments output directory is not "
                "the same as the current run:\n'{}' != '{}'.".format(
                    try_get_relative_path(previous_segments_output_directory),
                    try_get_relative_path(segments_output_directory),
                ),
                err=True,
            )
            click.echo(
                "\nUse '--segments-output-dir {}' or '--no-resume'.".format(
                    try_get_relative_path(previous_segments_output_directory)
                ),
                err=True,
            )
            sys.exit(1)

    if segments_output_dir_option is None or not segments_output_directory.exists():
        need_to_remove_segments_directory = True
        segments_directory_to_remove = segments_output_directory
        for directory in segments_output_directory.parents:
            if directory.exists():
                break
            segments_directory_to_remove = directory
        segments_output_directory.mkdir(parents=True, exist_ok=True)
    else:
        need_to_remove_segments_directory = False

    if not resume_run:
        with open(resume_file_path, "wb") as f:
            logger.debug("Write resume file to %s", resume_file_path)
            to_pickle = {
                "interval": rewind_interval,
                "segments_output_directory": segments_output_directory,
            }
            pickle.dump(to_pickle, f)

    if dry_run:
        click.echo("notice: This is a dry run. Skip downloading and exit.")
    else:
        # Absolute output path of an excerpt without extension.
        final_output_path: Path

        if OUTPUT_PATH_PLACEHOLDER_RE.search(str(output_path)):
            input_timezone = requested_date_interval.start.tzinfo
            template_context: DownloadOutputPathContext = {
                "id": playback.video_id,
                "title": playback.info.title,
                "input_start_date": requested_date_interval.start,
                "input_end_date": requested_date_interval.end,
                "actual_start_date": actual_date_interval.start.astimezone(
                    input_timezone
                ),
                "actual_end_date": actual_date_interval.end.astimezone(input_timezone),
                "duration": requested_end_date - requested_start_date,
            }
            final_output_path = expand_template_output_path(
                output_path,
                template_context,
                render_download_output_path_context,
                ctx.obj.config,
            )
        else:
            final_output_path = output_path
        final_output_path = resolve_output_path(final_output_path)

        if resume_run:
            extract_sequence_number = lambda p: int(p.name.split(".")[0])
            latest_sequence_number = extract_sequence_number(
                sorted(
                    segments_output_directory.glob(
                        f"*.i{(audio_stream or video_stream).itag}*"
                    ),
                    key=extract_sequence_number,
                )[-1]
            )
            sequences_to_download = range(
                latest_sequence_number, rewind_interval.end.sequence + 1
            )
            completed_segments = latest_sequence_number - rewind_interval.start.sequence
        else:
            sequences_to_download = rewind_interval.sequences
            completed_segments = 0

        total_segments = len(rewind_interval.sequences)

        progress_reporter = actions.download.RichProgressReporter()
        if audio_stream:
            progress_reporter.progress.add_task(
                "   - Audio", total=total_segments, completed=completed_segments
            )
        if video_stream:
            progress_reporter.progress.add_task(
                "   - Video", total=total_segments, completed=completed_segments
            )

        do_download_segments = partial(
            actions.download.download_segments,
            playback=playback,
            sequence_numbers=sequences_to_download,
            streams=[x for x in [audio_stream, video_stream] if x is not None],
            output_directory=segments_output_directory,
            progress_reporter=progress_reporter,
        )

        if no_merge:
            click.echo(
                "(<<) Downloading segments {}-{} (no merge requested)...".format(
                    rewind_interval.start.sequence, rewind_interval.end.sequence
                )
            )
            downloaded_segment_paths = do_download_segments()
            click.echo(
                "\nSuccess! Segments saved to {}/.".format(
                    try_get_relative_path(segments_output_directory)
                )
            )
        else:
            click.echo("(<<) Preparing and saving the excerpt...")
            click.echo(
                "1. Downloading segments {}-{}:".format(
                    rewind_interval.start.sequence, rewind_interval.end.sequence
                )
            )

            downloaded_segment_paths = do_download_segments()
            audio_and_video_segment_paths: list[list[Path]] = [[], []]
            if audio_stream:
                audio_and_video_segment_paths[0] = [
                    segments_output_directory
                    / compose_default_segment_filename(sequence, audio_stream.base_url)
                    for sequence in rewind_interval.sequences
                ]
            if video_stream:
                audio_and_video_segment_paths[1] = [
                    segments_output_directory
                    / compose_default_segment_filename(sequence, video_stream.base_url)
                    for sequence in rewind_interval.sequences
                ]

            if no_cut:
                click.echo("2. Merging segments (no cut requested)... ", nl=False)
            else:
                click.echo("2. Merging segments (may take a while)... ", nl=False)

            metadata_tags: dict[str, str] = {}
            if not no_metadata:
                convert_timestamp_to_string = lambda timestamp: f"{timestamp:.6f}"
                metadata_tags = {
                    "title": playback.info.title,
                    "author": playback.info.author,
                    "comment": playback.video_url,
                    "actual_start_time": convert_timestamp_to_string(
                        actual_date_interval.start.timestamp()
                    ),
                    "actual_end_time": convert_timestamp_to_string(
                        actual_date_interval.end.timestamp()
                    ),
                    "input_start_time": convert_timestamp_to_string(
                        requested_date_interval.start.timestamp()
                    ),
                    "input_end_time": convert_timestamp_to_string(
                        requested_date_interval.end.timestamp()
                    ),
                    "start_sequence_number": rewind_interval.start.sequence,
                    "end_sequence_number": rewind_interval.end.sequence,
                }

            merged_path = merge_segments(
                audio_and_video_segment_paths[0],
                audio_and_video_segment_paths[1],
                output_directory=final_output_path.parent,
                output_stem=final_output_path.name,
                temp_directory=playback.get_temp_directory(),
                metadata_tags=metadata_tags,
                **cut_kwargs,
            )

            click.echo("done.\n")
            click.echo(f"Success! Saved to '{try_get_relative_path(merged_path)}'.")

            if keep_segments and not preview:
                click.echo(
                    "~ Segments are kept in '{}'.".format(
                        try_get_relative_path(segments_output_directory)
                    )
                )

    run_temp_directory = playback.get_temp_directory()
    if keep_temp:
        click.echo(f"notice: No cleanup enabled, check {run_temp_directory}/")
    else:
        try:
            shutil.rmtree(run_temp_directory)
        except OSError:
            logger.warning(
                "Failed to remove temporary directory: %s", run_temp_directory
            )

    if not no_resume:
        resume_file_path.unlink()

    if not dry_run and not keep_segments and not preview:
        try:
            for paths in audio_and_video_segment_paths:
                for path in paths:
                    path.unlink()
        except OSError:
            logger.warning("Could not remove segment: %s", path)
        try:
            if need_to_remove_segments_directory:
                logger.debug(
                    "Remove created segments directory: %s",
                    segments_directory_to_remove,
                )
                remove_directories_between(
                    segments_directory_to_remove, segments_output_directory
                )
        except OSError:
            logger.warning(
                "Could not remove segments directory: %s",
                segments_directory_to_remove,
            )
