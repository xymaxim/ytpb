import email
import logging
import sys
import textwrap
from datetime import datetime, timedelta

import click
import requests

from ytpb.fetchers import YoutubeDLInfoFetcher, YtpbInfoFetcher
from ytpb.info import BroadcastStatus
from ytpb.download import compose_default_segment_filename
from ytpb.exceptions import (
    BadCommandArgument,
    QueryError,
    BroadcastStatusError,
    CachedItemNotFoundError,
    SegmentDownloadError,
    SequenceLocatingError,
)
from ytpb.segment import Segment
from ytpb.playback import Playback
from ytpb.types import DateInterval, SequenceRange, SetOfStreams
from ytpb.cli.custom import get_parameter_by_name
from ytpb.utils.date import format_timedelta, round_date
from ytpb.utils.url import normalize_video_url, extract_parameter_from_url
from ytpb.utils.remote import request_reference_sequence

logger = logging.getLogger(__name__)


CONSOLE_TEXT_WIDTH = 80
EARLIEST_DATE_TIMEDELTA = timedelta(days=6, hours=23)


def create_playback(ctx: click.Context) -> Playback:
    stream_url = ctx.params["stream_url"]

    if ctx.params["yt_dlp"]:
        fetcher = YoutubeDLInfoFetcher(stream_url)
    else:
        fetcher = YtpbInfoFetcher(stream_url)

    try:
        click.echo(f"Run playback for {stream_url}")
        click.echo("(<<) Collecting info about the video...")

        if ctx.params["no_cache"]:
            playback = Playback.from_url(
                stream_url, fetcher=fetcher, write_to_cache=False
            )
        elif ctx.params["force_update_cache"]:
            playback = Playback.from_url(
                stream_url, fetcher=fetcher, write_to_cache=True
            )
        else:
            try:
                playback = Playback.from_cache(stream_url, fetcher=fetcher)
            except CachedItemNotFoundError:
                logger.debug("Couldn't find unexpired cached item for the video")
                playback = Playback.from_url(
                    stream_url, fetcher=fetcher, write_to_cache=True
                )
    except BroadcastStatusError as e:
        match e.status:
            case BroadcastStatus.NONE:
                click.echo("It's seems that the video is not a live stream", err=True)
            case BroadcastStatus.COMPLETED:
                click.echo("Stream was live, but now it's finished", err=True)
        sys.exit(1)

    click.echo(f"Stream '{playback.info.title}' is alive!")

    return playback


def normalize_stream_url(ctx: click.Context, param: click.Argument, value: str) -> str:
    try:
        return normalize_video_url(value)
    except BadCommandArgument as e:
        raise click.BadParameter(str(e))


def check_end_options(start, end, duration, preview):
    if not (end or duration or preview):
        raise click.UsageError(
            "One of --end, --duration, or --preview must be specified."
        )

    if isinstance(end, datetime) and isinstance(start, datetime):
        if end <= start:
            raise click.BadParameter(
                "End date is ahead or equal to the start date.",
                param_hint="'-e' / '--end'"
            )


def get_downloaded_segment(playback, sequence, base_url):
    segment_filename = compose_default_segment_filename(sequence, base_url)
    segment = Segment.from_file(playback.get_temp_directory() / segment_filename)
    return segment


def _prepare_line_for_summary_info(
    date: datetime,
    input_actual_timedelta: timedelta,
    use_ms_precision: bool = False,
) -> str:
    if not use_ms_precision:
        date = round_date(date)
    date_diff_string = format_timedelta(input_actual_timedelta, use_ms_precision)

    formatted = email.utils.format_datetime(date).split(", ")[1]
    if use_ms_precision:
        date_part, tz_part = formatted[:-6], formatted[-5:]
        ms_value = f"{date.microsecond // 1000:03g}"
        formatted = f"{date_part}.{ms_value} {tz_part}"

    if date_diff_string[1:] != "00:00":
        output = f"{formatted} ({date_diff_string})"
    else:
        output = formatted

    return output


def print_summary_info(
    input_date_interval: DateInterval,
    actual_date_interval: DateInterval,
    rewind_range: SequenceRange,
    use_ms_precision: bool = False,
) -> None:
    input_tzinfo = input_date_interval.start.tzinfo

    start_time_info_line = _prepare_line_for_summary_info(
        actual_date_interval.start.astimezone(input_tzinfo),
        actual_date_interval.start - input_date_interval.start,
        use_ms_precision,
    )
    click.echo(f"Actual start: {start_time_info_line}, seq. {rewind_range.start}")

    end_time_info_line = _prepare_line_for_summary_info(
        actual_date_interval.end.astimezone(input_tzinfo),
        actual_date_interval.end - input_date_interval.end,
        use_ms_precision,
    )
    click.echo(f"  Actual end: {end_time_info_line}, seq. {rewind_range.end}")

    # total_duration = format_duration(
    #     timedelta(seconds=actual_date_interval.duration),
    #     DurationFormatPattern.ISO8601_LIKE
    # )
    # click.echo(f"Total duration: {total_duration}, estimated size: ?")


def check_streams_not_empty(
    audio_stream, audio_format, video_stream, video_format, max_text_width=62
):
    if audio_format and not audio_stream:
        message = (
            "  Error! Found no audio formats matching requested format spec: "
            f"{audio_format}."
        )
        if video_format and not video_stream:
            message += " Same for the video: {video_format}."
        click.echo(textwrap.fill(message, max_text_width))
        click.echo("~" * max_text_width)
        sys.exit(1)
    elif video_format and not video_stream:
        click.echo("~" * max_text_width)
        message = (
            "  Error! Found no video formats matching requested format spec: "
            f"{video_format}."
        )
        click.echo(textwrap.fill(message, max_text_width))
        click.echo("~" * max_text_width)
        sys.exit(1)


def query_streams_or_exit(
    streams: SetOfStreams, format_spec: str, param: str | None = None
) -> SetOfStreams:
    try:
        queried_streams = streams.query(format_spec)
    except QueryError as e:
        click.secho(f"error: Invalid value for {param}. {e}: '{format_spec}'", err=True)
        sys.exit(1)
    if not queried_streams:
        message = f"No streams found matching {param} format spec: '{format_spec}'"
        click.echo(message, err=True)
        sys.exit(1)
    return queried_streams


def raise_for_start_sequence_too_far(sequence: int, current_sequence: int, base_url: str) -> None:
    segment_duration = int(float(extract_parameter_from_url("dur", base_url)))
    earliest_sequence = (
        current_sequence - EARLIEST_DATE_TIMEDELTA.total_seconds() // segment_duration
    )
    if sequence <= earliest_sequence:
        click.echo("\n")
        message = "Start sequence number is beyond the limit of 7 days."
        raise click.BadParameter(message, param_hint="'-s' / '--start'")

    
def raise_for_sequence_ahead_of_current(sequence, current_sequence: int, ctx: click.Context, param_name: str) -> None:
    if sequence >= current_sequence:
        click.echo("\n")
        message = (
            "Sequence number is ahead or equal to the current one: "
            f"{sequence} >= {current_sequence}"
        )
        param = get_parameter_by_name(param_name, ctx)
        raise click.BadParameter(message, ctx, param)
