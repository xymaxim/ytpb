import email
import os
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

import click
import cloup
import structlog

from ytpb.download import compose_default_segment_filename
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
from ytpb.segment import Segment
from ytpb.types import DateInterval, SetOfStreams
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
        if from_manifest := ctx.params.get("from_manifest"):
            try:
                click.echo("Run playback from manifest file")
                playback = Playback.from_manifest(from_manifest, fetcher=fetcher)
            except BaseUrlExpiredError:
                click.echo("Oh no, the manifest has been expired, exit.", err=True)
                sys.exit(1)
        else:
            click.echo(f"Run playback for {stream_url}")
            click.echo("(<<) Collecting info about the video...")

            force_update_cache = ctx.params.get("force_update_cache", False)
            need_read_cache = not (
                ctx.params.get("no_cache", True) or force_update_cache
            )
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


def check_end_options(start, end, duration, preview):
    if not (end or duration or preview):
        raise click.UsageError(
            "One of --end, --duration, or --preview must be specified."
        )

    if isinstance(end, datetime) and isinstance(start, datetime):
        if end <= start:
            raise click.BadParameter(
                "End date is ahead or equal to the start date.",
                param_hint="'-e' / '--end'",
            )


def get_downloaded_segment(playback, sequence, base_url):
    segment_filename = compose_default_segment_filename(sequence, base_url)
    segment = Segment.from_file(playback.get_temp_directory() / segment_filename)
    return segment


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

    # total_duration = format_duration(
    #     timedelta(seconds=actual_date_interval.duration),
    #     DurationFormatPattern.IN_SENTENCE
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
