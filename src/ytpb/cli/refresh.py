import logging
import sys
from datetime import datetime

import click

from ytpb.cli.common import logging_options
from ytpb.compose import refresh_mpd
from ytpb.exceptions import BroadcastStatusError
from ytpb.info import BroadcastStatus
from ytpb.mpd import extract_representations_info
from ytpb.playback import Playback
from ytpb.utils.date import express_timedelta_in_words
from ytpb.utils.url import build_video_url_from_base_url, extract_parameter_from_url

logger = logging.getLogger(__name__)


@click.command(
    "refresh",
    short_help="Refresh composed DASH manfiest.",
    help="Refresh composed DASH manifest for stream excerpt.",
)
@logging_options
@click.option(
    "--print-summary", "-u", is_flag=True, help="Print summary after downloading."
)
@click.argument("manifest")
def refresh_command(
    print_summary: bool,
    manifest: str,
) -> int:
    with open(manifest, "r", encoding="utf-8") as f:
        manifest_content = f.read()

    list_of_streams = extract_representations_info(manifest_content)
    stream_url = build_video_url_from_base_url(list_of_streams[0].base_url)

    try:
        playback = Playback.from_url(stream_url)
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

    click.echo(f"Success! Manifest refreshed, and will expire in {expires_in}")


if __name__ == "__main__":
    refresh_command()
