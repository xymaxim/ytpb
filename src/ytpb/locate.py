"""Locate segments by given times."""

import math
import tempfile
from bisect import bisect_left
from functools import partial
from pathlib import Path
from typing import NamedTuple, Self

import requests
import structlog

from ytpb.download import compose_default_segment_filename, download_segment
from ytpb.errors import SegmentDownloadError, SequenceLocatingError
from ytpb.segment import Segment, SegmentMetadata
from ytpb.types import SegmentSequence, Timestamp
from ytpb.utils.remote import request_reference_sequence
from ytpb.utils.url import extract_parameter_from_url

__all__ = ("SegmentLocator", "LocateResult")


logger = structlog.get_logger(__name__)

#: Number of bytes sufficient to cover the YouTube metadata in segment
#: files. Note that the minimum value varies for different media formats, so the
#: value was determined empirically for all available MPEG-DASH formats.
PARTIAL_SEGMENT_SIZE_BYTES = 2000

# Absolute time difference tolerance (in seconds). See issue #5.
TIME_DIFF_TOLERANCE = 3e-2


class SequenceMetadataPair:
    """Represents a pair of segment sequence number and :class:`SegmentMetadata`."""

    def __init__(self, sequence: SegmentSequence, locator: "SegmentLocator"):
        self.locator = locator
        self.sequence = sequence

    @property
    def sequence(self) -> SegmentSequence:
        return self._sequence

    @sequence.setter
    def sequence(self, value: SegmentSequence):
        self._sequence = value
        self._metadata = self._download_segment_and_parse_metadata(value)

    @property
    def metadata(self):
        return self._metadata

    def _download_segment_and_parse_metadata(
        self, sequence: SegmentSequence
    ) -> SegmentMetadata:
        """Download a partial segment and parse metadata."""
        segment_filename = compose_default_segment_filename(
            sequence, self.locator.base_url
        )
        output_filename = segment_filename + ".part"
        downloaded_path = download_segment(
            sequence,
            self.locator.base_url,
            output_directory=self.locator.get_temp_directory(),
            output_filename=output_filename,
            size=PARTIAL_SEGMENT_SIZE_BYTES,
            session=self.locator.session,
            force_download=False,
        )
        with open(downloaded_path, "rb") as f:
            metadata = Segment.parse_youtube_metadata(f.read())
        return metadata


class LocateResult(NamedTuple):
    """Represents a locate result."""

    #: A segment sequence number.
    sequence: SegmentSequence
    #: A time difference between a target time and
    #: :attr:`ytpb.segment.Segment.ingestion_start_date`.
    time_difference: float
    #: Wheter a target time falls in gap.
    falls_in_gap: bool
    #: Stores all locate steps as pairs of segment sequence nubmer and time
    #: difference.
    track: list[tuple[SegmentSequence, float]]


