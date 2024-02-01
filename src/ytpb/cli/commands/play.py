from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import click
import cloup
import structlog
from cloup.constraints import constraint, require_any
from python_mpv_jsonipc import MPV

from ytpb.actions.compose import compose_dynamic_mpd
from ytpb.cli.common import create_playback, stream_argument
from ytpb.cli.options import cache_options, interval_option, yt_dlp_option
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType
from ytpb.streams import Streams
from ytpb.utils.remote import request_reference_sequence

logger = structlog.get_logger(__name__)

YTPB_CLIENT_NAME = "yp"


class StreamPlayer:
    def __init__(self, playback, mpv_path: Path):
        self._playback = playback
        self._mpv = MPV(mpv_location=mpv_path)

    def run(self):
        streams = Streams([self._playback.streams.get_by_itag("244")])
        some_base_url = next(iter(streams)).base_url

        latest_sequence = request_reference_sequence(
            some_base_url, self._playback.session
        )
        rewind_segment = self._playback.get_downloaded_segment(
            latest_sequence, some_base_url
        )

        manifest = compose_dynamic_mpd(self._playback, rewind_segment.metadata, streams)
        with NamedTemporaryFile("w", suffix=".mpd", delete=False) as f:
            manifest_path = Path(f.name)
            print(manifest_path)
            f.write(manifest)

        self._mpv.play(str(manifest_path))


@cloup.command(
    "play", short_help="Play and rewind streams.", help="Play and rewind a stream."
)
@cloup.option_group(
    "Input options",
    cloup.option(
        "-af",
        "--audio-format",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.AUDIO),
        help="Audio format to play.",
    ),
    cloup.option(
        "-vf",
        "--video-format",
        metavar="SPEC",
        type=FormatSpecParamType(FormatSpecType.VIDEO),
        help="Video format to play.",
    ),
    cloup.option(
        "--mpv-path",
        type=click.Path(path_type=Path),
        help="Path to the custom-built `mpv` binary.",
    ),
)
@yt_dlp_option
@cache_options
@stream_argument
@constraint(require_any, ["audio_format", "video_format"])
@click.pass_context
def play_command(
    ctx: click.Context,
    audio_format: str,
    video_format: str,
    mpv_path: Path,
    yt_dlp: bool,
    force_update_cache: bool,
    no_cache: bool,
    stream_url: str,
) -> int:
    playback = create_playback(ctx)
    player = StreamPlayer(playback, mpv_path)
    player.run()
