import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
import cloup
import structlog
from cloup.constraints import constraint, require_any
from rich import box
from rich.console import Console
from rich.table import Table

from ytpb import types
from ytpb.actions.compose import compose_static_mpd, refresh_mpd
from ytpb.cli.common import (
    CONSOLE_TEXT_WIDTH,
    create_playback,
    print_summary_info,
    query_streams_or_exit,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    resolve_output_path,
    stream_argument,
)
from ytpb.cli.options import (
    cache_options,
    interval_option,
    validate_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType
from ytpb.cli.templating import (
    check_is_template,
    IntervalOutputPathContext,
    MinimalOutputPathContext,
    render_template,
)
from ytpb.cli.utils.date import express_timedelta_in_words
from ytpb.cli.utils.path import sanitize_for_filename
from ytpb.errors import BroadcastStatusError
from ytpb.fetchers import YoutubeDLInfoFetcher, YtpbInfoFetcher
from ytpb.info import BroadcastStatus
from ytpb.playback import Playback
from ytpb.representations import extract_representations
from ytpb.streams import Streams
from ytpb.types import DateInterval, SegmentSequence
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.url import build_video_url_from_base_url, extract_parameter_from_url

logger = structlog.get_logger(__name__)


class MPDOutputPathContext(MinimalOutputPathContext, IntervalOutputPathContext): ...


def print_audio_table(console, streams, **table_kwargs):
    table = Table(title="(Audio)", **table_kwargs)
    for name in ("itag", "Format", "Codec", "Sampling"):
        if name == "itag":
            table.add_column(" " + name, ratio=0.2, justify="center")
        else:
            table.add_column(name, ratio=(1 - 0.2) / 3)
    for s in sorted(streams, key=lambda x: (x.audio_sampling_rate, x.itag)):
        table.add_row(s.itag, s.format, s.codecs, f"{s.audio_sampling_rate} Hz")
    console.print(table)


def print_video_table(console, streams, **table_kwargs):
    table = Table(title="(Video)", **table_kwargs)
    for name in ("itag", "Format", "Codec", "Quality"):
        if name == "itag":
            table.add_column(" " + name, ratio=0.2, justify="center")
        else:
            table.add_column(name, ratio=(1 - 0.2) / 3)
    for s in sorted(streams, key=lambda x: (x.codecs, x.quality, x.itag)):
        table.add_row(s.itag, s.format, s.codecs, str(s.quality))
    console.print(table)


@cloup.group("mpd", short_help="Compose MPEG-DASH manifests.")
def mpd_group():
    pass


@mpd_group.command(
    "compose",
    help="Compose an MPEG-DASH manifest.",
)
@cloup.option_group(
    "Input options",
    interval_option,
    cloup.option(
        "-af",
        "--audio-formats",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.AUDIO),
        help="Audio format(s) to include.",
    ),
    cloup.option(
        "-vf",
        "--video-formats",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.VIDEO),
        help="Video format(s) to include.",
    ),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Output path (with extension).",
    callback=validate_output_path(MPDOutputPathContext),
)
@yt_dlp_option
@cache_options
@stream_argument
@constraint(require_any, ["audio_formats", "video_formats"])
@click.pass_context
def compose_command(
    ctx: click.Context,
    interval: types.PointInStream,
    audio_formats: str,
    video_formats: str,
    output_path: Path,
    force_update_cache: bool,
    no_cache: bool,
    yt_dlp: bool,
    stream_url: str,
) -> int:
    playback = create_playback(ctx)

    queried_audio_streams = []
    if audio_formats:
        queried_audio_streams = query_streams_or_exit(
            playback.streams, audio_formats, "--audio-formats"
        )

    queried_video_streams = []
    if video_formats:
        queried_video_streams = query_streams_or_exit(
            playback.streams, video_formats, "--video-formats"
        )

    number_of_streams = len(queried_audio_streams) + len(queried_video_streams)
    if number_of_streams == 1:
        click.echo("This representation will be in the manifest:")
    else:
        click.echo(
            f"These {number_of_streams} representations will be in the manifest:"
        )

    console = Console(width=CONSOLE_TEXT_WIDTH)

    table_kwargs = {
        "box": box.MARKDOWN,
        "padding": (0, 1, 0, 1),
        "show_edge": False,
        "title_style": "italic",
        "header_style": None,
        "expand": True,
        "width": 60,
    }

    if queried_audio_streams:
        print_audio_table(console, queried_audio_streams, **table_kwargs)
    if queried_video_streams:
        print_video_table(console, queried_video_streams, **table_kwargs)
    click.echo()

    reference_stream = (queried_video_streams or queried_audio_streams)[0]
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

    if isinstance(requested_end, SegmentSequence):
        raise_for_sequence_ahead_of_current(
            requested_end, head_sequence, ctx, "interval"
        )
    if requested_end == "now":
        requested_end = head_sequence - 1

    click.echo("(<<) Locating start and end in the stream... ", nl=False)
    rewind_interval = playback.locate_interval(
        requested_start, requested_end, reference_stream
    )
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

    print_summary_info(requested_date_interval, actual_date_interval, rewind_interval)
    click.echo()

    # Absolute output path of a manifest with extension.
    final_output_path: Path
    if check_is_template(str(output_path)):
        input_timezone = requested_date_interval.start.tzinfo
        template_context: MPDOutputPathContext = {
            "id": playback.video_id,
            "title": sanitize_for_filename(playback.info.title),
            "input_start_date": requested_date_interval.start,
            "input_end_date": requested_date_interval.end,
            "actual_start_date": actual_date_interval.start.astimezone(input_timezone),
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

    click.echo("(<<) Composing MPEG-DASH manifest...")
    streams = Streams(queried_audio_streams + queried_video_streams)
    composed_manifest = compose_static_mpd(playback, rewind_interval, streams)

    with open(final_output_path, "w", encoding="utf-8") as f:
        f.write(composed_manifest)

    try:
        saved_to_path_value = f"{final_output_path.relative_to(Path.cwd())}"
    except ValueError:
        saved_to_path_value = final_output_path

    click.echo(f"Success! Saved to '{saved_to_path_value}'.")
    click.echo("~ Note that the manifest will expire in 6 hours.")


@mpd_group.command(
    "refresh",
    help="Refresh a composed MPEG-DASH manifest.",
)
@yt_dlp_option
@cloup.argument("manifest", help="Manifest file to refresh.")
def refresh_command(
    yt_dlp: bool,
    manifest: str,
) -> int:
    with open(manifest, "r", encoding="utf-8") as f:
        manifest_content = f.read()

    list_of_streams = extract_representations(manifest_content)
    stream_url = build_video_url_from_base_url(list_of_streams[0].base_url)

    if yt_dlp:
        fetcher = YoutubeDLInfoFetcher(stream_url)
    else:
        fetcher = YtpbInfoFetcher(stream_url)

    try:
        playback = Playback.from_url(stream_url, fetcher=fetcher, write_to_cache=False)
    except BroadcastStatusError as e:
        match e.status:
            case BroadcastStatus.COMPLETED:
                click.echo("Stream was live, but now it's finished", err=True)
        sys.exit(1)

    refreshed = refresh_mpd(manifest_content, playback.streams)
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(refreshed)

    some_base_url = next(iter(playback.streams)).base_url
    expires_at_time = int(extract_parameter_from_url("expire", some_base_url))
    expires_at_date = datetime.fromtimestamp(expires_at_time)
    expires_in = express_timedelta_in_words(expires_at_date - datetime.now())

    click.echo(f"Success! Manifest has been refreshed, and expires in {expires_in}.")