class SegmentLocator:
    """A class that locates a segment with a desired time.

    A timeline may contain numerous gaps, which leads to under- or
    overestimation, and it needs to be taken into account.

    The locating consists of three steps: (1) a "look around", jump-based search
    to find a segment directly or outline a search domain (the jump length is
    based on the time difference and constant duration of segments); (2) search
    for a segment in the outlined domain using a binary search if a segment is
    not found in the previous step; (3) check whether a target time falls in gap
    or not.
    """

    def __init__(
        self,
        base_url: str,
        reference_sequence: SegmentSequence | None = None,
        temp_directory: Path | None = None,
        session: requests.Session | None = None,
    ) -> Self:
        """Constructs a segment locator.

        Args:
            base_url: A segment base URL.
            reference_sequence: A segment sequence number used as a reference.
            temp_directory: A temporary directory used to store downloaded
              segments during locating.
            session: A :class:`request.Session` object.
        """
        self._temp_directory = temp_directory
        self.base_url = base_url
        self.session = session or requests.Session()

        if reference_sequence is None:
            reference_sequence = request_reference_sequence(base_url)
        self.reference = SequenceMetadataPair(reference_sequence, self)
        self.candidate: SequenceMetadataPair | None = None

        self.segment_duration = float(extract_parameter_from_url("dur", base_url))
        self.track: list[tuple[SegmentSequence, float]] = []

    def get_temp_directory(self):
        """Gets (and creates if needed) a temporary directory."""
        if self._temp_directory is None:
            self._temp_directory = tempfile.mkdtemp()
        return self._temp_directory

    def _download_full_segment(self, sequence: SegmentSequence) -> Path:
        downloaded_path = download_segment(
            sequence,
            self.base_url,
            output_directory=self.get_temp_directory(),
            session=self.session,
        )
        return downloaded_path

    def _find_time_diff(
        self, candidate: SequenceMetadataPair, desired_time: Timestamp
    ) -> float:
        return desired_time - candidate.metadata.ingestion_walltime

    def _get_bisected_segment_timestamp(
        self, sequence: SegmentSequence, *, target: Timestamp
    ) -> Timestamp:
        self.candidate.sequence = sequence
        current_diff_in_s = self._find_time_diff(self.candidate, target)
        self.track.append((sequence, current_diff_in_s))
        logger.debug(
            "Bisect step, time difference: %+f s",
            current_diff_in_s,
            seq=self.candidate.sequence,
            time=self.candidate.metadata.ingestion_walltime,
        )
        return self.candidate.metadata.ingestion_walltime

    def _search_sequence(
        self,
        desired_time: Timestamp,
        start: SegmentSequence,
        end: SegmentSequence,
        is_end: bool,
    ) -> LocateResult:
        """Search for a segment with a desired time inside a search domain with
        the given start and end sequence numbers and perform a gap check."""
        search_domain = range(min((start, end)), max((start, end)) + 1)
        logger.debug("Start a binary search", domain=search_domain)
        bisect_key = partial(self._get_bisected_segment_timestamp, target=desired_time)
        found_index = bisect_left(search_domain, desired_time, key=bisect_key)
        self.candidate.sequence = search_domain[found_index - 1]

        # After the previous step the time difference is always positive.
        current_diff_in_s = self._find_time_diff(self.candidate, desired_time)
        if current_diff_in_s == 0:
            return LocateResult(self.candidate.sequence, 0, False, self.track)

        downloaded_path = self._download_full_segment(self.candidate.sequence)
        candidate_segment = Segment.from_file(downloaded_path)
        candidate_duration = candidate_segment.get_actual_duration()

        logger.debug(
            "Candidate time difference: %+f s, actual duration: %f s",
            current_diff_in_s,
            candidate_duration,
        )

        falls_in_gap = False
        if candidate_duration < current_diff_in_s - TIME_DIFF_TOLERANCE:
            falls_in_gap = True
            logger.debug("Input target time falls in a gap")
            if not is_end:
                self.candidate.sequence += 1
                current_diff_in_s = self._find_time_diff(self.candidate, desired_time)
                self.track.append((self.candidate.sequence, current_diff_in_s))
                logger.debug(
                    "Step to adjacent segment, time difference: %+f s",
                    current_diff_in_s,
                    seq=self.candidate.sequence,
                    time=self.candidate.metadata.ingestion_walltime,
                )

        return LocateResult(
            self.candidate.sequence, current_diff_in_s, falls_in_gap, self.track
        )

    def find_sequence_by_time(
        self, desired_time: Timestamp, end: bool = False
    ) -> LocateResult:
        """Finds sequence number of a segment by the given timestamp.

        Args:
            desired_time: A target Unix timestamp.
            end: Whether a segment belongs to the end of an interval.

        Returns:
            A :class:`LocateResult` object.
        """
        logger.info(
            "Locating segment",
            end=end,
            target=desired_time,
            reference=self.reference.sequence,
        )

        current_diff_in_s = self._find_time_diff(self.reference, desired_time)
        start_direction = int(math.copysign(1, current_diff_in_s))
        self.candidate = self.reference

        has_segment_found = False

        has_domain_discovered = False
        has_sign_changed = False

        while not has_domain_discovered:
            self.track.append((self.candidate.sequence, current_diff_in_s))
            logger.debug(
                "Look around, time difference: %+f s",
                current_diff_in_s,
                seq=self.candidate.sequence,
                time=self.candidate.metadata.ingestion_walltime,
            )

            if 0 <= current_diff_in_s <= self.segment_duration + TIME_DIFF_TOLERANCE:
                has_segment_found = True
                break

            direction = int(math.copysign(1, current_diff_in_s))
            if not has_sign_changed:
                has_sign_changed = direction * start_direction < 0
            has_domain_discovered = has_sign_changed and direction == start_direction

            jump_length_in_seq = int(current_diff_in_s // self.segment_duration)
            self.candidate = SequenceMetadataPair(
                self.candidate.sequence + jump_length_in_seq, self
            )
            current_diff_in_s = self._find_time_diff(self.candidate, desired_time)

        if has_segment_found:
            result = LocateResult(
                self.candidate.sequence, current_diff_in_s, False, self.track
            )
        else:
            try:
                search_between = (self.track[-2][0], self.track[-1][0])
                result = self._search_sequence(desired_time, *search_between, end)
            except SegmentDownloadError as exc:
                raise SequenceLocatingError(exc) from exc

        logger.info("Segment has been located as %d", self.candidate.sequence)

        return result
