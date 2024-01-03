import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

import click
import cloup
import structlog

from ytpb.actions.capture import extract_frame_as_image
from ytpb.cli.common import (
    create_playback,
    prepare_line_for_summary_info,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    resolve_output_path,
    stream_argument,
)
from ytpb.cli.options import (
    cache_options,
    no_cleanup_option,
    validate_image_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import (
    FormatSpecParamType,
    FormatSpecType,
    PointInStreamParamType,
)
from ytpb.exceptions import QueryError, SegmentDownloadError, SequenceLocatingError
from ytpb.locate import SequenceLocator
from ytpb.segment import Segment
from ytpb.types import (
    AbsolutePointInStream,
    AddressableMappingProtocol,
    SegmentSequence,
)
from ytpb.utils.date import ISO8601DateFormatter
from ytpb.utils.path import (
    expand_template_output_path,
    MinimalOutputPathContext,
    OUTPUT_PATH_PLACEHOLDER_RE,
    OutputPathContextRenderer,
    render_minimal_output_path_context,
)
from ytpb.utils.remote import request_reference_sequence

logger = structlog.get_logger(__name__)


class CaptureOutputPathContext(MinimalOutputPathContext):
    moment_date: datetime


def render_capture_output_path_context(
    context: CaptureOutputPathContext,
    config_settings: AddressableMappingProtocol,
) -> CaptureOutputPathContext:
    output = context
    for variable in CaptureOutputPathContext.__annotations__.keys():
        match variable:
            case "moment_date" as x:
                date_formatter = ISO8601DateFormatter()
                output[x] = OutputPathContextRenderer.render_date(
                    context[x], date_formatter, config_settings
                )

    output.update(render_minimal_output_path_context(context, config_settings))

    return output


@cloup.command("capture", help="Take video frame capture.")
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
@no_cleanup_option
@cache_options
@stream_argument
@click.pass_context
def capture_command(
    ctx: click.Context,
    moment: AbsolutePointInStream | Literal["now"],
    video_format: str,
    output_path: Path,
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
                sl = SequenceLocator(
                    reference_base_url,
                    temp_directory=playback.get_temp_directory(),
                    session=playback.session,
                )
                moment_sequence = sl.find_sequence_by_time(date.timestamp())
            except SequenceLocatingError:
                message = "\nerror: An error occured during segment locating, exit."
                click.echo(message, err=True)
                sys.exit(1)
        case "now":
            moment_sequence = head_sequence

    click.echo("done.")

    try:
        segment_path = playback.download_segment(moment_sequence, reference_base_url)
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
    if OUTPUT_PATH_PLACEHOLDER_RE.search(str(output_path)):
        template_context: CaptureOutputPathContext = {
            "id": playback.video_id,
            "title": playback.info.title,
            "moment_date": requested_moment_date,
        }
        final_output_path = expand_template_output_path(
            output_path,
            template_context,
            render_capture_output_path_context,
            ctx.obj.config,
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
    click.echo(f"\nSuccess! Image saved to '{saved_to_path_value}'.")

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
