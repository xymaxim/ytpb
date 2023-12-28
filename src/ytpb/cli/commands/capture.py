import shutil
import sys
from datetime import datetime
from pathlib import Path
from textwrap import fill
from typing import Literal

import av
import click
import cloup
import structlog
from PIL import Image

from ytpb.cli.common import (
    create_playback,
    prepare_line_for_summary_info,
    raise_for_sequence_ahead_of_current,
    raise_for_too_far_sequence,
    stream_argument,
)
from ytpb.cli.options import (
    cache_options,
    no_cleanup_option,
    output_options,
    validate_output_path,
    yt_dlp_option,
)
from ytpb.cli.parameters import (
    FormatSpecParamType,
    FormatSpecType,
    PointInStreamParamType,
)
from ytpb.download import download_segment
from ytpb.exceptions import (
    BroadcastStatusError,
    CachedItemNotFoundError,
    QueryError,
    SegmentDownloadError,
    SequenceLocatingError,
)
from ytpb.fetchers import YoutubeDLInfoFetcher, YtpbInfoFetcher
from ytpb.info import BroadcastStatus
from ytpb.locate import SequenceLocator
from ytpb.playback import Playback
from ytpb.segment import Segment
from ytpb.types import AbsolutePointInStream, SegmentSequence
from ytpb.utils.path import (
    expand_template_output_path,
    OUTPUT_PATH_PLACEHOLDER_RE,
    OutputPathTemplateContext,
)
from ytpb.utils.remote import request_reference_sequence

logger = structlog.get_logger(__name__)


def validate_image_output_path(
    ctx: click.Context, param: click.Option, value: Path
) -> Path:
    if not value.suffix:
        raise click.BadParameter(f"File extension must be provided.")

    extensions = Image.registered_extensions()
    supported_extensions = {ext for ext, f in extensions.items() if f in Image.SAVE}
    if value.suffix not in supported_extensions:
        tip = fill("Choose one of: {}".format(", ".join(sorted(supported_extensions))))
        raise click.BadParameter(f"Format '{value.suffix}' is not supported.\n\n{tip}")

    return validate_output_path(ctx, param, value)


def save_frame_as_image(video_path: Path, target_time: float, output_path: Path):
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        target_pts = stream.start_time + target_time / stream.time_base
        previous_frame: av.VideoFrame = None
        for current_frame in container.decode(stream):
            if current_frame.pts >= target_pts:
                break
            previous_frame = current_frame
        else:
            logger.debug(
                "Target time is out of the video, use the last frame", time=target_time
            )
    target_frame = previous_frame or current_frame
    image = target_frame.to_image()
    image.save(output_path, quality=80)


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
def capture_command(
    ctx: click.Context,
    moment: AbsolutePointInStream | Literal["now"],
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
        downloaded_path = download_segment(
            moment_sequence,
            reference_base_url,
            output_directory=playback.get_temp_directory(),
            session=playback.session,
            force_download=False,
        )
    except SegmentDownloadError as exc:
        click.echo()
        logger.error(exc, sequence=exc.sequence, exc_info=True)
        sys.exit(1)

    moment_segment = Segment.from_file(downloaded_path)

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

    preliminary_path = output
    output_path_contains_template = OUTPUT_PATH_PLACEHOLDER_RE.search(
        str(preliminary_path)
    )
    if output_path_contains_template:
        input_timezone = actual_moment_date.tzinfo
        template_context = OutputPathTemplateContext(
            playback.video_id,
            playback.info.title,
            actual_moment_date,
            None,
            actual_moment_date,
            None,
            None,
        )
        preliminary_path = expand_template_output_path(
            preliminary_path, template_context, ctx.obj.config
        )
        preliminary_path = preliminary_path.expanduser()

    # Full absolute excerpt output path without extension.
    final_output_path = Path(preliminary_path).resolve()
    Path.mkdir(final_output_path.parent, parents=True, exist_ok=True)

    requested_frame_offset = requested_moment_date - moment_segment.ingestion_start_date
    save_frame_as_image(
        downloaded_path, requested_frame_offset.total_seconds(), final_output_path
    )

    try:
        saved_to_path_value = f"{final_output_path.relative_to(Path.cwd())}"
    except ValueError:
        saved_to_path_value = saved_to_path
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
