from dataclasses import asdict, dataclass
from difflib import unified_diff

import freezegun
import pytest
from freezegun import freeze_time

from ytpb.actions.compose import compose_dynamic_mpd, compose_static_mpd, refresh_mpd
from ytpb.errors import YtpbError
from ytpb.playback import Playback
from ytpb.segment import SegmentMetadata
from ytpb.streams import Streams
from ytpb.types import AudioOrVideoStream, AudioStream, VideoStream

from tests.helpers import patched_freezgun_astimezone

freezegun.api.FakeDatetime.astimezone = patched_freezgun_astimezone


@dataclass
class FakeRewindMoment:
    sequence: int


@dataclass
class FakeRewindInterval:
    start: FakeRewindMoment
    end: FakeRewindMoment


@pytest.fixture()
def testing_static_mpd(audio_base_url: str, video_base_url: str) -> str:
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<!--This file is created with ytpb, and expires at 2023-09-28T21:17:50+02:00-->
<MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:mpeg:DASH:schema:MPD:2011" xsi:schemaLocation="urn:mpeg:DASH:schema:MPD:2011 DASH-MPD.xsd" profiles="urn:mpeg:dash:profile:isoff-main:2011" type="static" mediaPresentationDuration="PT66S">
  <ProgramInformation>
    <Title>Webcam Zürich HB</Title>
    <Source>https://www.youtube.com/watch?v=kHwmzef842g</Source>
  </ProgramInformation>
  <Period duration="PT66S">
    <AdaptationSet id="0" mimeType="audio/mp4" subsegmentAlignment="true">
      <Representation id="140" codecs="mp4a.40.2" startWithSAP="1" audioSamplingRate="44100">
        <BaseURL>{audio_base_url}</BaseURL>
        <SegmentTemplate media="sq/$Number$" startNumber="7959120" duration="2000" timescale="1000"/>
      </Representation>
    </AdaptationSet>
    <AdaptationSet id="1" mimeType="video/webm" subsegmentAlignment="true">
      <Representation id="244" codecs="vp9" startWithSAP="1" width="854" height="480" maxPlayoutRate="1" frameRate="30">
        <BaseURL>{video_base_url}</BaseURL>
        <SegmentTemplate media="sq/$Number$" startNumber="7959120" duration="2000" timescale="1000"/>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>
"""


@pytest.fixture()
def testing_dynamic_mpd(audio_base_url: str, video_base_url: str) -> str:
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<!--This file is created with ytpb, and expires at 2023-09-28T21:17:50+02:00-->
<MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:mpeg:DASH:schema:MPD:2011" xsi:schemaLocation="urn:mpeg:DASH:schema:MPD:2011 DASH-MPD.xsd" profiles="urn:mpeg:dash:profile:isoff-live:2011" type="dynamic" availabilityStartTime="2023-03-25T23:33:54.491+00:00">
  <ProgramInformation>
    <Title>Webcam Zürich HB</Title>
    <Source>https://www.youtube.com/watch?v=kHwmzef842g</Source>
  </ProgramInformation>
  <Period start="PT15917833.539S">
    <AdaptationSet id="0" mimeType="audio/mp4" subsegmentAlignment="true">
      <Representation id="140" codecs="mp4a.40.2" startWithSAP="1" audioSamplingRate="44100">
        <BaseURL>{audio_base_url}</BaseURL>
        <SegmentTemplate media="sq/$Number$" startNumber="7959120" timescale="1000">
          <SegmentTimeline>
            <S d="2000" r="-1"/>
          </SegmentTimeline>
        </SegmentTemplate>
      </Representation>
    </AdaptationSet>
    <AdaptationSet id="1" mimeType="video/webm" subsegmentAlignment="true">
      <Representation id="244" codecs="vp9" startWithSAP="1" width="854" height="480" maxPlayoutRate="1" frameRate="30">
        <BaseURL>{video_base_url}</BaseURL>
        <SegmentTemplate media="sq/$Number$" startNumber="7959120" timescale="1000">
          <SegmentTimeline>
            <S d="2000" r="-1"/>
          </SegmentTimeline>
        </SegmentTemplate>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>
"""


@freeze_time(tz_offset=2)
def test_compose_static_mpd(
    stream_url: str,
    fake_info_fetcher: "FakeInfoFetcher",
    streams_in_list: list[AudioOrVideoStream],
    testing_static_mpd: str,
):
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()

    streams = Streams(streams_in_list)

    output = compose_static_mpd(
        playback,
        FakeRewindInterval(FakeRewindMoment(7959120), FakeRewindMoment(7959120 + 32)),
        streams.filter(lambda x: x.itag in ("140", "244")),
    )
    assert output == testing_static_mpd


@freeze_time(tz_offset=2)
def test_compose_dynamic_mpd(
    stream_url: str,
    fake_info_fetcher: "FakeInfoFetcher",
    streams_in_list: list[AudioOrVideoStream],
    testing_dynamic_mpd: str,
):
    playback = Playback(stream_url, fetcher=fake_info_fetcher)
    playback.fetch_and_set_essential()

    streams = Streams(streams_in_list)

    rewind_segment_metadata = SegmentMetadata(
        sequence_number=7959120,
        ingestion_walltime=1679787234.491176,
        ingestion_uncertainty=0,
        stream_duration=15917833.539,
        max_dvr_duration=0,
        target_duration=2,
        first_frame_time=1679787235.764305,
        first_frame_uncertainty=0,
    )

    output = compose_dynamic_mpd(
        playback,
        rewind_segment_metadata,
        streams.filter(lambda x: x.itag in ("140", "244")),
    )
    assert output == testing_dynamic_mpd


