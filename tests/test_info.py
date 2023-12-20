from dataclasses import asdict

from conftest import TEST_DATA_PATH

from ytpb import info


def test_extract_video_info(stream_url: str, active_live_video_info):
    with open(TEST_DATA_PATH / "webpage-1695928670.html") as f:
        result = info.extract_video_info(stream_url, f.read())
    assert asdict(result) == asdict(active_live_video_info)
