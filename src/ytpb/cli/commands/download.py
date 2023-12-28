import shutil
import sys
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Literal

import click
import cloup
import structlog
from requests.exceptions import HTTPError

from ytpb import types
from ytpb.cli import parameters
from ytpb.cli.common import (
    check_end_options,
    check_streams_not_empty,
    create_playback,
    get_downloaded_segment,
    print_summary_info,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    stream_argument,
)
from ytpb.cli.custom import get_parameter_by_name
from ytpb.cli.options import (
    boundary_options,
    cache_options,
    logging_options,
    no_cleanup_option,
    output_options,
    yt_dlp_option,
)
from ytpb.cli.parameters import (
    FormatSpecParamType,
    FormatSpecType,
    InputRewindInterval,
    RewindIntervalParamType,
)
from ytpb.download import download_segment
from ytpb.exceptions import (
    BaseUrlExpiredError,
    BroadcastStatusError,
    CachedItemNotFoundError,
    QueryError,
    SegmentDownloadError,
    SequenceLocatingError,
)
from ytpb.fetchers import YoutubeDLInfoFetcher, YtpbInfoFetcher
from ytpb.info import BroadcastStatus
from ytpb.merge import merge_segments
from ytpb.playback import Playback
from ytpb.segment import Segment
from ytpb.types import DateInterval, RelativeSegmentSequence, SegmentSequence
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.path import (
    expand_template_output_path,
    OUTPUT_PATH_PLACEHOLDER_RE,
    OutputPathTemplateContext,
)
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.units import S_TO_MS
from ytpb.utils.url import extract_parameter_from_url

logger = structlog.get_logger(__name__)


