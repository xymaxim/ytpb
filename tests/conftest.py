import json
import re
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from unittest.mock import Mock, patch

import platformdirs
import pytest
import responses
from pytest_socket import disable_socket

from ytpb.info import BroadcastStatus, YouTubeVideoInfo
from ytpb.playback import InfoFetcher, Playback
from ytpb.segment import Segment
from ytpb.streams import Streams
from ytpb.types import AudioOrVideoStream, AudioStream, VideoStream
from ytpb.utils.url import extract_parameter_from_url


TEST_DATA_PATH = Path(__file__).parent / "data"


def pytest_runtest_setup():
    disable_socket()


@pytest.fixture(scope="class")
def monkeyclass():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture
def mocked_responses() -> responses.RequestsMock:
    with responses.RequestsMock() as responses_mock:
        yield responses_mock


@pytest.fixture(autouse=True)
def monkeypatch_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_temp_directory: Path
):
    monkeypatch.setattr(
        "platformdirs.user_config_path", Mock(return_value=tmp_path / "config")
    )
    monkeypatch.setattr(
        "platformdirs.user_cache_path", Mock(return_value=tmp_path / "cache")
    )
    monkeypatch.setattr(
        "ytpb.playback.Playback.get_temp_directory",
        Mock(return_value=run_temp_directory),
    )


@pytest.fixture()
def cache_directory() -> Path:
    cache_directory_path = platformdirs.user_cache_path()
    cache_directory_path.mkdir(parents=True)
    return cache_directory_path


@pytest.fixture()
def create_cache_file(
    monkeypatch: pytest.MonkeyPatch,
    video_id: str,
    active_live_video_info: YouTubeVideoInfo,
    streams_in_list: list[AudioOrVideoStream],
    tmp_path: Path,
) -> None:
    test_cache_directory = platformdirs.user_cache_path() / "ytpb"
    test_cache_directory.mkdir(parents=True)

    some_base_url = streams_in_list[0].base_url
    expired_at = int(some_base_url.split("/expire/")[1].split("/")[0])

    with open(
        test_cache_directory / f"{expired_at}~{video_id}", "w", encoding="utf-8"
    ) as f:
        test_cached_item = {
            "info": asdict(active_live_video_info),
            "streams": [asdict(stream) for stream in streams_in_list],
        }
        json.dump(test_cached_item, f)


@pytest.fixture()
def run_temp_directory(tmp_path: Path) -> Path:
    return Path(tempfile.mkdtemp(dir=tmp_path))


@pytest.fixture()
def video_id() -> str:
    return "kHwmzef842g"


@pytest.fixture()
def stream_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


@pytest.fixture()
def short_stream_url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"


@pytest.fixture()
def fake_info_fetcher(
    stream_url: str, active_live_video_info, streams_in_list
) -> "FakeInfoFetcher":
    class FakeInfoFetcher(InfoFetcher):
        def fetch_video_info(self):
            return active_live_video_info

        def fetch_streams(self):
            return Streams(streams_in_list)

    return FakeInfoFetcher(stream_url)


@pytest.fixture()
def mock_playback_info_fetcher(fake_info_fetcher):
    with patch("ytpb.playback.YtpbInfoFetcher") as mock:
        mock.return_value = fake_info_fetcher
        yield mock


@pytest.fixture()
def mock_fetch_and_set_essential(
    streams_in_list: list[AudioOrVideoStream], active_live_video_info: YouTubeVideoInfo
):
    def _mocked_fetch_and_set_essential(self: Playback, *args, **kwargs):
        self._streams = Streams(streams_in_list)
        self._info = active_live_video_info

    with patch.object(
        Playback, "fetch_and_set_essential", _mocked_fetch_and_set_essential
    ) as mock:
        yield mock


def load_segment_from_file_callback(location: str, filename: str | None = None):
    def request_callback(request):
        sequence = extract_parameter_from_url("sq", request.url)

        if filename:
            filepath = Path(location) / filename
        else:
            match extract_parameter_from_url("mime", request.url).split("%2F"):
                case ("video", "webm"):
                    filepath = Path(location) / f"{sequence}.i244.webm"
                case ("audio", "mp4"):
                    filepath = Path(location) / f"{sequence}.i140.mp4"
                case _:
                    raise ValueError("No segments matching the request URL")

        try:
            with open(filepath, "rb") as f:
                if range_value := request.headers.get("Range"):
                    size = int(range_value.split("-")[-1])
                else:
                    size = None
                segment = f.read(size)
        except FileNotFoundError as e:
            pytest.exit(e.strerror)

        return 200, {}, segment

    return request_callback


@pytest.fixture()
def add_responses_callback_for_segment_urls(mocked_responses) -> Callable:
    def wrapper(*matching_url_or_urls: str) -> None:
        matching_url_re = re.compile("|".join(matching_url_or_urls))
        mocked_responses.add_callback(
            responses.GET,
            matching_url_re,
            load_segment_from_file_callback(TEST_DATA_PATH / "segments"),
        )

    return wrapper


