import email
import shutil
import sys
from datetime import datetime
from pathlib import Path

import click
import cloup
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
from timedelta_isoformat import timedelta

from ytpb.actions.capture import capture_frame
from ytpb.cli.commands.download import render_download_output_path_context

from ytpb.cli.common import (
    create_playback,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    resolve_output_path,
    stream_argument,
)
from ytpb.cli.custom import get_parameter_by_name
from ytpb.cli.options import (
    boundary_options,
    cache_options,
    no_cleanup_option,
    validate_image_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType, InputRewindInterval
from ytpb.download import download_segment
from ytpb.exceptions import QueryError, SegmentDownloadError, SequenceLocatingError
from ytpb.locate import SequenceLocator
from ytpb.segment import Segment
from ytpb.types import AddressableMappingProtocol, DateInterval, SegmentSequence
from ytpb.utils.date import DurationFormatPattern, format_duration
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.path import (
    expand_template_output_path,
    IntervalOutputPathContext,
    MinimalOutputPathContext,
    OUTPUT_PATH_PLACEHOLDER_RE,
)
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.units import S_TO_MS

logger = structlog.get_logger(__name__)


class TimelapseOutputPathContext(MinimalOutputPathContext, IntervalOutputPathContext):
    every: timedelta


def render_timelapse_output_path_context(
    context: TimelapseOutputPathContext,
    config_settings: AddressableMappingProtocol,
) -> TimelapseOutputPathContext:
    output = context
    for variable in TimelapseOutputPathContext.__annotations__.keys():
        match variable:
            case "every" as x:
                output[x] = context[x].isoformat().replace("P", "E")

    output.update(render_download_output_path_context(context, config_settings))

    return output


def convert_every_option_to_timedelta(
    ctx: click.Context, param: click.Option, value: str
) -> timedelta:
    try:
        output = timedelta.fromisoformat(f"PT{value}")
    except ValueError:
        raise click.BadParameter(
            "Couldn't match repetetion format, e.g.: '30S', '1DT2H3M4S'."
        )
    return output


def print_timelapse_summary_info(
    dates: list[datetime], end_date: datetime, every: timedelta
) -> None:
    click.echo(
        "Every {} a time-lapse frame will be captured:".format(
            format_duration(every, DurationFormatPattern.ISO8601_LIKE)
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


def create_capturing_progress_bar():
    return Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=32),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("eta"),
        TimeRemainingColumn(),
        console=Console(),
    )


@cloup.command("timelapse", help="Take a timelapse capture.")
@cloup.option_group(
    "Input options",
    boundary_options,
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
@no_cleanup_option
@cache_options
@stream_argument
@click.pass_context
def timelapse_command(
    ctx: click.Context,
    interval: InputRewindInterval,
    preview: bool,
    every: timedelta,
    video_format: str,
    output: Path,
    yt_dlp: bool,
    no_cleanup: bool,
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
        rewind_range = playback.locate_rewind_range(
            requested_start,
            requested_end,
            itag=reference_stream.itag,
        )
    except SequenceLocatingError:
        message = "\nerror: An error occured during segment locating, exit."
        click.echo(message, err=True)
        sys.exit(1)

    click.echo("done.")

    for point in (requested_start, requested_end):
        if type(point) is SegmentSequence:
            sequence = point
            try:
                download_segment(
                    sequence,
                    reference_base_url,
                    output_directory=playback.get_temp_directory(),
                    session=playback.session,
                    force_download=False,
                )
            except SegmentDownloadError as exc:
                click.echo()
                logger.error(exc, sequence=exc.sequence, exc_info=True)
                sys.exit(1)

    start_segment = playback.get_downloaded_segment(
        rewind_range.start, reference_base_url
    )
    try:
        end_segment = playback.get_downloaded_segment(
            rewind_range.end, reference_base_url
        )
    except FileNotFoundError:
        downloaded_path = download_segment(
            rewind_range.end,
            reference_base_url,
            playback.get_temp_directory(),
            session=playback.session,
        )
        end_segment = Segment.from_file(downloaded_path)

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

    start_diff, end_diff = requested_date_interval - actual_date_interval

    cut_at_start_s = start_diff if start_diff > 0 else 0
    cut_at_end_s = abs(end_diff) if end_diff < 0 else 0
    {
        "cut_at_start": round(cut_at_start_s * int(S_TO_MS)),
        "cut_at_end": round(cut_at_end_s * int(S_TO_MS)),
    }
    actual_date_interval = DateInterval(
        start=actual_date_interval.start + timedelta(seconds=cut_at_start_s),
        end=actual_date_interval.end - timedelta(seconds=cut_at_end_s),
    )

    s = requested_date_interval.start
    e = requested_date_interval.end
    dates_to_capture = [s + every * i for i in range((e - s) // every + 1)]

    print_timelapse_summary_info(dates_to_capture, requested_date_interval.end, every)

    if preview:
        click.echo("info: Preview mode is enabled, only first 3 frames will be taken.")

    click.echo()

    if preview:
        dates_to_capture = dates_to_capture[:3]

    length_of_timelapse = len(dates_to_capture)

    # Absolute output path of images with a numeric pattern.
    final_output_path: Path
    if OUTPUT_PATH_PLACEHOLDER_RE.search(str(output_path)):
        input_timezone = requested_date_interval.start.tzinfo
        template_context: TimelapseOutputPathContext = {
            "id": playback.video_id,
            "title": playback.info.title,
            "input_start_date": requested_date_interval.start,
            "input_end_date": requested_date_interval.end,
            "actual_start_date": actual_date_interval.start.astimezone(input_timezone),
            "actual_end_date": actual_date_interval.end.astimezone(input_timezone),
            "duration": requested_end_date - requested_start_date,
            "every": every,
        }
        expand_template_output_path(
            output_path,
            template_context,
            render_timelapse_output_path_context,
            ctx.obj.config,
        )
    else:
        final_output_path = output_path
    final_output_path = resolve_output_path(final_output_path)

    click.echo("(<<) Capturing frames as images:")

    capturing_progress = create_capturing_progress_bar()
    capturing_task = capturing_progress.add_task("", total=len(dates_to_capture))

    def _save_frame_as_image(
        segment: Segment, target_date: datetime, output_path_pattern: Path, i: int
    ) -> None:
        target_offset = target_date - segment.ingestion_start_date
        image = capture_frame(segment.local_path, target_offset)
        image_output_name = output_path_pattern.name % i
        image_output_path = output_path_pattern.with_name(image_output_name)
        image.save(image_output_path, quality=80)

    with capturing_progress:
        # Save the first frame of a time-lapse, a frame of the located start segment.
        _save_frame_as_image(start_segment, requested_start_date, final_output_path, 0)
        capturing_progress.advance(capturing_task)

        previous_sequence = start_segment.sequence
        for i, target_date in enumerate(dates_to_capture[1:], 1):
            # First, locate a segment by a target date.
            sl = SequenceLocator(
                reference_base_url,
                reference_sequence=previous_sequence,
                temp_directory=playback.get_temp_directory(),
                session=playback.session,
            )
            is_end = i == length_of_timelapse - 1
            found_sequence = sl.find_sequence_by_time(
                target_date.timestamp(), end=is_end
            )
            previous_sequence = found_sequence

            try:
                segment = playback.get_downloaded_segment(
                    found_sequence, reference_base_url
                )
            except FileNotFoundError:
                downloaded_path = download_segment(
                    found_sequence,
                    reference_base_url,
                    playback.get_temp_directory(),
                    session=playback.session,
                )
                segment = Segment.from_file(downloaded_path)

            # And save a desired frame as i-th image of a time-lapse.
            _save_frame_as_image(segment, target_date, final_output_path, i)

            capturing_progress.advance(capturing_task)

    try:
        saved_to_path_value = final_output_path.parent.relative_to(Path.cwd())
    except ValueError:
        saved_to_path_value = final_output_path.parent
    click.echo(f"\nSuccess! Saved to '{saved_to_path_value}/'.")

    run_temp_directory = playback.get_temp_directory()
    if no_cleanup:
        click.echo(f"notice: No cleanup enabled, check {run_temp_directory}/")
    else:
        try:
            shutil.rmtree(run_temp_directory)
        except OSError:
            logger.warning(
                "Failed to remove %s temporary directory", run_temp_directory
            )
