"""Basic information about videos."""

import re
from dataclasses import dataclass
from enum import auto, StrEnum
from typing import Any

from lxml import etree

from ytpb.errors import InfoExtractError
from ytpb.utils.other import normalize_info_string


class BroadcastStatus(StrEnum):
    """Represents a live broadcast status."""

    #: A broadcast is live.
    ACTIVE = auto()
    #: A broadcast has been scheduled but started.
    UPCOMING = auto()
    #: A broadcast has been completed.
    COMPLETED = auto()
    #: A video is not a live broadcast.
    NONE = auto()


@dataclass
class YouTubeVideoInfo:
    """Represents information about a video."""

    #: Youtube video URL.
    url: str
    #: Video's title.
    title: str
    #: Video's author (channel's name).
    author: str
    #: Video' broadcast status.
    status: BroadcastStatus
    dash_manifest_url: str | None = None

    def __post_init__(self):
        self.title = normalize_info_string(self.title)
        self.author = normalize_info_string(self.author)


class LeftNotFetched:
    pass


#: A sentinel object for a value that is intentionally not fetched.
LEFT_NOT_FETCHED = LeftNotFetched()


def _find_one_or_raise(element: etree.Element, path: str, message: str = "") -> Any:
    """Find first subelement or value which matches the given XPath expression
    or raise an InfoExtractError error."""
    try:
        (result,) = element.xpath(path)
        return result
    except ValueError as exc:
        raise InfoExtractError(message) from exc


def _extract_dash_manifest_url(index_page: str) -> str:
    matched = re.search(r"(?<=dashManifestUrl\":\").*?(?=\")", index_page)
    if not matched:
        raise InfoExtractError("Could not find DASH manifest URL")
    return matched[0]


def extract_video_info(url: str, index_page_text: str) -> YouTubeVideoInfo:
    """Extracts an information about a video from an index page.

    Args:
        url: A video URL.
        index_page_text: An index page string content.

    Returns:
        A :class:`YouTubeVideoInfo` filled with extracted attributes.

    Raises:
        InfoExtractError: If failed to extract an attribute.
    """
    index_page_element = etree.HTML(index_page_text)

    # Extracting title and author:
    video_object_element = _find_one_or_raise(
        index_page_element,
        './/*[@itemtype="http://schema.org/VideoObject"]',
        "Could not find a http://schema.org/VideoObject element",
    )
    title = _find_one_or_raise(
        video_object_element,
        './meta[@itemprop="name"]/@content',
        "Could not extract a title",
    )
    author = _find_one_or_raise(
        video_object_element,
        './*[@itemtype="http://schema.org/Person"]/link[@itemprop="name"]/@content',
        "Could not extract an author",
    )

    # Check if a video is a live stream or not:
    if (
        broadcast_event_element := index_page_element.find(
            './/*[@itemtype="http://schema.org/BroadcastEvent"]'
        )
    ) is not None:
        is_completed = bool(broadcast_event_element.find('./meta[@itemprop="endDate"]'))
        if is_completed:
            status = BroadcastStatus.COMPLETED
            dash_manifest_url = None
        else:
            status = BroadcastStatus.ACTIVE
            dash_manifest_url = _extract_dash_manifest_url(index_page_text)
    else:
        status = BroadcastStatus.NONE
        dash_manifest_url = None

    return YouTubeVideoInfo(url, title, author, status, dash_manifest_url)
