import operator
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, NamedTuple
from urllib.parse import parse_qs, urlparse

import requests
import structlog
from platformdirs import user_cache_path
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from ytpb.cache import read_from_cache, write_to_cache
from ytpb.config import USER_AGENT

from ytpb.download import compose_default_segment_filename, download_segment
from ytpb.exceptions import (
    BaseUrlExpiredError,
    CachedItemNotFoundError,
    MaxRetryError,
    SequenceLocatingError,
)
from ytpb.fetchers import InfoFetcher, YtpbInfoFetcher
from ytpb.info import LEFT_NOT_FETCHED, LeftNotFetched, YouTubeVideoInfo
from ytpb.locate import SequenceLocator
from ytpb.merge import merge_segments
from ytpb.mpd import extract_representations_info
from ytpb.segment import Segment
from ytpb.streams import SetOfStreams, Streams
from ytpb.types import (
    PointInStream,
    RelativePointInStream,
    RelativeSegmentSequence,
    SegmentSequence,
    SequenceRange,
)
from ytpb.utils.other import resolve_relativity_in_interval
from ytpb.utils.url import (
    build_video_url_from_base_url,
    check_base_url_is_expired,
    extract_parameter_from_url,
    get_id_from_video_url,
)


SEGMENT_URL_PATTERN = r"https://.+\.googlevideo\.com/videoplayback/.+"

logger = structlog.get_logger()


@dataclass
class ExcerptBoundaryDates:
    input_start_date: datetime
    input_end_date: datetime
    actual_start_date: datetime
    actual_end_date: datetime


@dataclass(frozen=True)
class ExcerptFileMetadata:
    video_url: str
    actual_start_date: int
    actual_end_date: int


@dataclass(frozen=True)
class ExcerptMetadata:
    video_url: str
    input_start_date: int
    input_end_date: int
    actual_start_date: int
    actual_end_date: int


class _ExcerptDownloadResult(NamedTuple):
    exception: Exception | None
    merged_path: Path | None
    audio_segment_paths: list[Path]
    video_segment_paths: list[Path]


class PlaybackSession(requests.Session):
    max_retries: int = 3

    def __init__(self, playback: "Playback" = None, **kwargs):
        super().__init__(**kwargs)

        self.playback = playback
        self.hooks["response"].append(self._maybe_refetch_streams)
        self.headers["User-Agent"] = USER_AGENT

    def set_playback(self, playback):
        self.playback = playback

    def _maybe_refetch_streams(self, response, *args, **kwargs):
        request = response.request
        retries_count = getattr(request, "retries_count", 0)

        if re.match(SEGMENT_URL_PATTERN, request.url):
            if response.status_code == 403 and retries_count < self.max_retries:
                logger.debug("Received 403 for segment url, refetch and then retry")

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
                request.retries_count = retries_count + 1

                return self.send(request, verify=False)

        if retries_count == self.max_retries:
            raise MaxRetryError(
                f"Maximum number of retries exceeded with URL: {request.url}",
                response,
            )


