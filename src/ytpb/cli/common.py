import email
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
import cloup
import structlog

from ytpb.errors import (
    BadCommandArgument,
    BaseUrlExpiredError,
    BroadcastStatusError,
    CachedItemNotFoundError,
    QueryError,
)
from ytpb.fetchers import YoutubeDLInfoFetcher, YtpbInfoFetcher
from ytpb.info import BroadcastStatus
from ytpb.playback import Playback, RewindInterval
from ytpb.types import DateInterval, SegmentSequence, SetOfStreams
from ytpb.utils.date import format_timedelta, round_date
from ytpb.utils.url import extract_parameter_from_url, normalize_video_url

logger = structlog.getLogger(__name__)


CONSOLE_TEXT_WIDTH = 80
EARLIEST_DATE_TIMEDELTA = timedelta(days=6, hours=23)


def get_parameter_by_name(name: str, ctx: click.Context) -> click.Parameter:
    return next((p for p in ctx.command.params if p.name == name), None)


def create_playback(ctx: click.Context) -> Playback:
    stream_url = ctx.params["stream_url"]

    if ctx.params["yt_dlp"]:
        fetcher = YoutubeDLInfoFetcher(stream_url)
    else:
        fetcher = YtpbInfoFetcher(stream_url)

    try:
        click.echo(f"Run playback for {stream_url}")
        click.echo("(<<) Collecting info about the video...")

        force_update_cache = ctx.params.get("force_update_cache", False)
        need_read_cache = not (ctx.params.get("no_cache", True) or force_update_cache)
        if need_read_cache:
            try:
                playback = Playback.from_cache(stream_url, fetcher=fetcher)
            except CachedItemNotFoundError:
                logger.debug("Could not find unexpired cached item for the video")
                playback = Playback.from_url(
                    stream_url, fetcher=fetcher, write_to_cache=True
                )
        else:
            playback = Playback.from_url(
                stream_url, fetcher=fetcher, write_to_cache=force_update_cache
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


stream_argument = cloup.argument(
    "stream_url",
    metavar="STREAM",
    help="Stream URL or video ID.",
    callback=normalize_stream_url,
)


def prepare_line_for_summary_info(
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
    rewind_interval: RewindInterval,
    use_ms_precision: bool = False,
) -> None:
    input_tzinfo = input_date_interval.start.tzinfo

    start_time_info_line = prepare_line_for_summary_info(
        actual_date_interval.start.astimezone(input_tzinfo),
        actual_date_interval.start - input_date_interval.start,
        use_ms_precision,
    )
    click.echo(
        "Actual start: {}, seq. {}".format(
            start_time_info_line, rewind_interval.start.sequence
        )
    )

    end_time_info_line = prepare_line_for_summary_info(
        actual_date_interval.end.astimezone(input_tzinfo),
        actual_date_interval.end - input_date_interval.end,
        use_ms_precision,
    )
    click.echo(
        "  Actual end: {}, seq. {}".format(
            end_time_info_line, rewind_interval.end.sequence
        )
    )


def query_streams_or_exit(
    streams: SetOfStreams,
    format_spec: str,
    param: str | None = None,
    allow_empty: bool = False,
    allow_many: bool = True,
) -> SetOfStreams:
    try:
        queried_streams = streams.query(format_spec)
    except QueryError as exc:
        message = f"error: Invalid value for '{param}'. {exc}: '{format_spec}'"
        click.echo(message, err=True)
        sys.exit(1)

    if queried_streams:
        if len(queried_streams) > 1 and not allow_many:
            logger.error(
                "Too many queried streams", itags=[s.itag for s in queried_streams]
            )
            click.echo(
                (
                    "error: Format spec is ambiguous: '{format_spec}'.\n\n"
                    "Found more than one stream matched a format spec. Please be more "
                    "explicit, or try 'yt-dlp --live-from-start -F ...' first."
                )
            )
            sys.exit(1)
    elif not allow_empty:
        message = (
            f"error: No streams found matching '{param}' format spec: '{format_spec}'"
        )
        click.echo(message, err=True)
        sys.exit(1)

    return queried_streams


def find_earliest_sequence(
    playback: Playback, head_sequence: SegmentSequence, head_date: datetime
) -> SegmentSequence:
    """Finds the earliest available segment sequence number.

    Note that the function returns not the most earliest available sequence
    number, but the safe one, which is close to the 7-days availability limit.
    """
    safe_offset = timedelta(days=1)

    some_stream = next(iter(playback.streams))
    segment_duration = float(extract_parameter_from_url("dur", some_stream.base_url))

    safe_jump_timedelta = EARLIEST_DATE_TIMEDELTA - safe_offset
    first_jump = int(safe_jump_timedelta.total_seconds() // segment_duration)
    first_sequence = head_sequence - first_jump
    if first_sequence <= 0:
        return 0

    first_segment = playback.get_segment(first_sequence, some_stream)
    first_date = first_segment.ingestion_start_date

    second_jump_timedelta = first_date - (head_date - EARLIEST_DATE_TIMEDELTA)
    second_jump = int(second_jump_timedelta.total_seconds() // segment_duration)

    result = first_sequence - second_jump
    if result <= 0:
        return 0

    return result


def raise_for_too_far_sequence(
    sequence: int,
    current_sequence: int,
    base_url: str,
    ctx: click.Context,
    param_name: str,
) -> None:
    segment_duration = int(float(extract_parameter_from_url("dur", base_url)))
    earliest_sequence = (
        current_sequence - EARLIEST_DATE_TIMEDELTA.total_seconds() // segment_duration
    )
    if sequence <= earliest_sequence:
        click.echo("\n")
        raise click.BadParameter(
            f"Sequence number is beyond the limit of 7 days: {sequence}",
            param=get_parameter_by_name(param_name, ctx),
        )


def raise_for_sequence_ahead_of_current(
    sequence, current_sequence: int, ctx: click.Context, param_name: str
) -> None:
    if sequence >= current_sequence:
        click.echo("\n")
        message = (
            "Sequence number is ahead or equal to the current one: "
            f"{sequence} >= {current_sequence}"
        )
        param = get_parameter_by_name(param_name, ctx)
        raise click.BadParameter(message, ctx, param)


def resolve_output_path(output_path: Path) -> Path:
    resolved_path = Path(output_path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return resolved_path


def suppress_output() -> None:
    sys.stdout = open(os.devnull, "w")


def echo_notice(message: str) -> None:
    click.echo(f"~ {message}")
