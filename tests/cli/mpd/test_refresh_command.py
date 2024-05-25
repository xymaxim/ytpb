# ruff: noqa: E501

import copy
import platform
from dataclasses import asdict
from difflib import unified_diff
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import freezegun
import pytest
from freezegun import freeze_time

from ytpb.info import YouTubeVideoInfo
from ytpb.playback import Playback
from ytpb.streams import Streams
from ytpb.types import AudioOrVideoStream, AudioStream, VideoStream

from tests.helpers import patched_freezgun_astimezone

freezegun.api.FakeDatetime.astimezone = patched_freezgun_astimezone


@pytest.fixture()
def dash_manifest(audio_base_url: str, video_base_url: str) -> str:
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<!--This file is created with ytpb, and expires at 2023-08-16T04:24:48+02:00-->
<MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:mpeg:DASH:schema:MPD:2011" xsi:schemaLocation="urn:mpeg:DASH:schema:MPD:2011 DASH-MPD.xsd" profiles="urn:mpeg:dash:profile:isoff-main:2011" type="static" mediaPresentationDuration="PT66S">
  <Period duration="PT66S">
    <AdaptationSet id="0" mimeType="audio/mp4" subsegmentAlignment="true">
      <SegmentTemplate media="sq/$Number$" startNumber="7959120" duration="2000" timescale="1000"/>
      <Representation id="140" codecs="mp4a.40.2" startWithSAP="1" audioSamplingRate="44100">
        <BaseURL>{audio_base_url}</BaseURL>
      </Representation>
    </AdaptationSet>
    <AdaptationSet id="1" mimeType="video/webm" subsegmentAlignment="true">
      <SegmentTemplate media="sq/$Number$" startNumber="7959120" duration="2000" timescale="1000"/>
      <Representation id="244" codecs="vp9" startWithSAP="1" width="854" height="480" maxPlayoutRate="1" frameRate="30">
        <BaseURL>{video_base_url}</BaseURL>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>
"""


@pytest.mark.expect_suffix(platform.system())
@freeze_time("2023-08-16T02:30:00+02:00", tz_offset=2)
def test_refresh_mpd(
    ytpb_cli_invoke: Callable,
    mock_fetch_and_set_essential: MagicMock,
    streams_in_list: list[AudioOrVideoStream],
    active_live_video_info: YouTubeVideoInfo,
    stream_url: str,
    video_id: str,
    audio_base_url: str,
    video_base_url: str,
    dash_manifest: str,
    tmp_path: Path,
    expected_out,
) -> None:
    # Given:
    manifest_path = tmp_path / "manifest.mpd"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(dash_manifest)

    # When:
    def mock_essential(obj: Playback, *args, **kwargs):
        updated_streams = copy.deepcopy(streams_in_list)
        for i, stream in enumerate(updated_streams):
            stream_as_dict = asdict(stream)
            stream_as_dict["base_url"] = "https://test/expire/1692153000/"
            if "audio" in stream.mime_type:
                updated_streams[i] = AudioStream(**stream_as_dict)
            else:
                updated_streams[i] = VideoStream(**stream_as_dict)
            obj._streams = Streams(updated_streams)
            obj._info = active_live_video_info

    with patch.object(
        Playback, "fetch_and_set_essential", side_effect=mock_essential, autospec=True
    ):
        result = ytpb_cli_invoke(["mpd", "refresh", str(manifest_path)])

    # Then:
    assert result.exit_code == 0
    assert result.output == expected_out

    with open(manifest_path, encoding="utf-8") as f:
        refreshed_manifest = f.read()

    actual_diff = list(
        unified_diff(
            dash_manifest.splitlines(keepends=True),
            refreshed_manifest.splitlines(keepends=True),
            n=0,
        )
    )
    assert actual_diff == [
        "--- \n",
        "+++ \n",
        "@@ -2 +2 @@\n",
        "-<!--This file is created with ytpb, and expires at 2023-08-16T04:24:48+02:00-->\n",
        "+<!--This file is created with ytpb, and expires at 2023-08-16T04:30:00+02:00-->\n",
        "@@ -8 +8 @@\n",
        f"-        <BaseURL>{audio_base_url}</BaseURL>\n",
        "+        <BaseURL>https://test/expire/1692153000/</BaseURL>\n",
        "@@ -14 +14 @@\n",
        f"-        <BaseURL>{video_base_url}</BaseURL>\n",
        "+        <BaseURL>https://test/expire/1692153000/</BaseURL>\n",
    ]
