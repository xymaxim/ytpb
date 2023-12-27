import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

import av
import click
import structlog

from ytpb.cli.common import (
    normalize_stream_url,
    raise_for_sequence_ahead_of_current,
    create_playback
)
from ytpb.cli.options import (
    cache_options,
    output_options,
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
from ytpb.types import (
    AbsolutePointInStream,
    SegmentSequence,
)
from ytpb.utils.path import (
    expand_template_output_path,
    OUTPUT_PATH_PLACEHOLDER_RE,
    OutputPathTemplateContext,
)
from ytpb.utils.remote import request_reference_sequence

logger = structlog.get_logger(__name__)


def save_video_frame_as_image(video_path: Path, target_time: float, output_path: Path):
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
                "Target time is out of the video, use the last frame",
                time=target_time
            )
    target_frame = previous_frame or current_frame
    image = target_frame.to_image()
    image.save(output_path, quality=80)

    
@click.command("capture", help="Take video frame capture.")
@click.option(
    "-m",
    "--moment",
    metavar="MOMENT",
    type=PointInStreamParamType(allowed_literals=["now"]),
    help="Moment to capture.",
)
@click.option(
    "-vf",
    "--video-format",
    metavar="SPEC",
    type=FormatSpecParamType(FormatSpecType.VIDEO),
    help="Video format to capture.",
)
@output_options
@click.option("-Y", "--yt-dlp", is_flag=True, help="Use yt-dlp to extract info.")
@click.option("--no-cleanup", is_flag=True, help="Do not clean up temporary files.")
@cache_options
@click.argument("stream_url", metavar="STREAM", callback=normalize_stream_url)
@click.pass_context
def capture_command(
    ctx: click.Context,
    moment:  AbsolutePointInStream | Literal["now"],
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

    match moment:
        case SegmentSequence() as sequence:
            moment_sequence = sequence
            raise_for_sequence_ahead_of_current(sequence, head_sequence, ctx, "moment")
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
            
    actual_moment_date = requested_moment_date

    click.echo()

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
            None
        )
        preliminary_path = expand_template_output_path(
            preliminary_path, template_context, ctx.obj.config
        )
        preliminary_path = preliminary_path.expanduser()

    # Full absolute excerpt output path without extension.
    final_output_path = Path(preliminary_path).resolve()
    Path.mkdir(final_output_path.parent, parents=True, exist_ok=True)

    requested_frame_offset = (
        requested_moment_date - moment_segment.ingestion_start_date
    )
    save_video_frame_as_image(
        downloaded_path,
        requested_frame_offset.total_seconds(),
        final_output_path
    )
