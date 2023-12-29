import sys
from datetime import datetime
from pathlib import Path
from textwrap import fill

import click
import cloup
import structlog
from PIL import Image
from timedelta_isoformat import timedelta

from ytpb.cli.common import (
    create_playback,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    stream_argument,
)

from ytpb.cli.custom import get_parameter_by_name
from ytpb.cli.options import (
    boundary_options,
    cache_options,
    no_cleanup_option,
    validate_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType, InputRewindInterval
from ytpb.download import download_segment
from ytpb.exceptions import QueryError, SegmentDownloadError, SequenceLocatingError
from ytpb.locate import SequenceLocator
from ytpb.segment import Segment
from ytpb.types import DateInterval, SegmentSequence
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.units import S_TO_MS

logger = structlog.get_logger(__name__)


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


def validate_image_output_path(
    ctx: click.Context, param: click.Option, value: Path
) -> Path:
    if not value.suffix:
        raise click.BadParameter("File extension must be provided.")

    extensions = Image.registered_extensions()
    supported_extensions = {ext for ext, f in extensions.items() if f in Image.SAVE}
    if value.suffix not in supported_extensions:
        tip = fill("Choose one of: {}".format(", ".join(sorted(supported_extensions))))
        raise click.BadParameter(f"Format '{value.suffix}' is not supported.\n\n{tip}")

    return validate_output_path(ctx, param, value)


def print_timelapse_summary_info(dates: list[datetime], end_date: datetime) -> None:
    message = "Every ... a time-lapse frame will be captured as following:"
    click.echo(message)

    for i, date in enumerate(dates[:2]):
        click.echo("     Frame {}: {}".format(i + 1, dates[i].isoformat()))

    if len(dates) > 3:
        click.echo("              ...")

    if len(dates) > 2:
        click.echo("  Last frame: {}".format(dates[-1].isoformat()))

    click.echo("        (End) {}".format(end_date.isoformat()))


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
    type=click.Path(path_type=Path),
    help="Output image path (with extension).",
    default="<id>_<input_start_date>.jpg",
    callback=validate_image_output_path,
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
    click.echo("(<<) Locating start and end in the stream... ", nl=False)

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

    print_timelapse_summary_info(dates_to_capture, requested_date_interval.end)

    if preview:
        click.echo("info: Preview mode is enabled, only first 3 frames will be taken.")

    click.echo()

    if preview:
        dates_to_capture = dates_to_capture[:3]

    length_of_timelapse = len(dates_to_capture)

    sequences_to_download: list[int] = [start_segment.sequence]
    previous_sequence = sequences_to_download[0]
    for i, date in enumerate(dates_to_capture[1:], 1):
        sl = SequenceLocator(
            reference_base_url,
            reference_sequence=previous_sequence,
            temp_directory=playback.get_temp_directory(),
            session=playback.session,
        )
        is_end = i == length_of_timelapse - 1
        found_sequence = sl.find_sequence_by_time(date.timestamp(), end=is_end)
        sequences_to_download.append(found_sequence)
        previous_sequence = found_sequence
