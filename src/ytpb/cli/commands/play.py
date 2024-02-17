from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree

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
from ytpb.segment import SegmentMetadata
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

        self._mpv.bind_key_press("s", self.take_screenshot)
        self._mpv.bind_event("client-message", self._client_message_handler)

    def _cleanup_on_quit(self):
        pass

    def _client_message_handler(self, event: dict) -> None:
        try:
            targeted_command, *args = event["args"]
            target, command = targeted_command.split(":")
        except ValueError:
            return
        else:
            if target != YTPB_CLIENT_NAME:
                return

        match command:
            case "rewind":
                try:
                    (rewind_value,) = args
                    self.rewind(datetime.fromisoformat(rewind_value))
                except ValueError:
                    pass

    def _compose_mpd(self, rewind_segment_metadata: SegmentMetadata) -> Path:
        mpd = compose_dynamic_mpd(
            self._playback, rewind_segment_metadata, self._streams
        )
        with NamedTemporaryFile(
            "w",
            prefix="ytpb-",
            suffix=".mpd",
            dir=self._playback.get_temp_directory(),
            delete=False,
        ) as f:
            self._mpd_path = Path(f.name)
            f.write(mpd)
            logger.debug("Saved playback MPD file to %s", f.name)

        mpd_etree = ElementTree.fromstring(mpd)
        mpd_start_time_string = mpd_etree.attrib["availabilityStartTime"]
        self._mpd_start_time = datetime.fromisoformat(mpd_start_time_string)
        logger.debug("MPD@availabilityStartTime=%s", mpd_start_time_string)

        return self._mpd_path

    def take_screenshot(self):
        time_pos = self._mpv.command("get_property", "time-pos")
        logger.debug("Got property from player", property="time-pos", value=time_pos)

        captured_date = self._mpd_start_time + timedelta(seconds=time_pos)
        output_path = "{}_{}.jpg".format(
            self._playback.video_id, captured_date.isoformat(timespec="seconds")
        )
        output_path = output_path.replace("-", "").replace(":", "")
        output_path = output_path.replace("00.", ".")
        self._mpv.command("osd-msg", "screenshot-to-file", output_path, "video")

    def rewind(self, rewind_date: datetime) -> None:
        some_stream = next(iter(self._streams))
        rewind_moment = self._playback.locate_moment(rewind_date, some_stream.itag)

        rewind_segment = self._playback.get_downloaded_segment(
            rewind_moment.sequence, some_stream.base_url
        )

        composed_mpd_path = self._compose_mpd(rewind_segment.metadata)

        self._mpv.command("loadfile", str(composed_mpd_path))
        self._mpv.command("set_property", "pause", "yes")
        self._mpv.command(
            "script-message",
            "yp:rewind-completed",
            str(composed_mpd_path),
            str(rewind_moment.cut_at),
        )

    def run(self):
        some_base_url = next(iter(self._streams)).base_url

        latest_sequence = request_reference_sequence(
            some_base_url, self._playback.session
        )
        rewind_segment = self._playback.get_downloaded_segment(
            latest_sequence, some_base_url
        )

        composed_mpd_path = self._compose_mpd(rewind_segment.metadata)

        self._mpv.play(str(composed_mpd_path))


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
