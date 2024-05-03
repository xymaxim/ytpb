"""Fetchers are used to gather essential information about videos.

Such information includes the basic video information and streams.
"""

from abc import ABC, abstractmethod

import requests
import structlog
from yt_dlp import DownloadError, YoutubeDL

from ytpb.errors import BroadcastStatusError
from ytpb.info import BroadcastStatus, extract_video_info, YouTubeVideoInfo
from ytpb.representations import extract_representations
from ytpb.streams import Streams
from ytpb.types import AudioOrVideoStream, AudioStream, SetOfStreams, VideoStream
from ytpb.utils.url import extract_parameter_from_url

logger = structlog.get_logger(__name__)


class InfoFetcher(ABC):
    """A base abstract class for fetchers.

    Notes:
        Keep in mind that fetchers serve to fetch information, not to
        store.

        A good practice would be to treat each fetch operation as atomic and
        invoke it sequentially. This provides flexibility and will avoid
        repeated calls triggered from outside.
    """

    def __init__(self, video_url: str, session: requests.Session | None = None) -> None:
        """Constructs an object of this class.

        Args:
            video_url: A video URL.
            base_url: A segment base URL.
            session: A :class:`requests.Session` object.
        """
        self.video_url = video_url
        self.session = session or requests.Session()

    @abstractmethod
    def fetch_video_info(self):
        """Fetches basic information about a video."""
        raise NotImplementedError

    @abstractmethod
    def fetch_streams(self):
        """Fetches streams available for a video."""
        raise NotImplementedError


class YtpbInfoFetcher(InfoFetcher):
    """A native fetcher."""

    def fetch_video_info(self) -> YouTubeVideoInfo:
        logger.debug("Fetching index webpage and extracting info")

        response = self.session.get(self.video_url)
        response.raise_for_status()

        info = extract_video_info(self.video_url, response.text)
        if info.status != BroadcastStatus.ACTIVE:
            raise BroadcastStatusError("Stream is not live", info.status)
        self._info = info

        return info

    def fetch_streams(self) -> SetOfStreams:
        assert self._info, "Video info is not set"

        logger.debug("Fetching manifest file and extracting streams")

        dash_manifest_url = self._info.dash_manifest_url
        response = self.session.get(dash_manifest_url)
        response.raise_for_status()

        streams_list = extract_representations(response.text)
        streams = Streams(streams_list)

        return streams


class YoutubeDLInfoFetcher(InfoFetcher):
    """A fetcher that uses :mod:`yt_dlp` to gather information.

    All information is extracted from the :class:`~yt_dlp.YoutubeDL`'s
    information dictionary.
    """

    #: The default options passed to :class:`yt_dlp.YoutubeDL`.
    default_options = {
        "live_from_start": True,
        "quiet": True,
    }

    def __init__(
        self,
        video_url: str,
        session: requests.Session | None = None,
        options: dict | None = None,
    ) -> None:
        """Constructs an object of this class.

        Args:
            video_url: A video URL.
            base_url: A segment base URL.
            session: A :class:`requests.Session` object.
            options: Options passed to :class:`yt_dlp.YoutubeDL`.
        """
        super().__init__(video_url, session)
        self._ydl = YoutubeDL(self.default_options | (options or {}))
        self._formats: list[dict] = []

    def fetch_video_info(self) -> YouTubeVideoInfo:
        try:
            extracted = self._ydl.extract_info(self.video_url, download=False)
        except DownloadError as exc:
            raise AssertionError from exc

        try:
            self._formats = extracted["formats"]

            match extracted["live_status"]:
                case "is_live":
                    status = BroadcastStatus.ACTIVE
                case "was_live" | "post_live":
                    status = BroadcastStatus.COMPLETED
                case "is_upcoming":
                    status = BroadcastStatus.UPCOMING
                case _:
                    status = BroadcastStatus.NONE
            if status != BroadcastStatus.ACTIVE:
                raise BroadcastStatusError("Stream is not live", status)

            info = YouTubeVideoInfo(
                url=extracted["webpage_url"],
                title=extracted["title"],
                author=extracted["uploader"],
                status=status,
                dash_manifest_url=extracted["formats"][0]["manifest_url"],
            )
        except KeyError:
            raise KeyError("Failed to parse extracted info")

        return info

    def _parse_format_item(self, item: dict) -> AudioOrVideoStream:
        base_url = item["fragment_base_url"]
        raw_mime_type = extract_parameter_from_url("mime", base_url)
        mime_type = raw_mime_type.replace("%2F", "/")

        attributes = {
            "itag": item["format_id"],
            "base_url": base_url,
            "mime_type": mime_type,
        }
        if item["acodec"] != "none":
            attributes.update(
                {
                    "codecs": item["acodec"],
                    "audio_sampling_rate": item["asr"],
                }
            )
            stream = AudioStream(**attributes)
        else:
            attributes.update(
                {
                    "codecs": item["vcodec"],
                    "width": item["width"],
                    "height": item["height"],
                    "frame_rate": item["fps"],
                }
            )
            stream = VideoStream(**attributes)
        return stream

    def fetch_streams(self) -> SetOfStreams:
        assert self._formats, "Formats are not set"

        streams = Streams()
        for format_item in self._formats:
            try:
                stream = self._parse_format_item(format_item)
                streams.add(stream)
            except KeyError:
                raise AssertionError

        return streams
