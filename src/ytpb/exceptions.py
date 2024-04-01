from __future__ import annotations

from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ytpb.info import BroadcastStatus


class YtpbError(Exception):
    """Base Ytpb exception."""


class BroadcastStatusError(YtpbError):
    """Raised because of :class:`ytpb.info.BroadcastStatus`."""

    def __init__(self, message: str, status: BroadcastStatus):
        self.status = status
        super().__init__(message)


class InfoExtractError(YtpbError):
    """Failed to extract a YouTube video information."""


class BaseUrlExpiredError(YtpbError):
    pass


class CachedItemNotFoundError(YtpbError):
    """Failed to find an unexpired cached item."""

    def __str__(self) -> str:
        return "Unexpired cached item doesn't exist for the video"


class MaxRetryError(YtpbError):
    """Raised when retry limit has been exceeded."""

    def __init__(self, message, response):
        self.response = response
        super().__init__(message)


class FFmpegRunError(YtpbError):
    """Raised during FFmpeg subprocess call."""


class QueryError(YtpbError):
    """Failed to query streams with format spec."""


class BadCommandArgument(YtpbError):
    pass


class SequenceLocatingError(YtpbError):
    """Failed to locate a segment."""


class SegmentDownloadError(YtpbError, requests.exceptions.HTTPError):
    """Failed to download a segment."""

    def __init__(self, message: str, sequence: int):
        self.sequence = sequence
        super().__init__(message)
