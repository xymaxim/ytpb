"""Playback for live streams."""

import operator
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Literal
from urllib.parse import parse_qs, urlparse

import requests
import structlog
from platformdirs import user_cache_path

from ytpb.cache import read_from_cache, write_to_cache
from ytpb.config import USER_AGENT
from ytpb.download import compose_default_segment_filename, download_segment
from ytpb.errors import (
    BaseUrlExpiredError,
    CachedItemNotFoundError,
    MaxRetryError,
    SequenceLocatingError,
)
from ytpb.fetchers import InfoFetcher, YtpbInfoFetcher
from ytpb.info import LEFT_NOT_FETCHED, LeftNotFetched, YouTubeVideoInfo
from ytpb.locate import SegmentLocator
from ytpb.representations import extract_representations
from ytpb.segment import Segment
from ytpb.streams import SetOfStreams, Streams
from ytpb.types import (
    AbsolutePointInStream,
    PointInStream,
    RelativePointInStream,
    RelativeSegmentSequence,
    SegmentSequence,
)
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.url import (
    build_video_url_from_base_url,
    check_base_url_is_expired,
    extract_id_from_video_url,
    extract_parameter_from_url,
)

logger = structlog.get_logger(__name__)

SEGMENT_URL_PATTERN = r"https://.+\.googlevideo\.com/videoplayback/.+"


@dataclass(frozen=True)
class RewindMoment:
    """Represents a moment that has been rewound."""

    #: An actual rewound date.
    date: datetime
    #: A sequence number of a segment with a target date.
    sequence: SegmentSequence
    #: A difference (in seconds) between segment start ingestion date and target
    #: date.
    cut_at: float
    #: Wether a moment represents the end of an interval.
    is_end: bool = False
    #: Wether a moment falls in gap.
    falls_in_gap: bool = False


@dataclass(frozen=True)
class RewindInterval:
    """Represents an interval that has been rewound."""

    start: RewindMoment
    end: RewindMoment

    def __post_init__(self):
        if self.start.sequence > self.end.sequence:
            raise ValueError(
                "Start moment is ahead of the end one: "
                f"{self.start.sequence} > {self.end.sequence}"
            )

    @property
    def duration(self) -> timedelta:
        """An interval duration."""
        return self.end.date - self.start.date

    @property
    def sequences(self) -> Iterable[SegmentSequence]:
        """Segment sequence numbers that represent the interval."""
        return range(self.start.sequence, self.end.sequence + 1)


class PlaybackSession(requests.Session):
    """A session to use with :class:`Playback`.

    This session can be used to provide a retry mechanism for failed
    requests. Here is a list of handled HTTP status codes for segment URLs:

    - 403: Refresh segment base URL, and repeat a request
    - 404: Retry a request with no change
    """

    max_retries: int = 3

    def __init__(self, playback: "Playback" = None, **kwargs):
        super().__init__(**kwargs)

        self.playback = playback
        self.hooks["response"].append(self._handle_http_errors)
        self.headers["User-Agent"] = USER_AGENT

    def set_playback(self, playback):
        self.playback = playback

    def _handle_403_error(self, request: requests.Request) -> None:
        old_corresponding_stream = next(
            iter(
                self.playback.streams.filter(
                    lambda x: request.url.startswith(x.base_url)
                )
            )
        )
        old_base_url = old_corresponding_stream.base_url

        self.playback.fetch_and_set_essential()
        new_corresponding_stream = self.playback.streams.get_by_itag(
            old_corresponding_stream.itag
        )
        new_base_url = new_corresponding_stream.base_url

        request.url = request.url.replace(old_base_url, new_base_url)

    def _handle_http_errors(
        self, response: requests.Response, *args, **kwargs
    ) -> requests.Response:
        if response.ok:
            return response

        request = response.request
        retries_count = getattr(request, "retries_count", 0)

        if retries_count < self.max_retries:
            if re.match(SEGMENT_URL_PATTERN, request.url):
                logger.debug("Received %s for %s", response.status_code, request.url)
                logger.debug(
                    "Handle error, and make another try (%s of %s)",
                    retries_count + 1,
                    self.max_retries,
                )
                match response.status_code:
                    case 403:
                        self._handle_403_error(request)
                    case 404:
                        pass
                    case _:
                        logger.debug("Unhandleable error encountered, do nothing")
                        return response
                request.retries_count = retries_count + 1
                return self.send(request, verify=False)
        else:
            raise MaxRetryError(
                f"Maximum number of retries exceeded with URL: {request.url}",
                response,
            )


