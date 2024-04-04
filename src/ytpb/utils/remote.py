import requests

from ytpb.errors import YtpbError
from ytpb.types import AudioOrVideoStream, SegmentSequence, VideoStream


def get_priority_reference_stream(streams: list[AudioOrVideoStream]) -> str:
    for stream in streams:
        if isinstance(stream, VideoStream):
            break
    return stream


def request_reference_sequence(
    base_url: str, session: requests.Session | None = None
) -> SegmentSequence:
    session = session or requests.Session()
    response = session.head(base_url, allow_redirects=True)
    try:
        return int(response.headers["X-Head-Seqnum"])
    except KeyError:
        raise YtpbError("'X-Head-Seqnum' header value is missing")
