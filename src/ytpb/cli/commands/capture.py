import email
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import click
import cloup
import structlog
from PIL import Image
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from timedelta_isoformat import timedelta as isotimedelta

from ytpb.actions.capture import capture_frames, extract_frame_as_image
from ytpb.cli.common import (
    create_playback,
    echo_notice,
    get_parameter_by_name,
    prepare_line_for_summary_info,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    resolve_output_path,
    stream_argument,
)
from ytpb.cli.options import (
    cache_options,
    interval_option,
    keep_temp_option,
    validate_image_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import (
    FormatSpecParamType,
    FormatSpecType,
    InputRewindInterval,
    PointInStreamParamType,
)
from ytpb.cli.templating import (
    check_is_template,
    IntervalOutputPathContext,
    MinimalOutputPathContext,
    render_template,
    VideoStreamOutputPathContext,
)
from ytpb.cli.utils.date import DurationFormatPattern, format_duration
from ytpb.cli.utils.path import sanitize_for_filename
from ytpb.errors import QueryError, SegmentDownloadError, SequenceLocatingError
from ytpb.locate import SegmentLocator
from ytpb.segment import Segment
from ytpb.types import AbsolutePointInStream, DateInterval, SegmentSequence
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.remote import request_reference_sequence

logger = structlog.get_logger(__name__)


class CaptureOutputPathContext(MinimalOutputPathContext, VideoStreamOutputPathContext):
    #: Date the frame was captured.
    moment_date: datetime


class TimelapseOutputPathContext(
    MinimalOutputPathContext, VideoStreamOutputPathContext, IntervalOutputPathContext
):
    #: Interval at wich frames are captured.
    every: timedelta


def convert_every_option_to_timedelta(
    ctx: click.Context, param: click.Option, value: str
) -> timedelta:
    try:
        output = isotimedelta.fromisoformat(f"PT{value}")
    except ValueError:
        raise click.BadParameter(
            "Couldn't match repetetion format, e.g.: '30S', '1DT2H3M4S', etc."
        )
    return output


def print_timelapse_summary_info(
    dates: list[datetime], end_date: datetime, every: timedelta
) -> None:
    click.echo(
        "Every {} a time-lapse frame will be captured:".format(
            format_duration(every, DurationFormatPattern.SENTENCE)
        )
    )

    def _format_datetime(x):
        return email.utils.format_datetime(x).split(", ")[1]

    click.echo("{:>12}: {} / S".format("Frame 1", _format_datetime(dates[0])))

    number_of_dates = len(dates)
    if number_of_dates == 2:
        click.echo("{:>12}: {}".format("Last frame", _format_datetime(dates[-1])))
    elif number_of_dates > 2:
        click.echo("{:>12}: {}".format("Frame 2", _format_datetime(dates[1])))
        if number_of_dates > 3:
            click.echo(f"{'':12}  {'...':^26}")
        click.echo("{:>12}: {}".format("Last frame", _format_datetime(dates[-1])))

    click.echo("{:>12}  {} / E".format("", _format_datetime(end_date)))


@cloup.group("capture", help="Capture a single or many frames.")
def capture_group():
    pass


@capture_group.command("frame", help="Capture a single frame.")
@cloup.option_group(
    "Input options",
    cloup.option(
        "-m",
        "--moment",
        metavar="MOMENT",
        type=PointInStreamParamType(allowed_literals=["now"]),
        help="Moment to capture.",
    ),
    cloup.option(
        "-vf",
        "--video-format",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.VIDEO),
        help="Video format to capture.",
    ),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Output path (with extension).",
    callback=validate_image_output_path(CaptureOutputPathContext),
)
@yt_dlp_option
@keep_temp_option
@cache_options
@stream_argument
@click.pass_context
def frame_command(
    ctx: click.Context,
    moment: AbsolutePointInStream | Literal["now"],
    video_format: str,
    output_path: Path,
    yt_dlp: bool,
    keep_temp: bool,
    force_update_cache: bool,
    no_cache: bool,
    stream_url: str,
):
    playback = create_playback(ctx)

    if video_format:
        logger.debug("Query video stream by format spec", spec=video_format)
        try:
            queried_video_streams = playback.streams.query(video_format)
        except QueryError as exc:
            click.echo(f"\nerror: Failed to query video streams. {exc}", err=True)
            sys.exit(1)
    else:
        queried_video_streams = []

    click.echo()
    click.echo("(<<) Locating a moment in the stream... ", nl=False)

    reference_stream = queried_video_streams[0]
    reference_base_url = reference_stream.base_url

    head_sequence = request_reference_sequence(reference_base_url, playback.session)

    match moment:
        case SegmentSequence() as sequence:
            raise_for_too_far_sequence(
                sequence, head_sequence, reference_base_url, ctx, "moment"
            )
            raise_for_sequence_ahead_of_current(sequence, head_sequence, ctx, "moment")
            moment_sequence = sequence
        case datetime() as date:
            try:
                sl = SegmentLocator(
                    reference_base_url,
                    temp_directory=playback.get_temp_directory(),
                    session=playback.session,
                )
                moment_sequence, *_ = sl.find_sequence_by_time(date.timestamp())
            except SequenceLocatingError:
                message = "\nerror: An error occured during segment locating, exit."
                click.echo(message, err=True)
                sys.exit(1)
        case "now":
            moment_sequence = head_sequence

    click.echo("done.")

    try:
        segment_path = playback.download_segment(moment_sequence, reference_stream)
        moment_segment = Segment.from_file(segment_path)
    except SegmentDownloadError as exc:
        click.echo()
        logger.error(exc, sequence=exc.sequence, exc_info=True)
        sys.exit(1)

    requested_moment_date: datetime
    match moment:
        case SegmentSequence() | "now":
            requested_moment_date = moment_segment.ingestion_start_date
        case datetime() as date:
            requested_moment_date = date

    # TODO: This should be expanded to take into account a case when a requested
    # date fall into a gap.
    actual_moment_date = requested_moment_date

    actual_moment_info_line = prepare_line_for_summary_info(
        actual_moment_date, actual_moment_date - requested_moment_date
    )

    click.echo(
        "Actual moment: {}, seq. {}".format(
            actual_moment_info_line, moment_segment.sequence
        )
    )

    # Absolute output path of an image with extension.
    final_output_path: Path
    if check_is_template(str(output_path)):
        template_context: CaptureOutputPathContext = {
            "id": playback.video_id,
            "title": sanitize_for_filename(playback.info.title),
            "video_stream": reference_stream,
            "moment_date": requested_moment_date,
        }
        final_output_path = render_template(
            output_path,
            ctx.obj.jinja_environment,
            template_context,
        )
    else:
        final_output_path = output_path
    final_output_path = resolve_output_path(final_output_path)

    image = extract_frame_as_image(moment_segment, requested_moment_date)
    image.save(final_output_path, quality=80)

    try:
        saved_to_path_value = final_output_path.relative_to(Path.cwd())
    except ValueError:
        saved_to_path_value = final_output_path
    click.echo(f"\nSuccess! Saved to '{saved_to_path_value}'.")

    run_temp_directory = playback.get_temp_directory()
    if keep_temp:
        echo_notice(f"No cleanup enabled, check {run_temp_directory}")
    else:
        try:
            shutil.rmtree(run_temp_directory)
        except OSError:
            logger.warning(
                "Failed to remove %s temporary directory", run_temp_directory
            )


