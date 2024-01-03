from __future__ import annotations

from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ytpb.info import BroadcastStatus


class YtpbError(Exception):
    """Base Ytpb exception."""


class BroadcastStatusError(YtpbError):
    def __init__(self, message: str, status: BroadcastStatus):
        self.status = status
        super().__init__(message)


class InfoExtractError(YtpbError):
    pass


class BaseUrlExpiredError(YtpbError):
    pass


class CachedItemNotFoundError(YtpbError):
    def __str__(self) -> str:
        return "Unexpired cached item doesn't exist for the video"


class MaxRetryError(YtpbError):
    """Raised when retry limit has been exceeded."""

    def __init__(self, message, response):
        self.response = response
        super().__init__(message)


class FFmpegRunError(YtpbError):
    pass


class QueryError(YtpbError):
    pass


class BadCommandArgument(YtpbError):
    pass


class SequenceLocatingError(YtpbError):
    pass


class SegmentDownloadError(YtpbError, requests.exceptions.HTTPError):
    def __init__(self, message: str, sequence: int):
        self.sequence = sequence
        super().__init__(message)