@freeze_time(tz_offset=2)
def test_refresh_mpd(streams_in_list: list[dict], testing_static_mpd: str):
    selected_streams_list = []
    for stream in streams_in_list:
        if stream.itag in ("140", "244"):
            stream_dict = asdict(stream)
            stream_dict["base_url"] = "https://test/expire/1695929000/"
            if "audio" in stream_dict["mime_type"]:
                updated_stream = AudioStream(**stream_dict)
            else:
                updated_stream = VideoStream(**stream_dict)
            selected_streams_list.append(updated_stream)

    updated_streams = Streams(selected_streams_list)

    output = refresh_mpd(testing_static_mpd, updated_streams)

    actual_diff = list(
        unified_diff(
            testing_static_mpd.splitlines(keepends=True),
            output.splitlines(keepends=True),
            n=0,
        )
    )
    assert actual_diff == [
        "--- \n",
        "+++ \n",
        "@@ -2 +2 @@\n",
        "-<!--This file is created with ytpb, and expires at 2023-09-28T21:17:50+02:00-->\n",
        "+<!--This file is created with ytpb, and expires at 2023-09-28T21:23:20+02:00-->\n",
        "@@ -11 +11 @@\n",
        "-        <BaseURL>https://rr5---sn-25ge7nzr.googlevideo.com/videoplayback/expire/1695928670/ei/_nwVZYXhAqbQvdIPjKmqgAM/ip/0.0.0.0/id/kHwmzef842g.2/itag/140/source/yt_live_broadcast/requiressl/yes/spc/UWF9fy2D4rPPhPMeyQnmxgP0Yhyaohs/vprv/1/playlist_type/DVR/ratebypass/yes/mime/audio%2Fmp4/live/1/gir/yes/noclen/1/dur/2.000/keepalive/yes/fexp/24007246/beids/24350017/sparams/expire,ei,ip,id,itag,source,requiressl,spc,vprv,playlist_type,ratebypass,mime,live,gir,noclen,dur/sig/AOq0QJ8wRAIgANge9FK8aJnP8nDX_HCd9LixBc1iiZueVKgR1eWAi4ACIE5wyoXt2JUnPjHbh6xp8ZJhy1j9ScEgHiBAO_2xH3h9/initcwndbps/623750/mh/XB/mm/44/mn/sn-25ge7nzr/ms/lva/mt/1695906793/mv/m/mvi/5/pl/38/lsparams/initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/AG3C_xAwRQIhAM6lQ9DNT724pGLtqWR01mXgxu_67Ing2nzPBj4ffCT8AiAYnVuWcAosv-DKUGO2bNSq5ptYGJhRCdlYo8E3-6HKOA%3D%3D/</BaseURL>\n",
        "+        <BaseURL>https://test/expire/1695929000/</BaseURL>\n",
        "@@ -17 +17 @@\n",
        "-        <BaseURL>https://rr5---sn-25ge7nzr.googlevideo.com/videoplayback/expire/1695928670/ei/_nwVZYXhAqbQvdIPjKmqgAM/ip/0.0.0.0/id/kHwmzef842g.2/itag/244/source/yt_live_broadcast/requiressl/yes/spc/UWF9fy2D4rPPhPMeyQnmxgP0Yhyaohs/vprv/1/playlist_type/DVR/ratebypass/yes/mime/video%2Fwebm/live/1/gir/yes/noclen/1/dur/2.000/keepalive/yes/fexp/24007246/beids/24350017/sparams/expire,ei,ip,id,itag,source,requiressl,spc,vprv,playlist_type,ratebypass,mime,live,gir,noclen,dur/sig/AOq0QJ8wRgIhAJBYRElUjO7WhY5_gsjtj0aUbXbyb9Z_Yjo7JeecnqrzAiEAkzwV4SYIFponf7BddjJ5hscSZr8hbPBSx09Qffev9AA%3D/initcwndbps/623750/mh/XB/mm/44/mn/sn-25ge7nzr/ms/lva/mt/1695906793/mv/m/mvi/5/pl/38/lsparams/initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/AG3C_xAwRQIhAP_FmY_xO0cSx-hk2oibYFE1AHaCvDHeYyMXXUEuBNeVAiARmaf6MprHE-eEJJx3Ai59WyTOSt8INUUWhA7MSoEO2w%3D%3D/</BaseURL>\n",
        "+        <BaseURL>https://test/expire/1695929000/</BaseURL>\n",
    ]


def test_refresh_mpd_with_mismatched_streams(
    streams_in_list: list[AudioOrVideoStream], testing_static_mpd: str
):
    streams = Streams(streams_in_list)
    with pytest.raises(YtpbError) as exc_info:
        refresh_mpd(testing_static_mpd, streams.filter(lambda x: x.itag == "140"))
    assert str(exc_info.value) == "No stream with itag '244' in the streams"
