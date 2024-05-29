import pickle
import shutil
import sys
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Any, Callable, TypedDict

import click
import cloup
import structlog
from cloup.constraints import constraint, mutually_exclusive, require_any

from ytpb import actions
from ytpb.cli.common import (
    create_playback,
    echo_notice,
    find_earliest_sequence,
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
    validate_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType, InputRewindInterval
from ytpb.cli.templating import (
    AudioStreamOutputPathContext,
    check_is_template,
    IntervalOutputPathContext,
    MinimalOutputPathContext,
    render_template,
    VideoStreamOutputPathContext,
)
from ytpb.cli.utils.path import (
    remove_directories_between,
    sanitize_for_filename,
    try_get_relative_path,
)
from ytpb.download import compose_default_segment_filename
from ytpb.errors import SequenceLocatingError
from ytpb.merge import merge_segments
from ytpb.types import (
    AudioOrVideoStream,
    DateInterval,
    RelativeSegmentSequence,
    SegmentSequence,
)
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.url import build_segment_url, extract_parameter_from_url

logger = structlog.get_logger(__name__)


class DownloadOutputPathContext(
    MinimalOutputPathContext,
    AudioStreamOutputPathContext,
    VideoStreamOutputPathContext,
    IntervalOutputPathContext,
): ...


class MetadataTagsContext(TypedDict):
    #: Video's title.
    title: str
    #: Video's author (channel's name).
    author: str
    #: YouTube video URL as a comment.
    comment: str
    #: Input start date.
    input_start_date: str
    #: Input end date.
    input_end_date: str
    #: Actual start date.
    actual_start_date: str
    #: Actual end date.
    actual_end_date: str
    #: Start segment sequence number.
    start_segment: str
    #: End segment sequence number.
    end_segment: str


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

    itag_part = "".join([stream.itag for stream in streams if stream])

    return f"{video_id}-{interval_part}-{itag_part}.resume"


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
    cloup.option(
        "-ps",
        "--preview-start",
        help="Preview interval start.",
        is_flag=True,
    ),
    cloup.option(
        "-pe",
        "--preview-end",
        help="Preview interval end.",
        is_flag=True,
    ),
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
    cloup.option(
        "--dump-rewind-interval",
        is_flag=True,
        help="Print segments rewind interval and exit.",
    ),
)
@cloup.option_group(
    "Output options",
    cloup.option(
        "-o",
        "--output",
        "output_path",
        type=click.Path(path_type=Path),
        help="Output path (without extension).",
        callback=validate_output_path(DownloadOutputPathContext),
    ),
    cloup.option(
        "-S", "--keep-segments", is_flag=True, help="Keep downloaded segments."
    ),
    cloup.option(
        "-s",
        "--segments-output-dir",
        "segments_output_dir_option",
        type=click.Path(path_type=Path),
        help="Location where to download segments to.",
    ),
    cloup.option(
        "-c", "--cut", is_flag=True, help="Accurately cut an excerpt at boundaries."
    ),
    cloup.option("--no-metadata", is_flag=True, help="Do not write metadata tags."),
    cloup.option(
        "--no-merge",
        is_flag=True,
        help="Only download segments, without merging.",
    ),
)
@click.option(
    "-x",
    "--dry-run",
    is_flag=True,
    help="Run without downloading.",
)
@yt_dlp_option
@click.option(
    "--ignore-resume", is_flag=True, help="Avoid resuming unfinished download."
)
@cache_options
@keep_temp_option
@stream_argument
@constraint(require_any, ["audio_format", "video_format"])
@constraint(mutually_exclusive, ["preview_start", "preview_end"])
@click.pass_context
def download_command(
    ctx: click.Context,
    interval: InputRewindInterval,
    audio_format: str,
    video_format: str,
    preview_start: bool,
    preview_end: bool,
    dump_base_urls: bool,
    dump_segment_urls: bool,
    dump_rewind_interval: bool,
    output_path: Path,
    keep_segments: bool,
    segments_output_dir_option: Path,
    cut: bool,
    no_metadata: bool,
    no_merge: bool,
    dry_run: bool,
    yt_dlp: bool,
    ignore_resume: bool,
    no_cache: bool,
    force_update_cache: bool,
    keep_temp: bool,
    stream_url: str,
) -> int:
    if dump_base_urls or dump_segment_urls or dump_rewind_interval:
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

    if requested_start == "earliest":
        head_date = datetime.now(timezone.utc)
        requested_start = find_earliest_sequence(playback, head_sequence, head_date)

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

    preview_mode = preview_start or preview_end
    if not preview_mode and (requested_start == ".." or requested_end == ".."):
        raise click.BadParameter(
            "Open interval is only valid in the preview mode.",
            param=get_parameter_by_name("interval", ctx),
        )

    if preview_mode:
        preview_duration_value = ctx.obj.config.traverse("general.preview_duration")
        segment_duration = float(extract_parameter_from_url("dur", reference_base_url))
        preview_segments = round(preview_duration_value / segment_duration)

        if preview_start:
            if requested_start == "..":
                raise click.BadParameter(
                    "Start '..' is only valid in the end preview mode.",
                    param=get_parameter_by_name("interval", ctx),
                )
            elif isinstance(requested_start, timedelta):
                located_moment = playback.locate_moment(
                    requested_end, reference_stream, is_end=True
                )
                requested_start = located_moment.date - requested_start
            requested_end = RelativeSegmentSequence(preview_segments)
        if preview_end:
            if requested_end == "..":
                raise click.BadParameter(
                    "End '..' is only valid in the start preview mode.",
                    param=get_parameter_by_name("interval", ctx),
                )
            elif isinstance(requested_end, timedelta):
                located_moment = playback.locate_moment(
                    requested_start, reference_stream
                )
                requested_end = located_moment.date + requested_end
            requested_start = RelativeSegmentSequence(preview_segments)

    resume_run: bool = False
    resume_file_path = Path.cwd() / compose_resume_filename(
        playback.video_id, (audio_stream, video_stream)
    )

    if not ignore_resume and resume_file_path.exists():
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
            # assert False, requested_start
            rewind_interval = playback.locate_interval(
                requested_start,
                requested_end,
                reference_stream,
            )
        except SequenceLocatingError:
            message = "\nerror: An error occured during segment locating, exit."
            click.echo(message, err=True)
            sys.exit(1)

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

    if dump_rewind_interval:
        click.echo(
            "{start}-{end}".format(
                start=rewind_interval.start.sequence, end=rewind_interval.end.sequence
            ),
            ctx.obj.original_stdout,
        )
        sys.exit()

    # if preview_mode and interval[1] != "..":
    if preview_mode:
        echo_notice(
            "Preview mode enabled, interval {} is ignored.".format(
                "end" if preview_start else "start"
            )
        )

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
    if cut:
        cut_at_start = 0 if preview_start else rewind_interval.start.cut_at
        cut_at_end = 0 if preview_end else rewind_interval.end.cut_at
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

    if dry_run:
        echo_notice("This is a dry run. Skip downloading and exit.")
    else:
        # Absolute output path of an excerpt without extension.
        final_output_path: Path

        if preview_mode:
            default_output_path = ctx.obj.config.traverse(
                "options.download.output_path"
            )
            if str(output_path) == default_output_path:
                output_path = Path("{{ title|adjust }}_{{ id }}_preview")

        if check_is_template(str(output_path)):
            input_timezone = requested_date_interval.start.tzinfo
            template_context: DownloadOutputPathContext = {
                "id": playback.video_id,
                "title": sanitize_for_filename(playback.info.title),
                "audio_stream": audio_stream,
                "video_stream": video_stream,
                "input_start_date": requested_date_interval.start,
                "input_end_date": requested_date_interval.end,
                "actual_start_date": (
                    actual_date_interval.start.astimezone(input_timezone)
                ),
                "actual_end_date": actual_date_interval.end.astimezone(input_timezone),
                "duration": requested_end_date - requested_start_date,
            }
            final_output_path = render_template(
                output_path,
                ctx.obj.jinja_environment,
                template_context,
            )
        else:
            final_output_path = output_path
        final_output_path = resolve_output_path(final_output_path)

        if preview_mode:
            segments_output_directory = playback.get_temp_directory()
        elif segments_output_dir_option:
            segments_output_directory = segments_output_dir_option
        elif keep_segments or no_merge:
            segments_output_directory = final_output_path
        else:
            segments_output_directory = resume_file_path.with_name(
                f"{resume_file_path.stem}"
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
                    "\nUse '--segments-output-dir {}' or '--ignore-resume'.".format(
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

        if not resume_run and not preview_mode:
            with open(resume_file_path, "wb") as f:
                logger.debug("Write resume file to %s", resume_file_path)
                to_pickle = {
                    "interval": rewind_interval,
                    "segments_output_directory": segments_output_directory,
                }
                pickle.dump(to_pickle, f)

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
            do_download_segments()
            click.echo(
                "\nSuccess! Segments saved to '{}'.".format(
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

            do_download_segments()
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

            if cut:
                click.echo("2. Merging segments (cut requested)... ", nl=False)
            else:
                click.echo("2. Merging segments (may take a while)... ", nl=False)

            metadata_tags: dict[str, Any] = {}
            if not no_metadata:

                def _convert_date_to_isostring(date: datetime) -> str:
                    iso_date = date.astimezone(timezone.utc)
                    return iso_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                metadata_date_converter: Callable[[datetime], str]
                match ctx.obj.config.traverse("output.metadata.dates"):
                    case "unix":
                        metadata_date_converter = lambda d: f"{d.timestamp():.6f}"
                    case "iso":
                        metadata_date_converter = _convert_date_to_isostring
                    case _ as value:
                        click.echo()
                        logger.warning(
                            f"Unknown 'output.metadata.dates = {value}' config value, "
                            "fallback to 'iso'"
                        )
                        metadata_date_converter = _convert_date_to_isostring

                metadata_context: MetadataTagsContext = {
                    "title": playback.info.title,
                    "author": playback.info.author,
                    "comment": playback.video_url,
                    "input_start_date": metadata_date_converter(
                        requested_date_interval.start
                    ),
                    "input_end_date": metadata_date_converter(
                        requested_date_interval.end
                    ),
                    "actual_start_date": metadata_date_converter(
                        actual_date_interval.start
                    ),
                    "actual_end_date": metadata_date_converter(
                        actual_date_interval.end
                    ),
                    "start_segment": str(rewind_interval.start.sequence),
                    "end_segment": str(rewind_interval.end.sequence),
                }

            merged_path = merge_segments(
                audio_and_video_segment_paths[0],
                audio_and_video_segment_paths[1],
                output_directory=final_output_path.parent,
                output_stem=final_output_path.name,
                temp_directory=playback.get_temp_directory(),
                metadata_tags=metadata_context,
                **cut_kwargs,
            )

            click.echo("done.\n")
            click.echo(f"Success! Saved to '{try_get_relative_path(merged_path)}'.")

            if keep_segments and not preview_mode:
                click.echo(
                    "~ Segments are kept in '{}'.".format(
                        try_get_relative_path(segments_output_directory)
                    )
                )

    run_temp_directory = playback.get_temp_directory()
    if keep_temp:
        echo_notice(f"No cleanup enabled, check {run_temp_directory}")
    else:
        try:
            shutil.rmtree(run_temp_directory)
        except OSError:
            logger.warning(
                "Failed to remove temporary directory: %s", run_temp_directory
            )

    if not dry_run and not preview_mode:
        resume_file_path.unlink()

    if not (dry_run or keep_segments or preview_mode):
        try:
            for paths in audio_and_video_segment_paths:
                for path in paths:
                    path.unlink()
        except OSError:
            logger.warning("Could not remove segment: %s", path)
        try:
            if need_to_remove_segments_directory:
                logger.debug(
                    "Remove segments directory: %s",
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
