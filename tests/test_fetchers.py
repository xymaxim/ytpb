from pathlib import Path
from unittest.mock import MagicMock, patch

import responses
from yt_dlp import YoutubeDL

from ytpb.fetchers import YoutubeDLInfoFetcher, YtpbInfoFetcher
from ytpb.info import YouTubeVideoInfo
from ytpb.playback import Playback
from ytpb.streams import AudioOrVideoStream


@patch("ytpb.fetchers.extract_video_info")
@patch("ytpb.fetchers.extract_representations")
def test_ytpb_info_fetcher(
    mock_extract_representations: MagicMock,
    mock_extract_video_info: MagicMock,
    mocked_responses: responses.RequestsMock,
    stream_url: str,
    active_live_video_info: YouTubeVideoInfo,
    streams_in_list: list[AudioOrVideoStream],
    tmp_path: Path,
):
    mocked_responses.get(stream_url, status=200)
    mocked_responses.get(active_live_video_info.dash_manifest_url, status=200)

    mock_extract_video_info.return_value = active_live_video_info
    mock_extract_representations.return_value = streams_in_list

    fetcher = YtpbInfoFetcher(stream_url)
    assert fetcher.fetch_video_info() == active_live_video_info
    assert len(fetcher.fetch_streams()) == len(streams_in_list)


def test_youtube_dl_info_fetcher(
    stream_url: str,
    active_live_video_info: YouTubeVideoInfo,
    streams_in_list: list[AudioOrVideoStream],
    youtube_dl_info: dict,
    tmp_path: Path,
):
    with patch.object(YoutubeDL, "extract_info", autospec=True) as mock:
        mock.return_value = youtube_dl_info

        fetcher = YoutubeDLInfoFetcher(stream_url)
        playback = Playback(stream_url, fetcher=fetcher)
        playback.fetch_and_set_essential()

    assert playback.info == active_live_video_info
    assert len(playback.streams) == len(streams_in_list)
