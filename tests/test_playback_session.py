import copy
from dataclasses import asdict
from unittest.mock import patch
from urllib.parse import urljoin

import pytest
import responses
from ytpb.errors import MaxRetryError

from ytpb.playback import Playback
from ytpb.streams import AudioStream, Streams


class SideEffectCycler:
    def __init__(self, side_effects):
        self._side_effects = iter(side_effects)

    def __call__(self, *args, **kwargs):
        return next(self._side_effects)(*args, **kwargs)


@pytest.fixture()
def make_refresh_base_url_side_effect(streams_in_list, active_live_video_info):
    def wrapper(itag: str, new_base_url: str):
        def side_effect(obj: Playback, *args, **kwargs):
            updated_streams = copy.deepcopy(streams_in_list)
            for i, stream in enumerate(updated_streams):
                if stream.itag == itag:
                    stream_attributes = asdict(stream)
                    stream_attributes["base_url"] = new_base_url
                    updated_streams[i] = AudioStream(**stream_attributes)
                    break
            obj._streams = Streams(updated_streams)
            obj._info = active_live_video_info

        return side_effect

    return wrapper


def test_retry_on_403_for_segment_url(
    mocked_responses: responses.RequestsMock,
    mock_fetch_and_set_essential,
    make_refresh_base_url_side_effect,
    stream_url: str,
    audio_base_url: str,
) -> None:
    # Given:
    initial_segment_url = urljoin(audio_base_url, "sq/0")
    mocked_responses.get(initial_segment_url, status=403)

    refreshed_base_url = "https://test.googlevideo.com/videoplayback/test/"
    refreshed_segment_url = urljoin(refreshed_base_url, "sq/0")
    mocked_responses.get(refreshed_segment_url, status=200)

    # When:
    playback = Playback(stream_url)
    playback.fetch_and_set_essential()

    with patch.object(Playback, "fetch_and_set_essential", autospec=True) as mock:
        mock.side_effect = make_refresh_base_url_side_effect("140", refreshed_base_url)
        response = playback.session.get(initial_segment_url)

    # Then:
    assert response.status_code == 200
    assert response.url == refreshed_segment_url


def test_retry_on_404_for_segment_url(
    mocked_responses: responses.RequestsMock,
    mock_fetch_and_set_essential,
    stream_url: str,
    audio_base_url: str,
) -> None:
    # Given:
    initial_segment_url = urljoin(audio_base_url, "sq/0")
    mocked_responses.get(initial_segment_url, status=404)
    mocked_responses.get(initial_segment_url, status=200)

    # When:
    playback = Playback(stream_url)
    playback.fetch_and_set_essential()

    response = playback.session.get(initial_segment_url)

    # Then:
    assert response.status_code == 200
    assert response.url == initial_segment_url


def test_retry_on_unknown_for_segment_url(
    mocked_responses: responses.RequestsMock,
    mock_fetch_and_set_essential,
    stream_url: str,
    audio_base_url: str,
) -> None:
    # Given:
    initial_segment_url = urljoin(audio_base_url, "sq/0")
    mocked_responses.get(initial_segment_url, status=401)

    # When:
    playback = Playback(stream_url)
    playback.fetch_and_set_essential()
    response = playback.session.get(initial_segment_url)

    # Then:
    assert response.status_code == 401


def test_max_retries_exceeded_with_segment_url(
    mocked_responses: responses.RequestsMock,
    mock_fetch_and_set_essential,
    stream_url: str,
    audio_base_url: str,
) -> None:
    segment_url = urljoin(audio_base_url, "sq/0")
    mocked_responses.get(segment_url, status=403)

    playback = Playback(stream_url)
    playback.fetch_and_set_essential()

    with pytest.raises(MaxRetryError) as exc_info:
        playback.session.get(segment_url)

    assert exc_info.value.response.status_code == 403


def test_retry_head_request_with_segment_base_url(
    mocked_responses: responses.RequestsMock,
    mock_fetch_and_set_essential,
    make_refresh_base_url_side_effect,
    audio_base_url: str,
    stream_url: str,
) -> None:
    # Given:
    refreshed_base_url = "https://test.googlevideo.com/videoplayback/test/"
    mocked_responses.head(audio_base_url, status=403)
    mocked_responses.head(refreshed_base_url, status=200)

    # When:
    playback = Playback(stream_url)
    playback.fetch_and_set_essential()

    with patch.object(Playback, "fetch_and_set_essential", autospec=True) as mock:
        mock.side_effect = make_refresh_base_url_side_effect("140", refreshed_base_url)
        response = playback.session.head(audio_base_url)

    # Then:
    assert response.status_code == 200
    assert response.url == refreshed_base_url