class Playback:
    """The playback for live streams."""

    def __init__(
        self,
        video_url: str,
        session: requests.Session | None = None,
        fetcher: InfoFetcher | None = None,
        write_to_cache: bool = False,
    ):
        """Constructs a playback.

        To work with a playback, fetch the essential information afterwards::

            playback = Playback(video_url)
            playback.fetch_and_set_essential()

        Args:
            video_url: A video URL.
            session: An instance of :class:`requests.Session`.
            fetcher: A fetcher used to gather the video information and streams.
            write_to_cache: Wether to write to cache.
        """
        self.video_url = video_url
        self.session = session or PlaybackSession(self)
        self.fetcher = fetcher or YtpbInfoFetcher(video_url)
        self._need_to_cache = write_to_cache

        self._info: YouTubeVideoInfo | LeftNotFetched | None = None
        self._streams: SetOfStreams | None = None
        self._temp_directory: Path | None = None
        self._cache_directory: Path | None = None

    @classmethod
    def from_url(cls, video_url: str, **kwargs) -> "Playback":
        """Creates a playback for the given video URL.

        This also fetches the video information and streams.

        Args:
            video_url: A video URL.
            **kwargs: Optional arguments that :class:`Playback` takes.

        Returns:
            An instance of :class:`Playback`.
        """
        playback = cls(video_url, **kwargs)
        playback.fetch_and_set_essential()
        return playback

    @classmethod
    def from_manifest(
        cls,
        manifest_path: Path,
        fetch_video_info: bool = True,
        **kwargs,
    ) -> "Playback":
        with open(manifest_path, "r") as f:
            list_of_streams = extract_representations(f.read())
            streams = Streams(list_of_streams)

        some_base_url = next(iter(streams)).base_url
        video_url = build_video_url_from_base_url(some_base_url)

        if not check_base_url_is_expired(some_base_url):
            playback = cls(video_url, **kwargs)
            playback.set_streams(streams, fetch_video_info=fetch_video_info)
        else:
            logger.debug("Found expired base url, ignore the manifest")
            raise BaseUrlExpiredError

        return playback

    @classmethod
    def from_cache(cls, video_url: str, **kwargs) -> "Playback":
        """Creates a playback for the given URL from cache.

        This also implies writing to cache. Note that an unexpired cache item
        for a stream should exist.

        Example:
            To write a new cache item, create a playback with
            ``write_to_cache=True``::

                from ytpb.errors import CachedItemNotFoundError
                try:
                    playback = Playback.from_cache(video_url)
                except CachedItemNotFoundError:
                    playback = Playback.from_url(video_url, write_to_cache=True)

        Args:
            video_url: A video URL.

        Raises:
            CachedItemNotFoundError: If a cache item is not found or expired.
        """
        video_id = extract_id_from_video_url(video_url)
        cached_item = read_from_cache(video_id, Playback.get_cache_directory())
        if cached_item is None:
            raise CachedItemNotFoundError

        playback = cls(video_url, write_to_cache=True, **kwargs)
        playback._info = YouTubeVideoInfo(**cached_item["info"])
        playback._streams = Streams.from_dicts(cached_item["streams"])

        return playback

    @staticmethod
    def get_cache_directory():
        """Gets the cache directory."""
        return user_cache_path("ytpb")

    def get_temp_directory(self) -> Path:
        """Gets the run temporary directory."""
        if self._temp_directory is None:
            self._temp_directory = Path(tempfile.mkdtemp(prefix="ytpb-"))
            logger.debug("Run temp directory set to %s", self._temp_directory)
        return self._temp_directory

    @property
    def video_url(self) -> str:
        return self._video_url

    @video_url.setter
    def video_url(self, value: str) -> None:
        self._video_url = value
        try:
            self._video_id = parse_qs(urlparse(value).query)["v"][0]
        except (KeyError, IndexError):
            print("Could not extract video ID from URL")

    @property
    def video_id(self) -> str:
        return self._video_id

    @property
    def info(self) -> YouTubeVideoInfo | LeftNotFetched:
        if self._info is None:
            raise ValueError(
                "Attribute 'info' is not set, call 'fetch_and_set_essential' first"
            )
        return self._info

    @property
    def streams(self) -> SetOfStreams:
        if self._streams is None:
            raise ValueError(
                "Attribute 'streams' is not set, call 'fetch_and_set_essential' first"
            )
        return self._streams

    def _write_to_cache_if_needed(self):
        if self._need_to_cache:
            item_to_cache = {
                "info": asdict(self._info),
                "streams": [asdict(stream) for stream in self.streams],
            }
            some_base_url = next(iter(self.streams)).base_url
            expires_at = extract_parameter_from_url("expire", some_base_url)
            cache_directory = Playback.get_cache_directory()
            write_to_cache(self.video_id, expires_at, item_to_cache, cache_directory)

    def _fetch_and_set_video_info(self) -> None:
        self._info = self.fetcher.fetch_video_info()

    def _fetch_and_set_streams(self) -> None:
        self._streams = self.fetcher.fetch_streams()

    def fetch_and_set_essential(self) -> None:
        """Fetches and sets essential information.

        Such information includes information about a video and streams.
        """

        self._fetch_and_set_video_info()
        self._fetch_and_set_streams()
        self._write_to_cache_if_needed()

    def set_streams(self, value: SetOfStreams, fetch_video_info: bool = True) -> None:
        """Sets streams manually.

        By default, it also fetches information about a video.

        Args:
            value: Streams to set.
            fetch_video_info: Wether fetch information about a video or not. If
              not, the :attr:`.info` attribute will be set to
              :attr:`ytpb.info.LEFT_NOT_FETCHED`.

        Notes:
            In most cases, you don't need this. It could be only useful, when
            you can't fetch streams the usual way, with
            :meth:`fetch_and_set_essential`.
        """
        self._streams = value
        if not self._info or fetch_video_info:
            self._fetch_and_set_video_info()
        else:
            self._info = LEFT_NOT_FETCHED
        self._write_to_cache_if_needed()

    def _get_reference_base_url(self, itag: str) -> str:
        return self.streams.get_by_itag(itag).base_url

    def download_segment(
        self,
        sequence: SegmentSequence,
        base_url: str,
        location: Literal[".", "segments"] = ".",
        force_download: bool = False,
    ) -> Path:
        """Downloads a segment.

        Args:
            sequence: A segment sequence number.
            base_url: A segment base URL.
            force_download: Wether to force download a segment even if it exists.

        Returns:
            A path to the downloaded segment.
        """
        path = download_segment(
            sequence,
            base_url,
            self.get_temp_directory() / location,
            session=self.session,
            force_download=force_download,
        )
        return path

    def get_segment(
        self,
        sequence: SegmentSequence,
        base_url: str,
        location: Literal[".", "segments"] = ".",
        download: bool = True,
    ) -> Segment:
        """Gets a :class:`Segment` representing a downloaded segment.

        By default, if a segment file cannot be found, it will be downloaded.

        Args:
            sequence: A segment sequence number.
            base_url: A segment base URL.
            location: Where a segment is located relative to
                :meth:`get_temp_directory`. The single dot ('.') represents the run
                temporary directory itself.
            download: Wether to download a segment if it doesn't exist.

        Returns:
            A :class:`Segment` object.

        Raises:
            FileNotFoundError: If couldn't find a downloaded segment.
        """
        segment_filename = compose_default_segment_filename(sequence, base_url)
        segment_directory = self.get_temp_directory() / location
        try:
            segment = Segment.from_file(segment_directory / segment_filename)
        except FileNotFoundError as exc:
            if download:
                downloaded_path = self.download_segment(sequence, base_url)
                segment = Segment.from_file(downloaded_path)
            else:
                exc.add_note(
                    "Couldn't find a segment. Make sure to download it before "
                    "and the same segment filename compose function is used"
                )
                raise
        return segment

    def locate_moment(
        self,
        point: AbsolutePointInStream,
        itag: str | None = None,
        is_end: bool = False,
    ) -> RewindMoment:
        """Locates a moment by a point in stream.

        Args:
            point: An absolute point.
            itag: An itag value.
            is_end: Wether a moment represents the end of an interval.

        Notes:
            See also :class:`ytpb.locate.SegmentLocator`.

        Returns:
            A located moment of :class:`RewindMoment`.
        """
        itag = itag or next(iter(self.streams)).itag
        base_url = self._get_reference_base_url(itag)

        match point:
            case SegmentSequence() as sequence:
                self.download_segment(sequence, base_url)
                segment = self.get_segment(sequence, base_url)
                if is_end:
                    date = segment.ingestion_end_date
                else:
                    date = segment.ingestion_start_date
                moment = RewindMoment(date, sequence, 0, is_end)
            case datetime() as date:
                sl = SegmentLocator(
                    base_url,
                    temp_directory=self.get_temp_directory(),
                    session=self.session,
                )
                locate_result = sl.find_sequence_by_time(point.timestamp(), end=is_end)
                segment = self.get_segment(locate_result.sequence, base_url)
                if locate_result.falls_in_gap:
                    if is_end:
                        date = segment.ingestion_end_date
                    else:
                        date = segment.ingestion_start_date
                    cut_at = 0
                else:
                    cut_at = locate_result.time_difference
                moment = RewindMoment(
                    date=date,
                    sequence=locate_result.sequence,
                    cut_at=cut_at,
                    is_end=is_end,
                    falls_in_gap=locate_result.falls_in_gap,
                )

        return moment

    def locate_interval(
        self,
        start_point: PointInStream,
        end_point: PointInStream,
        itag: str | None = None,
    ) -> RewindInterval:
        """Locates an interval by start and end points in stream.

        Args:
            start_point: A start absolute or relative point.
            end_point: An end absolute or relative point.
            itag: An itag value.

        Notes:
            See also :class:`ytpb.locate.SegmentLocator`.

        Returns:
           A located interval of :class:`RewindInterval`.
        """
        # First, resolve relativity where it's possible, without locating:
        start_point, end_point = resolve_relativity_in_interval(start_point, end_point)

        itag = itag or next(iter(self.streams)).itag
        if type(start_point) is type(end_point) is SegmentSequence:
            start_moment = self.locate_moment(start_point, itag=itag)
            end_moment = self.locate_moment(end_point, itag=itag, is_end=True)
            return RewindInterval(start_moment, end_moment)

        # Then, locate end if start is relative:
        if isinstance(start_point, RelativePointInStream):
            end_moment = self.locate_moment(end_point, itag=itag, is_end=True)
        else:
            end_moment = None

        # Finally, iterate over start and end points to locate moments:
        start_and_end_moments: list[RewindMoment | None] = [None, end_moment]
        for index, (point, is_start) in enumerate(
            ((start_point, True), (end_point, False))
        ):
            start_moment, end_moment = start_and_end_moments
            if isinstance(point, RelativePointInStream):
                start_moment, end_moment = start_and_end_moments
                # Given the current relative point as delta, the resulted point:
                # start/end point = end/start point -/+ delta.
                if is_start:
                    contrary_moment = end_moment
                    contrary_op = operator.sub
                else:
                    contrary_moment = start_moment
                    contrary_op = operator.add

                match point:
                    case RelativeSegmentSequence() as sequence_delta:
                        sequence = contrary_op(contrary_moment.sequence, sequence_delta)
                        moment = self.locate_moment(sequence, itag, not is_start)
                    case timedelta() as time_delta:
                        date = contrary_op(contrary_moment.date, time_delta)
                        moment = self.locate_moment(date, itag, not is_start)
            else:
                if end_moment:
                    continue
                moment = self.locate_moment(point, itag, not is_start)

            start_and_end_moments[index] = moment

        try:
            resulted_interval = RewindInterval(*start_and_end_moments)
        except ValueError as exc:
            raise SequenceLocatingError(str(exc)) from exc

        return resulted_interval
