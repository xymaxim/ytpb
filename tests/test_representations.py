from ytpb import representations

from .conftest import TEST_DATA_PATH


def test_representation_properties(audio_base_url):
    representation = representations.AudioRepresentationInfo(
        itag="140",
        codecs="mp4a.40.2",
        mime_type="audio/mp4",
        base_url=audio_base_url,
        audio_sampling_rate=44100,
    )
    assert representation.type == "audio"
    assert representation.format == "mp4"


def test_extract_representations_info(audio_base_url: str, video_base_url: str):
    with open(TEST_DATA_PATH / "manifest-1695928670.mpd") as f:
        results = representations.extract_representations(f.read())

    assert (
        representations.AudioRepresentationInfo(
            itag="140",
            codecs="mp4a.40.2",
            mime_type="audio/mp4",
            base_url=audio_base_url,
            audio_sampling_rate=44100,
        )
        in results
    )
    assert (
        representations.VideoRepresentationInfo(
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
