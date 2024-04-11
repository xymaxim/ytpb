import shutil
import sys
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

import click
import cloup
import structlog
from cloup.constraints import constraint, require_any

from ytpb import actions
from ytpb.cli.common import (
    create_playback,
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
    no_cleanup_option,
    preview_option,
    validate_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType, InputRewindInterval
from ytpb.errors import SequenceLocatingError
from ytpb.merge import merge_segments
from ytpb.types import (
    AddressableMappingProtocol,
    DateInterval,
    RelativeSegmentSequence,
    SegmentSequence,
)
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.path import (
    expand_template_output_path,
    IntervalOutputPathContext,
    MinimalOutputPathContext,
    OUTPUT_PATH_PLACEHOLDER_RE,
    render_interval_output_path_context,
    render_minimal_output_path_context,
)
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.url import build_segment_url, extract_parameter_from_url

logger = structlog.get_logger(__name__)


class DownloadOutputPathContext(
    MinimalOutputPathContext, IntervalOutputPathContext
): ...


def render_download_output_path_context(
    context: DownloadOutputPathContext,
    config_settings: AddressableMappingProtocol,
) -> DownloadOutputPathContext:
    output = context
    output.update(render_minimal_output_path_context(context, config_settings))
    output.update(render_interval_output_path_context(context, config_settings))
    return output


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
    preview_option,
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
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Output path (without extension).",
    callback=validate_output_path(DownloadOutputPathContext),
)
@click.option(
    "-m",
    "--from-manifest",
    metavar="PATH",
    type=click.Path(path_type=Path),
    help="Path to a MPEG-DASH manifest.",
)
@click.option(
    "-X",
    "--dry-run",
    is_flag=True,
    help="Run without downloading.",
)
@yt_dlp_option
@click.option("--no-cut", is_flag=True, help="Do not perform excerpt cutting.")
@click.option(
    "--no-merge",
    is_flag=True,
    help="Only download segments, without merging. This implies '--no-cleanup'.",
)
@no_cleanup_option
@cache_options
@stream_argument
@constraint(require_any, ["audio_format", "video_format"])
@click.pass_context
def download_command(
    ctx: click.Context,
    interval: InputRewindInterval,
    audio_format: str,
    video_format: str,
    preview: bool,
    dump_base_urls: bool,
    dump_segment_urls: bool,
    output_path: Path,
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
    if dump_base_urls or dump_segment_urls:
        suppress_output()

    if no_merge:
        no_cleanup = True

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

    if preview and interval[1] != "..":
        click.echo("info: The preview mode is enabled, interval end is ignored.")

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
    if not no_cut:
        cut_at_start = rewind_interval.start.cut_at
        if preview:
            cut_at_end = 0
        else:
            cut_at_end = rewind_interval.end.cut_at
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
        click.echo("notice: This is a dry run. Skip downloading and exit.")
    else:
        # Absolute output path of an excerpt without extension.
        final_output_path: Path

        if OUTPUT_PATH_PLACEHOLDER_RE.search(str(output_path)):
            input_timezone = requested_date_interval.start.tzinfo
            template_context: DownloadOutputPathContext = {
                "id": playback.video_id,
                "title": playback.info.title,
                "input_start_date": requested_date_interval.start,
                "input_end_date": requested_date_interval.end,
                "actual_start_date": actual_date_interval.start.astimezone(
                    input_timezone
                ),
                "actual_end_date": actual_date_interval.end.astimezone(input_timezone),
                "duration": requested_end_date - requested_start_date,
            }
            final_output_path = expand_template_output_path(
                output_path,
                template_context,
                render_download_output_path_context,
                ctx.obj.config,
            )
        else:
            final_output_path = output_path
        final_output_path = resolve_output_path(final_output_path)

        total_segments = (
            rewind_interval.end.sequence - rewind_interval.start.sequence + 1
        )
        progress_reporter = actions.download.RichProgressReporter()
        if audio_stream:
            progress_reporter.progress.add_task("   - Audio", total=total_segments)
        if video_stream:
            progress_reporter.progress.add_task("   - Video", total=total_segments)
        do_download_segments = partial(
            actions.download.download_segments,
            playback,
            rewind_interval,
            [x for x in [audio_stream, video_stream] if x is not None],
            progress_reporter=progress_reporter,
        )

        if no_merge:
            click.echo(
                "(<<) Downloading segments {}-{} (no merge requested)...".format(
                    rewind_interval.start.sequence, rewind_interval.end.sequence
                )
            )
            downloaded_segment_paths = do_download_segments()
            some_downloaded_path = downloaded_segment_paths[0][0]
            click.echo(
                "\nSuccess! Segments saved to {}/.".format(some_downloaded_path.parent)
            )
        else:
            click.echo("(<<) Preparing and saving the excerpt...")
            click.echo(
                "1. Downloading segments {}-{}:".format(
                    rewind_interval.start.sequence, rewind_interval.end.sequence
                )
            )

            downloaded_segment_paths = do_download_segments()
            audio_and_video_segment_paths: list[list[Path]] = [[], []]
            match audio_stream, video_stream:
                case _, None:
                    audio_and_video_segment_paths[0] = downloaded_segment_paths[0]
                case None, _:
                    audio_and_video_segment_paths[1] = downloaded_segment_paths[0]
                case _:
                    audio_and_video_segment_paths = downloaded_segment_paths

            if no_cut:
                click.echo("2. Merging segments (no cut requested)... ", nl=False)
            else:
                click.echo("2. Merging segments (may take a while)... ", nl=False)

            merged_path = merge_segments(
                audio_and_video_segment_paths[0],
                audio_and_video_segment_paths[1],
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