@pytest.fixture()
def add_responses_callback_for_reference_base_url(mocked_responses) -> Callable:
    def wrapper(reference_sequence: int = 7959203):
        mocked_responses.add_callback(
            responses.HEAD,
            re.compile(r"https://.+\.googlevideo\.com/videoplayback/.+"),
            lambda _: (200, {"X-Head-Seqnum": str(reference_sequence)}, ""),
        )

    return wrapper


@pytest.fixture()
def active_live_video_info(youtube_dl_info: dict) -> YouTubeVideoInfo:
    return YouTubeVideoInfo(
        url=youtube_dl_info["webpage_url"],
        title=youtube_dl_info["title"],
        author=youtube_dl_info["uploader"],
        status=BroadcastStatus.ACTIVE,
        dash_manifest_url=youtube_dl_info["formats"][0]["manifest_url"],
    )


@pytest.fixture()
def audio_base_url(youtube_dl_info) -> str:
    return "https://rr5---sn-25ge7nzr.googlevideo.com/videoplayback/expire/1695928670/ei/_nwVZYXhAqbQvdIPjKmqgAM/ip/0.0.0.0/id/kHwmzef842g.2/itag/140/source/yt_live_broadcast/requiressl/yes/spc/UWF9fy2D4rPPhPMeyQnmxgP0Yhyaohs/vprv/1/playlist_type/DVR/ratebypass/yes/mime/audio%2Fmp4/live/1/gir/yes/noclen/1/dur/2.000/keepalive/yes/fexp/24007246/beids/24350017/sparams/expire,ei,ip,id,itag,source,requiressl,spc,vprv,playlist_type,ratebypass,mime,live,gir,noclen,dur/sig/AOq0QJ8wRAIgANge9FK8aJnP8nDX_HCd9LixBc1iiZueVKgR1eWAi4ACIE5wyoXt2JUnPjHbh6xp8ZJhy1j9ScEgHiBAO_2xH3h9/initcwndbps/623750/mh/XB/mm/44/mn/sn-25ge7nzr/ms/lva/mt/1695906793/mv/m/mvi/5/pl/38/lsparams/initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/AG3C_xAwRQIhAM6lQ9DNT724pGLtqWR01mXgxu_67Ing2nzPBj4ffCT8AiAYnVuWcAosv-DKUGO2bNSq5ptYGJhRCdlYo8E3-6HKOA%3D%3D/"


@pytest.fixture()
def video_base_url() -> str:
    return "https://rr5---sn-25ge7nzr.googlevideo.com/videoplayback/expire/1695928670/ei/_nwVZYXhAqbQvdIPjKmqgAM/ip/0.0.0.0/id/kHwmzef842g.2/itag/244/source/yt_live_broadcast/requiressl/yes/spc/UWF9fy2D4rPPhPMeyQnmxgP0Yhyaohs/vprv/1/playlist_type/DVR/ratebypass/yes/mime/video%2Fwebm/live/1/gir/yes/noclen/1/dur/2.000/keepalive/yes/fexp/24007246/beids/24350017/sparams/expire,ei,ip,id,itag,source,requiressl,spc,vprv,playlist_type,ratebypass,mime,live,gir,noclen,dur/sig/AOq0QJ8wRgIhAJBYRElUjO7WhY5_gsjtj0aUbXbyb9Z_Yjo7JeecnqrzAiEAkzwV4SYIFponf7BddjJ5hscSZr8hbPBSx09Qffev9AA%3D/initcwndbps/623750/mh/XB/mm/44/mn/sn-25ge7nzr/ms/lva/mt/1695906793/mv/m/mvi/5/pl/38/lsparams/initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/AG3C_xAwRQIhAP_FmY_xO0cSx-hk2oibYFE1AHaCvDHeYyMXXUEuBNeVAiARmaf6MprHE-eEJJx3Ai59WyTOSt8INUUWhA7MSoEO2w%3D%3D/"


@pytest.fixture()
def youtube_dl_info() -> dict:
    with open(TEST_DATA_PATH / "info-1695928670.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def streams_in_list(youtube_dl_info: dict) -> list[AudioOrVideoStream]:
    list_of_streams: list[AudioOrVideoStream] = []
    for f in youtube_dl_info["formats"]:
        base_url = f["fragment_base_url"]
        raw_mime_type = extract_parameter_from_url("mime", base_url)
        mime_type = raw_mime_type.replace("%2F", "/")

        attributes = {
            "itag": f["format_id"],
            "base_url": base_url,
            "mime_type": mime_type,
        }
        if f["acodec"] != "none":
            attributes.update(
                {
                    "codecs": f["acodec"],
                    "audio_sampling_rate": f["asr"],
                }
            )
            stream = AudioStream(**attributes)
        else:
            attributes.update(
                {
                    "codecs": f["vcodec"],
                    "width": f["width"],
                    "height": f["height"],
                    "frame_rate": f["fps"],
                }
            )
            stream = VideoStream(**attributes)
        list_of_streams.append(stream)

    return list_of_streams


@pytest.fixture()
def audio_segment() -> Segment:
    yield Segment.from_file(TEST_DATA_PATH / "segments" / "7959120.i140.mp4")


@pytest.fixture()
def next_audio_segment() -> Segment:
    yield Segment.from_file(TEST_DATA_PATH / "segments" / "7959121.i140.mp4")