@capture_group.command("timelapse", help="Capture time-lapse frames.")
@cloup.option_group(
    "Input options",
    interval_option,
    cloup.option(
        "-e",
        "--every",
        metavar="REPETITION",
        help="Capture frames every REPETITION.",
        type=str,
        callback=convert_every_option_to_timedelta,
        required=True,
    ),
    cloup.option(
        "-vf",
        "--video-format",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.VIDEO),
        help="Video format to capture.",
    ),
    cloup.option(
        "-p",
        "--preview",
        help="Run in preview mode.",
        is_flag=True,
    ),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Output path (with extension).",
    callback=validate_image_output_path(TimelapseOutputPathContext),
)
@yt_dlp_option
@keep_temp_option
@cache_options
@stream_argument
@click.pass_context
def timelapse_command(
    ctx: click.Context,
    interval: InputRewindInterval,
    every: timedelta,
    video_format: str,
    preview: bool,
    output_path: Path,
    yt_dlp: bool,
    keep_temp: bool,
    force_update_cache: bool,
    no_cache: bool,
    stream_url: str,
):
    playback = create_playback(ctx)

    if video_format:
        logger.debug("Query video stream by format spec", spec=video_format)
        try:
            queried_video_streams = playback.streams.query(video_format)
        except QueryError as exc:
            click.echo(f"\nerror: Failed to query video streams. {exc}", err=True)
            sys.exit(1)
    else:
        queried_video_streams = []

    click.echo()
    click.echo("(<<) Locating interval start (S) and end (E)... ", nl=False)

    reference_stream = queried_video_streams[0]
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

    try:
        rewind_interval = playback.locate_interval(
            requested_start, requested_end, reference_stream
        )
    except SequenceLocatingError:
        message = "\nerror: An error occured during segment locating, exit."
        click.echo(message, err=True)
        sys.exit(1)

    click.echo("done.")

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

    s, e = requested_date_interval.start, requested_date_interval.end
    dates_to_capture = [s + every * i for i in range((e - s) // every + 1)]

    print_timelapse_summary_info(dates_to_capture, requested_date_interval.end, every)

    if preview:
        click.echo()
        echo_notice("Preview mode enabled, only first 3 frames will be taken.")
        dates_to_capture = dates_to_capture[:3]

    click.echo()

    # Absolute output path of images with a numeric pattern.
    final_output_path: Path
    if check_is_template(str(output_path)):
        input_timezone = requested_date_interval.start.tzinfo
        template_context: TimelapseOutputPathContext = {
            "id": playback.video_id,
            "title": sanitize_for_filename(playback.info.title),
            "audio_stream": None,
            "video_stream": reference_stream,
            "input_start_date": requested_date_interval.start,
            "input_end_date": requested_date_interval.end,
            "actual_start_date": actual_date_interval.start.astimezone(input_timezone),
            "actual_end_date": actual_date_interval.end.astimezone(input_timezone),
            "duration": requested_end_date - requested_start_date,
            "every": every,
        }
        final_output_path = render_template(
            output_path,
            ctx.obj.jinja_environment,
            template_context,
        )
    else:
        final_output_path = output_path
    final_output_path = resolve_output_path(final_output_path)

    click.echo("(<<) Capturing frames as images:")

    capturing_progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=32),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("eta"),
        TimeRemainingColumn(),
        console=Console(),
    )
    capturing_task = capturing_progress.add_task("", total=len(dates_to_capture))

    def _save_ith_frame_as_image(
        image: Image, output_path_pattern: Path, i: int
    ) -> None:
        image_output_name = output_path_pattern.name % i
        image_output_path = output_path_pattern.with_name(image_output_name)
        image.save(image_output_path, quality=80)

    with capturing_progress:
        # Save the first frame of a time-lapse -- the start segment was already located.
        first_frame_image = extract_frame_as_image(start_segment, requested_start_date)
        _save_ith_frame_as_image(first_frame_image, final_output_path, 0)
        capturing_progress.advance(capturing_task)

        captured = capture_frames(
            playback, dates_to_capture[1:], reference_stream, start_segment.sequence
        )
        for i, (image, _) in enumerate(captured, 1):
            _save_ith_frame_as_image(image, final_output_path, i)
            capturing_progress.advance(capturing_task)

    try:
        saved_to_path_value = final_output_path.parent.relative_to(Path.cwd())
    except ValueError:
        saved_to_path_value = final_output_path.parent
    click.echo(f"\nSuccess! Saved to '{saved_to_path_value}'.")

    run_temp_directory = playback.get_temp_directory()
    if keep_temp:
        echo_notice(f"No cleanup enabled, check {run_temp_directory}")
    else:
        try:
            shutil.rmtree(run_temp_directory)
        except OSError:
            logger.warning(
                "Failed to remove %s temporary directory", run_temp_directory
            )
