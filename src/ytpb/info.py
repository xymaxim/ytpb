import re
from dataclasses import dataclass
from enum import auto, StrEnum
from typing import Any

from lxml import etree

from ytpb.exceptions import InfoExtractError


class BroadcastStatus(StrEnum):
    ACTIVE = auto()
    UPCOMING = auto()
    COMPLETED = auto()
    NONE = auto()


@dataclass
class YouTubeVideoInfo:
    """Information about YouTube video."""

    url: str
    title: str
    author: str
    status: BroadcastStatus
    dash_manifest_url: str | None = None


class LeftNotFetched:
    """Represents a value that is intentionally not fetched."""


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
