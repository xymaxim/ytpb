import re

from conftest import TEST_DATA_PATH
from lxml import etree

from ytpb import mpd


def test_strip_manifest():
    manifest = etree.parse(TEST_DATA_PATH / "manifest-1695928670.mpd")

    stripped_tags = ["<SegmentList", "<SegmentTimeline", "<SegmentURL", r"<S\s"]
    stripped_tags_re = re.compile("|".join(stripped_tags).encode())
    assert stripped_tags_re.search(etree.tostring(manifest))

    output = mpd.strip_manifest(manifest)
    assert output and not stripped_tags_re.search(output)


def test_extract_representations_info(audio_base_url: str, video_base_url: str):
    with open(TEST_DATA_PATH / "manifest-1695928670.mpd") as f:
        results = mpd.extract_representations_info(f.read())

    assert (
        mpd.AudioRepresentationInfo(
            itag="140",
            codecs="mp4a.40.2",
            mime_type="audio/mp4",
            base_url=audio_base_url,
            audio_sampling_rate=44100,
        )
        in results
    )
    assert (
        mpd.VideoRepresentationInfo(
            itag="244",
            codecs="vp9",
            mime_type="video/webm",
            base_url=video_base_url,
            width=854,
            height=480,
            frame_rate=30,
        )
        in results
    )
