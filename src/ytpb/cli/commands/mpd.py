import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
import cloup
from rich import box
from rich.console import Console
from rich.table import Table

from ytpb import types
from ytpb.cli import parameters
from ytpb.cli.commands.download import (
    DownloadOutputPathContext,
    render_download_output_path_context,
)
from ytpb.cli.common import (
    CONSOLE_TEXT_WIDTH,
    create_playback,
    get_downloaded_segment,
    print_summary_info,
    query_streams_or_exit,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    stream_argument,
)
from ytpb.cli.custom import OrderedGroup
from ytpb.cli.options import (
    boundary_options,
    cache_options,
    output_options,
    yt_dlp_option,
)
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType
from ytpb.compose import compose_mpd, refresh_mpd
from ytpb.download import download_segment
from ytpb.exceptions import BroadcastStatusError, CachedItemNotFoundError
from ytpb.fetchers import YoutubeDLInfoFetcher, YtpbInfoFetcher
from ytpb.info import BroadcastStatus
from ytpb.mpd import extract_representations_info
from ytpb.playback import Playback
from ytpb.segment import Segment
from ytpb.streams import Streams
from ytpb.types import DateInterval, SegmentSequence
from ytpb.utils.date import express_timedelta_in_words
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.path import expand_template_output_path, OUTPUT_PATH_PLACEHOLDER_RE
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.url import build_video_url_from_base_url, extract_parameter_from_url

logger = logging.getLogger(__name__)


MpdOutputPathContext = DownloadOutputPathContext
render_mpd_output_path_context = render_download_output_path_context


def print_audio_table(console, streams, **table_kwargs):
    table = Table(title="(Audio)", **table_kwargs)
    for name in ("itag", "Format", "Codec", "Sampling"):
        if name == "itag":
            table.add_column(" " + name, ratio=20, justify="center")
        else:
            table.add_column(name, ratio=(100 - 20) / 3)
    for s in sorted(streams, key=lambda x: (x.audio_sampling_rate, x.itag)):
        table.add_row(s.itag, s.format, s.codecs, f"{s.audio_sampling_rate} Hz")
    console.print(table)


def print_video_table(console, streams, **table_kwargs):
    table = Table(title="(Video)", **table_kwargs)
    for name in ("itag", "Format", "Codec", "Quality"):
        if name == "itag":
            table.add_column(" " + name, ratio=20, justify="center")
        else:
            table.add_column(name, ratio=(100 - 20) / 3)
    for s in sorted(streams, key=lambda x: (x.codecs, x.quality, x.itag)):
        table.add_row(s.itag, s.format, s.codecs, str(s.quality))
    console.print(table)


@cloup.group("mpd", short_help="Compose and play MPEG-DASH manifests.")
def mpd_group():
    pass


@mpd_group.command(
    "compose",
    short_help="Compose MPEG-DASH manifest.",
    help="Compose MPEG-DASH manifest for stream excerpt.",
)
@cloup.option_group(
    "Input options",
    boundary_options,
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
@click.pass_context
@output_options
@yt_dlp_option
@cache_options
@stream_argument
def compose_command(
    ctx: click.Context,
    interval: types.PointInStream,
    preview: bool,
    audio_formats: str,
    video_formats: str,
    output: Path,
    force_update_cache: bool,
    no_cache: bool,
    yt_dlp: bool,
    stream_url: str,
) -> int:
    if not audio_formats and not video_formats:
        raise click.BadArgumentUsage(
            "At least --audio-formats or --video-formats must be specified."
        )

    console = Console(width=CONSOLE_TEXT_WIDTH)

    playback = create_playback(ctx)

    if audio_formats:
        queried_audio_streams = query_streams_or_exit(
            playback.streams, audio_formats, "--audio-formats"
        )
    else:
        queried_audio_streams = []

    if video_formats:
        queried_video_streams = query_streams_or_exit(
            playback.streams, video_formats, "--video-formats"
        )
    else:
        queried_video_streams = []

    num_of_streams = len(queried_audio_streams) + len(queried_video_streams)
    if num_of_streams == 1:
        click.echo("This representation will be in the manifest:")
    else:
        click.echo(f"These {num_of_streams} representations will be in the manifest:")

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

    if preview:
        assert False
        segment_duration = ...
        preview_duration_value = ctx.obj.config.traverse("general.preview_duration")
        number_of_segments = round(preview_duration_value / segment_duration)
        requested_end = RelativeSequenceNumber(number_of_segments)

    click.echo("(<<) Locating start and end in the stream... ", nl=False)
    rewind_range = playback.locate_rewind_range(
        requested_start,
        requested_end,
        itag=reference_stream.itag,
    )
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
    end_segment = playback.get_downloaded_segment(rewind_range.end, reference_base_url)

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

    print_summary_info(requested_date_interval, actual_date_interval, rewind_range)
    click.echo()

    preliminary_path = output
    output_path_contains_template = OUTPUT_PATH_PLACEHOLDER_RE.search(
        str(preliminary_path)
    )
    if output_path_contains_template:
        input_timezone = requested_date_interval.start.tzinfo
        template_context: MpdOutputPathContext = {
            "id": playback.video_id,
            "title": playback.info.title,
            "input_start_date": requested_date_interval.start,
            "input_end_date": requested_date_interval.end,
            "actual_start_date": actual_date_interval.start.astimezone(input_timezone),
            "actual_end_date": actual_date_interval.end.astimezone(input_timezone),
            "duration": requested_end_date - requested_start_date,
        }
        preliminary_path = expand_template_output_path(
            preliminary_path,
            template_context,
            render_mpd_output_path_context,
            ctx.obj.config,
        )
        preliminary_path = preliminary_path.expanduser()

    # Full absolute manifest output path with extension.
    final_output_path = Path(preliminary_path).resolve()
    Path.mkdir(final_output_path.parent, parents=True, exist_ok=True)

    click.echo("(<<) Composing MPEG-DASH manifest...")
    streams = Streams(queried_audio_streams + queried_video_streams)
    composed_manifest = compose_mpd(playback.info, streams, rewind_range)

    with open(final_output_path, "w") as f:
        f.write(composed_manifest)

    try:
        saved_to_path_value = f"{final_output_path.relative_to(Path.cwd())}"
    except ValueError:
        saved_to_path_value = final_output_path

    click.echo(f"Success! Manifest saved to '{saved_to_path_value}'.")
    click.echo("~ Note that the manifest will expire in 6 hours.")


@mpd_group.command(
    "refresh",
    short_help="Refresh composed MPEG-DASH manifest.",
    help="Refresh composed MPEG-DASH manifest for stream excerpt.",
)
@yt_dlp_option
@cloup.argument("manifest", help="Manifest file to refresh.")
def refresh_command(
    yt_dlp: bool,
    manifest: str,
) -> int:
    with open(manifest, "r", encoding="utf-8") as f:
        manifest_content = f.read()

    list_of_streams = extract_representations_info(manifest_content)
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
    with open(manifest, "w") as f:
        f.write(refreshed)

    some_base_url = next(iter(playback.streams)).base_url
    expires_at_time = int(extract_parameter_from_url("expire", some_base_url))
    expires_at_date = datetime.fromtimestamp(expires_at_time)
    expires_in = express_timedelta_in_words(expires_at_date - datetime.now())

    click.echo(f"Success! Manifest has been refreshed, and expires in {expires_in}.")
