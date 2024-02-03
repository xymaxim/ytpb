from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import click
import cloup
import structlog
from cloup.constraints import constraint, require_any
from python_mpv_jsonipc import MPV

from ytpb.actions.compose import compose_dynamic_mpd
from ytpb.cli.common import create_playback, query_streams_or_exit, stream_argument
from ytpb.cli.options import cache_options, interval_option, yt_dlp_option
from ytpb.cli.parameters import FormatSpecParamType, FormatSpecType
from ytpb.playback import Playback
from ytpb.streams import Streams
from ytpb.types import AudioOrVideoStream, SetOfStreams
from ytpb.utils.remote import request_reference_sequence

logger = structlog.get_logger(__name__)

YTPB_CLIENT_NAME = "yp"


class StreamPlayer:
    def __init__(self, playback: Playback, streams: SetOfStreams, mpv_path: Path):
        self._playback = playback
        self._streams = streams
        self._mpd_start_time: datetime | None = None

        self._mpv = MPV(
            mpv_location=mpv_path,
            terminal=True,
            input_terminal=True,
            quit_callback=self._cleanup_on_quit,
        )

        @self._mpv.on_key_press("s")
        def handle_take_screenshot():
            time_pos = self._mpv.command("get_property", "time-pos")
            captured_date = self._mpd_start_time + timedelta(seconds=time_pos)
            output_path = "{}_{}.jpg".format(
                self._playback.video_id, captured_date.isoformat(timespec="seconds")
            )
            output_path = output_path.replace("-", "").replace(":", "")
            output_path = output_path.replace("00.", ".")
            self._mpv.command("osd-msg", "screenshot-to-file", output_path, "video")

    def _cleanup_on_quit(self):
        self._mpd_path.unlink()
        logger.debug("Removed playback MPD file: %s", self._mpd_path)

    def run(self):
        some_base_url = next(iter(self._streams)).base_url

        latest_sequence = request_reference_sequence(
            some_base_url, self._playback.session
        )
        rewind_segment = self._playback.get_downloaded_segment(
            latest_sequence, some_base_url
        )

        self._mpd_start_time = datetime.fromtimestamp(
            rewind_segment.metadata.ingestion_walltime, timezone.utc
        )

        mpd = compose_dynamic_mpd(
            self._playback, rewind_segment.metadata, self._streams
        )
        with NamedTemporaryFile("w", prefix="ytpb-", suffix=".mpd", delete=False) as f:
            self._mpd_path = Path(f.name)
            f.write(mpd)
            logger.debug("Saved playback MPD file to %s", f.name)

        self._mpv.play(str(self._mpd_path))


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

    if audio_format:
        logger.debug("Query audio streams by format spec", spec=audio_format)
        queried_audio_streams = query_streams_or_exit(
            playback.streams, audio_format, "--audio-format", allow_many=False
        )

    if video_format:
        logger.debug("Query video stream by format spec", spec=video_format)
        queried_video_streams = query_streams_or_exit(
            playback.streams, video_format, "--video-format", allow_many=False
        )

    all_queried_streams = Streams(queried_audio_streams + queried_video_streams)

    player = StreamPlayer(playback, all_queried_streams, mpv_path)
    player.run()