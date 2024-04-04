import pytest

from ytpb.errors import BadCommandArgument
from ytpb.utils.url import (
    extract_media_type_from_url,
    extract_parameter_from_url,
    normalize_video_url,
)


def test_extract_itag_from_url(audio_base_url):
    assert extract_parameter_from_url("itag", audio_base_url) == "140"


def test_extract_mime_type_from_url(audio_base_url):
    assert extract_media_type_from_url(audio_base_url) == ("audio", "mp4")


@pytest.mark.parametrize(
    "stream_url_or_id",
    [
        "https://www.youtube.com/watch?v=kHwmzef842g",
        "https://www.youtube.com/watch?v=kHwmzef842g&param=value",
        "https://www.youtu.be/kHwmzef842g",
        "kHwmzef842g",
    ],
)
def test_normalize_video_url(stream_url_or_id):
    expected = "https://www.youtube.com/watch?v=kHwmzef842g"
    assert expected == normalize_video_url(stream_url_or_id)


@pytest.mark.parametrize(
    "stream_url_or_id",
    [
        "https://www.youtube.com/watch?v=kHwmzef842gxxx",
        "https://www.youtube.com/watch?v=kHwmzef",
        "https://www.youtu.be/kHwmzef842gxxx",
        "kHwmzef842gxxx",
        "kHwmzef",
    ],
)
def test_failed_normalize_video_url(stream_url_or_id):
    with pytest.raises(BadCommandArgument):
        normalize_video_url(stream_url_or_id)