@cloup.command("download", help="Download stream excerpt.")
@cloup.option_group(
    "Input options",
    boundary_options,
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
)
@output_options
@click.option(
    "-m",
    "--from-manifest",
    metavar="PATH",
    type=click.Path(path_type=Path),
    help="Path to MPEG-DASH manifest.",
)
@click.option(
    "-X",
    "--dry-run",
    is_flag=True,
    help=("Run without downloading."),
)
@yt_dlp_option
@click.option("--no-cut", is_flag=True, help="Do not perform excerpt cutting.")
@click.option(
    "--no-merge",
    is_flag=True,
    help=("Only download segments, without merging. This implies '--no-cleanup'."),
)
@no_cleanup_option
@cache_options
@stream_argument
@click.pass_context
def download_command(
    ctx: click.Context,
    interval: InputRewindInterval,
    preview: bool,
    audio_format: str,
    video_format: str,
    output: Path,
    from_manifest: Path,
    dry_run: bool,
    yt_dlp: bool,
    no_cut: bool,
    no_merge: bool,
    no_cleanup: bool,
    force_update_cache: bool,
    no_cache: bool,
    stream_url: str,
) -> int:
    if audio_format is None and video_format is None:
        raise click.UsageError(
            "At least --audio-format or --video-format must be specified."
        )

    if no_merge:
        no_cleanup = True

    playback = create_playback(ctx)

    if audio_format:
        logger.debug("Query audio stream by format spec", spec=audio_format)
        try:
            queried_audio_streams = playback.streams.query(audio_format)
        except QueryError as exc:
            click.echo(f"\nerror: Failed to query audio streams. {exc}", err=True)
            sys.exit(1)
    else:
        queried_audio_streams = []
    if video_format:
        logger.debug("Query video stream by format spec", spec=video_format)
        try:
            queried_video_streams = playback.streams.query(video_format)
        except QueryError as exc:
            click.echo(f"\nerror: Failed to query video streams. {exc}", err=True)
            sys.exit(1)
    else:
        queried_video_streams = []

    check_streams_not_empty(
        queried_audio_streams,
        audio_format,
        queried_video_streams,
        video_format,
    )

    are_both_streams_ambiguous = (
        len(queried_audio_streams) > 1 and len(queried_video_streams) > 1
    )
    ambiguous_tip = (
        "Found more than one formats matching a format spec.\n"
        "Please be more explicit, or try 'yt-dlp --live-from-start -F ...' first."
    )
    if not are_both_streams_ambiguous:
        if len(queried_audio_streams) == 1 and len(queried_video_streams) == 1:
            click.echo("These representations will be downloaded:")
        elif len(queried_audio_streams) == 1:
            click.echo("This representation will be downloaded:")

        audio_stream, video_stream = None, None
        if audio_format:
            if len(queried_audio_streams) == 1:
                audio_stream = queried_audio_streams[0]
                click.echo(
                    f"   - Audio: itag {audio_stream.itag}, "
                    f"{audio_stream.format} ({audio_stream.codecs}), "
                    f"{audio_stream.audio_sampling_rate} Hz"
                )
                logger.info("Queried audio stream", base_url=audio_stream.base_url)
            else:
                logger.error(
                    "Too many queried audio streams",
                    itags=[s.itag for s in queried_audio_streams],
                )
                click.echo("error: Audio format spec is ambiguous.\n", err=True)
                click.echo(ambiguous_tip, err=True)
                sys.exit(1)

        if video_format:
            if len(queried_video_streams) == 1:
                video_stream = queried_video_streams[0]
                click.echo(
                    f"   - Video: itag {video_stream.itag}, "
                    f"{video_stream.format} ({video_stream.codecs}), "
                    f"{video_stream.width}x{video_stream.height}, "
                    f"{video_stream.frame_rate} fps"
                )
                logger.info("Queried video stream", base_url=video_stream.base_url)
            else:
                logger.error(
                    "Too many queried video streams",
                    itags=[s.itag for s in queried_video_streams],
                )
                click.echo("error: Video format spec is ambiguous.\n", err=True)
                click.echo(ambiguous_tip, err=True)
                sys.exit(1)
    else:
        message = "error: Both audio and video format specs are ambiguous.\n"
        click.echo(message, err=True)
        click.echo(ambiguous_tip, err=True)
        sys.exit(1)

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
        preview_duration_value = ctx.obj.config.traverse("general.preview_duration")
        segment_duration = float(extract_parameter_from_url("dur", reference_base_url))
        number_of_segments = round(preview_duration_value / segment_duration)
        requested_end = RelativeSegmentSequence(number_of_segments)

    try:
        rewind_range = playback.locate_rewind_range(
            requested_start,
            requested_end,
            itag=reference_stream.itag,
        )
    except SequenceLocatingError as exc:
        message = "\nerror: An error occured during segment locating, exit."
        click.echo(message, err=True)
        sys.exit(1)

    click.echo("done.")

    if preview and interval[1] != "..":
        click.echo("info: The preview mode is enabled, interval end is ignored.")

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

    if no_cut:
        cut_kwargs = {}
    else:
        start_diff, end_diff = requested_date_interval - actual_date_interval
        cut_at_start_s = start_diff if start_diff > 0 else 0
        if preview:
            cut_at_end_s = 0
        else:
            cut_at_end_s = abs(end_diff) if end_diff < 0 else 0
        cut_kwargs = {
            "cut_at_start": round(cut_at_start_s * int(S_TO_MS)),
            "cut_at_end": round(cut_at_end_s * int(S_TO_MS)),
        }
        if not no_merge:
            actual_date_interval = DateInterval(
                start=actual_date_interval.start + timedelta(seconds=cut_at_start_s),
                end=actual_date_interval.end - timedelta(seconds=cut_at_end_s),
            )

    print_summary_info(requested_date_interval, actual_date_interval, rewind_range)
    click.echo()

    if dry_run:
        click.echo("notice: This is a dry run. Skip downloading and exit.")
    else:
        preliminary_path = output
        output_path_contains_template = OUTPUT_PATH_PLACEHOLDER_RE.search(
            str(preliminary_path)
        )
        if output_path_contains_template:
            input_timezone = requested_date_interval.start.tzinfo
            template_context = OutputPathTemplateContext(
                playback.video_id,
                playback.info.title,
                requested_date_interval.start,
                requested_date_interval.end,
                actual_date_interval.start.astimezone(input_timezone),
                actual_date_interval.end.astimezone(input_timezone),
                actual_date_interval.end - actual_date_interval.start,
            )
            preliminary_path = expand_template_output_path(
                preliminary_path, template_context, ctx.obj.config
            )
            preliminary_path = preliminary_path.expanduser()

        # Full absolute excerpt output path without extension.
        final_output_path = Path(preliminary_path).resolve()
        Path.mkdir(final_output_path.parent, parents=True, exist_ok=True)

        do_download_excerpt_segments = partial(
            playback.download_excerpt,
            rewind_range,
            audio_format,
            video_format,
            output_directory=final_output_path.parent,
            output_stem=final_output_path.name,
            no_merge=True,
        )

        if no_merge:
            click.echo(
                f"(<<) Downloading segments {rewind_range.start}-{rewind_range.end} "
                "(no merge requested)..."
            )
            download_result = do_download_excerpt_segments()
            some_downloaded_paths = (
                download_result.audio_segment_paths
                or download_result.video_segment_paths
            )
            click.echo(
                "\nSuccess! Segments saved to {}/.".format(
                    some_downloaded_paths[0].parent
                )
            )
        else:
            click.echo("(<<) Preparing and saving the excerpt...")
            click.echo(
                f"1. Downloading segments {rewind_range.start}-{rewind_range.end}:"
            )

            download_result = do_download_excerpt_segments()

            if no_cut:
                click.echo("2. Merging segments (no cut requested)... ", nl=False)
            else:
                click.echo("2. Merging segments (may take a while)... ", nl=False)

            merged_path = merge_segments(
                download_result.audio_segment_paths,
                download_result.video_segment_paths,
                output_directory=final_output_path.parent,
                output_stem=final_output_path.name,
                temp_directory=playback.get_temp_directory(),
                **cut_kwargs,
            )
            click.echo("done.\n")

            try:
                saved_to_path_value = f"{merged_path.relative_to(Path.cwd())}"
            except ValueError:
                saved_to_path_value = merged_path
            click.echo(f"Success! Saved to '{saved_to_path_value}'.")

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