class Playback:
    def __init__(
        self,
        video_url: str,
        session: requests.Session | None = None,
        fetcher: InfoFetcher | None = None,
        write_to_cache: bool = False,
        temp_directory: Path | None = None,
    ):
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
            list_of_streams = extract_representations_info(f.read())
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
        video_id = get_id_from_video_url(video_url)
        cached_item = read_from_cache(video_id, Playback.get_cache_directory())
        if cached_item is None:
            raise CachedItemNotFoundError

        playback = cls(video_url, write_to_cache=True, **kwargs)
        playback._info = YouTubeVideoInfo(**cached_item["info"])
        playback._streams = Streams.from_dicts(cached_item["streams"])

        return playback

    @staticmethod
    def get_cache_directory():
        return user_cache_path("ytpb")

    def get_temp_directory(self) -> Path:
        if self._temp_directory is None:
            self._temp_directory = Path(tempfile.mkdtemp(prefix="ytpb-"))
            logger.debug("Run temp directory set to %s", self._temp_directory)
        return self._temp_directory

    @property
    def video_url(self):
        return self._video_url

    @video_url.setter
    def video_url(self, value: str):
        self._video_url = value
        try:
            self._video_id = parse_qs(urlparse(value).query)["v"][0]
        except (KeyError, IndexError):
            print("Could not extract video ID from URL")

    @property
    def video_id(self):
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

    def fetch_and_set_essential(
        self, force_fetch=False, fetch_streams: bool = True
    ) -> None:
        self._fetch_and_set_video_info()
        if fetch_streams:
            self._fetch_and_set_streams()
        self._write_to_cache_if_needed()

    def set_streams(self, value: SetOfStreams, fetch_video_info: bool = True) -> None:
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
        sequence,
        base_url,
        location: Literal[".", "segments"] = ".",
        force_download: bool = False,
    ) -> Path:
        path = download_segment(
            sequence,
            base_url,
            self.get_temp_directory() / location,
            session=self.session,
            force_download=force_download,
        )
        return path

    def get_downloaded_segment(
        self,
        sequence: SegmentSequence,
        base_url: str,
        location: Literal[".", "segments"] = ".",
        download: bool = True,
    ) -> Segment:
        """Get a downloaded segment, or download it if it doesn't exist."""
        segment_filename = compose_default_segment_filename(sequence, base_url)
        segment_directory = self.get_temp_directory() / location
        try:
            segment = Segment.from_file(segment_directory / segment_filename)
        except FileNotFoundError:
            if download:
                downloaded_path = download_segment(
                    sequence,
                    base_url,
                    self.get_temp_directory(),
                    session=self.session,
                )
                segment = Segment.from_file(downloaded_path)
            else:
                raise
        return segment

    def locate_rewind_range(
        self,
        start_point: PointInStream,
        end_point: PointInStream,
        itag: str | None = None,
    ) -> SequenceRange:
        # First, resolve relativity where it's possible, without locating:
        start_point, end_point = resolve_relativity_in_interval(start_point, end_point)

        if type(start_point) is type(end_point) is SegmentSequence:
            return SequenceRange(start_point, end_point)
        else:
            itag = itag or next(iter(self.streams)).itag
            base_url = self._get_reference_base_url(itag)
            sl = SequenceLocator(
                base_url,
                temp_directory=self.get_temp_directory(),
                session=self.session,
            )

        # Then, locate end if start is relative:
        if isinstance(start_point, RelativePointInStream):
            if isinstance(end_point, SegmentSequence):
                end_sequence = end_point
            elif isinstance(end_point, datetime):
                end_sequence = sl.find_sequence_by_time(end_point.timestamp(), end=True)
        else:
            end_sequence = None

        # Finally, iterate over start and end points to locate sequences:
        start_and_end_sequences: list[SegmentSequence | None] = [None, end_sequence]
        for index, (point, is_start) in enumerate(
            ((start_point, True), (end_point, False))
        ):
            if isinstance(point, RelativePointInStream):
                start_sequence, end_sequence = start_and_end_sequences
                # Given the current relative point as delta, the resulted point:
                # start/end point = end/start point -/+ delta.
                if is_start:
                    contrary_sequence = end_sequence
                    contrary_op = operator.sub
                else:
                    contrary_sequence = start_sequence
                    contrary_op = operator.add

                match point:
                    case RelativeSegmentSequence() as sequence_delta:
                        sequence = contrary_op(contrary_sequence, sequence_delta)
                    case timedelta() as delta:
                        contrary_segment = self.get_downloaded_segment(
                            contrary_sequence, base_url
                        )
                        if is_start:
                            contrary_date = contrary_segment.ingestion_end_date
                        else:
                            contrary_date = contrary_segment.ingestion_start_date
                        target_date = contrary_op(contrary_date, delta)
                        sequence = sl.find_sequence_by_time(
                            target_date.timestamp(), end=not is_start
                        )
            else:
                match point:
                    case SegmentSequence():
                        sequence = point
                    case datetime() as date:
                        sequence = sl.find_sequence_by_time(
                            date.timestamp(), end=not is_start
                        )

            start_and_end_sequences[index] = sequence

        try:
            resulted_range = SequenceRange(*start_and_end_sequences)
        except ValueError as exc:
            raise SequenceLocatingError(str(exc)) from exc

        return resulted_range

    def download_excerpt(
        self,
        rewind_range: SequenceRange,
        audio_format_spec: str | None = None,
        video_format_spec: str | None = None,
        output_directory: str | Path | None = None,
        output_stem: str | Path | None = None,
        no_merge: bool = False,
        **merge_kwargs,
    ) -> _ExcerptDownloadResult:
        def _get_segment_download_progress_bar():
            return Progress(
                TextColumn("{task.description}"),
                BarColumn(bar_width=28),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TextColumn("eta"),
                TimeRemainingColumn(),
                console=Console(),
            )

        start_sequence, end_sequence = rewind_range.start, rewind_range.end
        sequences_to_download = range(start_sequence, end_sequence + 1)

        download_progress = _get_segment_download_progress_bar()

        if audio_format_spec:
            if queried := self.streams.query(audio_format_spec):
                audio_base_url = queried[0].base_url
                audio_download_task = download_progress.add_task(
                    "   - Audio", total=len(sequences_to_download)
                )
            else:
                raise AssertionError

        if video_format_spec:
            if queried := self.streams.query(video_format_spec):
                video_base_url = queried[0].base_url
                video_download_task = download_progress.add_task(
                    "   - Video", total=len(sequences_to_download)
                )
            else:
                raise AssertionError

        segments_output_directory = self.get_temp_directory() / "segments"
        segments_output_directory.mkdir(parents=True, exist_ok=True)
        download_segment_kwargs = {
            "output_directory": segments_output_directory,
            "session": self.session,
        }

        downloaded_audio_paths: list[Path] = []
        downloaded_video_paths: list[Path] = []

        with download_progress:
            for sequence in sequences_to_download:
                if audio_format_spec:
                    downloaded_path = download_segment(
                        sequence, audio_base_url, **download_segment_kwargs
                    )
                    downloaded_audio_paths.append(downloaded_path)
                    download_progress.advance(audio_download_task)
                if video_format_spec:
                    downloaded_path = download_segment(
                        sequence, video_base_url, **download_segment_kwargs
                    )
                    downloaded_video_paths.append(downloaded_path)
                    download_progress.advance(video_download_task)

        if no_merge:
            result = _ExcerptDownloadResult(
                None,
                None,
                downloaded_audio_paths,
                downloaded_video_paths,
            )
        else:
            try:
                merged_path = merge_segments(
                    downloaded_audio_paths,
                    downloaded_video_paths,
                    output_directory=output_directory,
                    output_stem=output_stem,
                    temp_directory=self.get_temp_directory(),
                    **merge_kwargs,
                )
                result = _ExcerptDownloadResult(
                    None, merged_path, downloaded_audio_paths, downloaded_video_paths
                )
            except Exception as e:
                result = _ExcerptDownloadResult(
                    e, None, downloaded_audio_paths, downloaded_video_paths
                )

        return result
