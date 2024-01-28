from abc import ABC, abstractmethod

import requests
import structlog
from yt_dlp import DownloadError, YoutubeDL

from ytpb.exceptions import BroadcastStatusError
from ytpb.info import BroadcastStatus, extract_video_info, YouTubeVideoInfo
from ytpb.mpd import extract_representations_info
from ytpb.streams import Streams
from ytpb.types import AudioOrVideoStream, AudioStream, VideoStream
from ytpb.utils.url import extract_parameter_from_url

logger = structlog.get_logger(__name__)


class InfoFetcher(ABC):
    def __init__(self, video_url: str, session: requests.Session | None = None):
        self.video_url = video_url
        self.session = session or requests.Session()

    @abstractmethod
    def fetch_video_info(self):
        raise NotImplementedError

    @abstractmethod
    def fetch_streams(self, force_fetch: bool = True):
        raise NotImplementedError


class YtpbInfoFetcher(InfoFetcher):
    def fetch_video_info(self):
        logger.debug("Fetching index webpage and extracting video info")

        response = self.session.get(self.video_url)
        response.raise_for_status()

        info = extract_video_info(self.video_url, response.text)
        if info.status != BroadcastStatus.ACTIVE:
            raise BroadcastStatusError("Stream is not live", info.status)
        self.info = info

        return self.info

    def fetch_streams(self, force_fetch: bool = True):
        logger.debug("Fetching manifest file and extracting streams info")

        dash_manifest_url = self.info.dash_manifest_url
        response = self.session.get(dash_manifest_url)
        response.raise_for_status()

        streams_list = extract_representations_info(response.text)
        streams = Streams(streams_list)

        return streams


class YoutubeDLInfoFetcher(InfoFetcher):
    options = {
        "live_from_start": True,
        "quiet": True,
    }

    def __init__(self, video_url: str, session: requests.Session | None = None):
        super().__init__(video_url, session)
        self._ydl = YoutubeDL(self.options)
        self._formats: list[dict] = []

    def fetch_video_info(self):
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

    def fetch_streams(self, force_fetch: bool = True):
        streams = Streams()

        if not self._formats or force_fetch:
            self.fetch_video_info()

        for format_item in self._formats:
            try:
                stream = self._parse_format_item(format_item)
                streams.add(stream)
            except KeyError:
                raise AssertionError

        return streams
