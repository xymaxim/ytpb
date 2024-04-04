import re
import time
from urllib.parse import parse_qs, urlparse

from ytpb.errors import BadCommandArgument
from ytpb.types import SegmentSequence


def normalize_video_url(video_url_or_id: str) -> str:
    video_id_re = r"(?P<video_id>[\w-]{11})"
    patterns = (
        rf"{video_id_re}$",
        rf"https://www\.(?:youtube\.com/watch\?v=|youtu\.be\/){video_id_re}(?![^&])",
    )

    for pattern in patterns:
        if matched := re.match(pattern, video_url_or_id):
            video_url = build_video_url_with_id(matched.group("video_id"))
            break
    else:
        raise BadCommandArgument(
            "Stream URL or ID not matched. Make sure it opens in a browser."
        )

    return video_url


def extract_parameter_from_url(parameter: str, url: str) -> str:
    url_path_parts = urlparse(url).path.split("/")
    try:
        value_index = url_path_parts.index(parameter)
        value = url_path_parts[value_index + 1]
    except ValueError:
        raise Exception(f"parameter '{parameter}' is not in URL")
    except IndexError:
        raise Exception(f"value of '{parameter}' is not in URL")
    return value


def extract_media_type_from_url(url: str) -> tuple[str, str]:
    media_type = extract_parameter_from_url("mime", url)
    type_name, subtype_name = media_type.split("%2F")
    return type_name, subtype_name


def extract_id_from_base_url(base_url: str) -> str:
    return extract_parameter_from_url("id", base_url)[:11]


def extract_id_from_video_url(video_url: str) -> str:
    parsed = urlparse(video_url)
    try:
        return parse_qs(parsed.query)["v"][0]
    except KeyError:
        return parsed.path.lstrip("/")


def build_video_url_with_id(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def build_video_url_from_base_url(base_url: str) -> str:
    video_id = extract_id_from_base_url(base_url)
    return build_video_url_with_id(video_id)


def build_segment_url(base_url: str, sq: SegmentSequence | str) -> str:
    return f"{base_url.rstrip('/')}/sq/{sq}"


def check_base_url_is_expired(base_url: str) -> bool:
    expires_at = int(extract_parameter_from_url("expire", base_url))
    return time.time() >= expires_at
